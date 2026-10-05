import base64
import json
import logging
import os
import re
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from demo_auth import get_demo_token


logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def response(status_code, body):
    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "application/json",
            "Cache-Control": "no-store",
        },
        "body": json.dumps(body),
    }


def read_json(stream):
    raw = stream.read(65537)
    if len(raw) > 65536:
        raise ValueError("Response exceeds demonstration size limit")
    return json.loads(raw.decode("utf-8"))


def call_unified_api(method, path, body=None, idempotency_key=None):
    base_url = os.environ["UNIFIED_API_BASE_URL"].rstrip("/")
    headers = {
        "Authorization": f"Bearer {get_demo_token()}",
        "Content-Type": "application/json",
    }
    if idempotency_key:
        headers["Idempotency-Key"] = idempotency_key

    data = json.dumps(body).encode() if body is not None else None
    request = Request(
        base_url + path,
        data=data,
        headers=headers,
        method=method,
    )

    try:
        with urlopen(request, timeout=6) as result:
            return response(result.status, read_json(result))
    except HTTPError as error:
        return response(error.code, read_json(error))


def lambda_handler(event, context):
    try:
        route = event.get("routeKey")

        if route == "POST /demo/lookup":
            raw_body = event.get("body", "")
            if not isinstance(raw_body, str) or len(raw_body) > 8192:
                raise ValueError("Invalid request body")

            if event.get("isBase64Encoded"):
                raw_body = base64.b64decode(
                    raw_body, validate=True
                ).decode("utf-8")

            body = json.loads(raw_body)
            if not isinstance(body, dict) or set(body) != {"mode", "component"}:
                raise ValueError("Request must contain only mode and component")

            mode = body["mode"]
            component = body["component"]
            if mode not in ("sync", "async"):
                raise ValueError("mode must be sync or async")
            if component not in ("COMPONENT_A", "COMPONENT_B"):
                raise ValueError("component must be COMPONENT_A or COMPONENT_B")

            unified_body = {
                "merchantId": "merchant-1001",
                "component": component,
            }

            if mode == "sync":
                return call_unified_api(
                    "POST", "/partner-eligibility", unified_body
                )

            headers = {
                name.lower(): value
                for name, value in (event.get("headers") or {}).items()
            }
            key = headers.get("idempotency-key", "")
            if not isinstance(key, str) or not re.fullmatch(
                r"[A-Za-z0-9_-]{1,128}", key
            ):
                raise ValueError("A valid Idempotency-Key is required")

            return call_unified_api(
                "POST", "/eligibility-requests", unified_body, key
            )

        if route == "GET /demo/requests/{requestId}":
            request_id = (event.get("pathParameters") or {}).get("requestId", "")
            if not isinstance(request_id, str) or not re.fullmatch(
                r"req-[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}",
                request_id,
            ):
                raise ValueError("Invalid request ID")

            return call_unified_api(
                "GET", f"/eligibility-requests/{request_id}"
            )

        return response(404, {"code": "NOT_FOUND", "message": "Unknown demo route"})

    except (ValueError, UnicodeError):
        return response(
            400,
            {"code": "INVALID_REQUEST", "message": "Invalid demonstration request"},
        )
    except Exception:
        logger.exception("Demonstration request failed")
        return response(
            502,
            {"code": "DEMO_UNAVAILABLE", "message": "Unable to reach the integration API"},
        )
