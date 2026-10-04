import base64
import binascii
import json
import logging
import os
import re

from botocore.exceptions import ClientError

from async_store import AsyncStore, IdempotencyConflictError
from authorization import (
    authorize_request,
    ForbiddenError,
    UnauthenticatedError,
)
from handler import http_response
from service import validate_request, InvalidRequestError

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def error_response(status, code, message):
    return http_response(status, {"code": code, "message": message})


def authenticated_client(event):
    try:
        client_id = event["requestContext"]["authorizer"]["jwt"]["claims"]["client_id"]
    except (KeyError, TypeError):
        raise UnauthenticatedError("Authenticated client identity is required")

    if not isinstance(client_id, str) or not client_id:
        raise UnauthenticatedError("Authenticated client identity is required")
    return client_id


def parse_body(event):
    body = event.get("body")
    if not isinstance(body, str) or not body:
        raise InvalidRequestError("A JSON request body is required")

    if event.get("isBase64Encoded"):
        try:
            body = base64.b64decode(body, validate=True).decode("utf-8")
        except (binascii.Error, UnicodeError, ValueError):
            raise InvalidRequestError("Invalid encoded request body")

    try:
        return json.loads(body)
    except json.JSONDecodeError:
        raise InvalidRequestError("Request body must be valid JSON")


def lambda_handler(event, context):
    route = event.get("routeKey")

    try:
        client_id = authenticated_client(event)

        if route == "POST /eligibility-requests":
            request = parse_body(event)
            validate_request(request)
            authorize_request(event, request)

            headers = {
                name.lower(): value
                for name, value in (event.get("headers") or {}).items()
            }
            key = headers.get("idempotency-key")
            if not isinstance(key, str) or not re.fullmatch(
                r"[A-Za-z0-9_-]{1,128}", key
            ):
                raise InvalidRequestError("A valid Idempotency-Key is required")

            store = AsyncStore(os.environ["REQUEST_TABLE_NAME"])
            request_id = store.create_request(client_id, key, request)

            logger.info(
                "Accepted request %s; API request ID %s",
                request_id,
                event.get("requestContext", {}).get("requestId"),
            )
            return http_response(202, {
                "requestId": request_id,
                "statusUrl": f"/eligibility-requests/{request_id}",
            })

        if route == "GET /eligibility-requests/{requestId}":
            request_id = (event.get("pathParameters") or {}).get("requestId")
            if not isinstance(request_id, str) or not re.fullmatch(
                r"[A-Za-z0-9_-]{1,128}", request_id
            ):
                raise InvalidRequestError("Invalid request ID")

            store = AsyncStore(os.environ["REQUEST_TABLE_NAME"])
            record = store.get_request(client_id, request_id)
            if record is None:
                return error_response(
                    404, "REQUEST_NOT_FOUND", "Request not found"
                )

            authorize_request(event, {
                "merchantId": record["merchantId"],
                "component": record["component"],
            })

            response = {
                field: record[field]
                for field in ("requestId", "merchantId", "component", "status")
            }
            if record["status"] == "SUCCEEDED":
                response["result"] = record["result"]
            elif record["status"] == "FAILED":
                response["error"] = record["error"]

            return http_response(200, response)

        return error_response(404, "ROUTE_NOT_FOUND", "Route not found")

    except UnauthenticatedError as error:
        return error_response(401, "UNAUTHENTICATED", str(error))
    except ForbiddenError as error:
        return error_response(403, "FORBIDDEN", str(error))
    except InvalidRequestError as error:
        return error_response(400, "INVALID_REQUEST", str(error))
    except IdempotencyConflictError as error:
        return error_response(409, "IDEMPOTENCY_CONFLICT", str(error))
    except ClientError:
        logger.exception("Asynchronous API database operation failed")
        if route == "POST /eligibility-requests":
            return error_response(
                503, "ACCEPTANCE_UNCONFIRMED",
                "Retry with the same idempotency key and body",
            )
        return error_response(500, "INTERNAL_ERROR", "Unable to retrieve request")
    except Exception:
        logger.exception("Asynchronous API failed")
        return error_response(500, "INTERNAL_ERROR", "Unexpected internal failure")
