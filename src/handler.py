import base64
import binascii
import json
import logging

from authorization import (
    authorize_request,
    UnauthenticatedError,
    ForbiddenError,
)

from backends import MerchantNotFoundError
from service import check_eligibility, validate_request, InvalidRequestError

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def http_response(status_code, payload):
    return {
        "statusCode": status_code,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(payload),
        "isBase64Encoded": False,
    }


def lambda_handler(event, context):
    try:
        body = event.get("body")
        if not isinstance(body, str) or not body:
            raise InvalidRequestError("A JSON request body is required")

        if event.get("isBase64Encoded", False):
            try:
                body = base64.b64decode(body, validate=True).decode("utf-8")
            except (binascii.Error, UnicodeDecodeError, ValueError):
                raise InvalidRequestError("Invalid encoded request body")

        try:
            request = json.loads(body)
        except json.JSONDecodeError:
            raise InvalidRequestError("Request body must be valid JSON")

        validate_request(request)
        authorize_request(event, request)
        result = check_eligibility(request)
        return http_response(200, result)

    except UnauthenticatedError as error:
        return http_response(401, {
            "code": "UNAUTHENTICATED",
            "message": str(error),
        })

    except ForbiddenError as error:
        return http_response(403, {
            "code": "FORBIDDEN",
            "message": str(error),
        })

    except InvalidRequestError as error:
        return http_response(400, {
            "code": "INVALID_REQUEST",
            "message": str(error),
        })

    except MerchantNotFoundError as error:
        return http_response(404, {
            "code": "MERCHANT_NOT_FOUND",
            "message": str(error),
        })

    except Exception:
        logger.exception("Eligibility lookup failed")
        return http_response(500, {
            "code": "INTERNAL_ERROR",
            "message": "Unable to complete eligibility lookup",
        })
