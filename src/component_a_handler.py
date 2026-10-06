import base64
import json
import re

from backends import COMPONENT_A_MERCHANTS
from merchant_profiles import COMPONENT_A_PROFILES


def response(status_code, body):
    return {
        "statusCode": status_code,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(body),
    }


def lambda_handler(event, context):
    try:
        raw_body = event.get("body")
        if not isinstance(raw_body, str) or not raw_body:
            raise ValueError("A JSON request body is required")

        if event.get("isBase64Encoded"):
            raw_body = base64.b64decode(
                raw_body, validate=True
            ).decode("utf-8")

        request = json.loads(raw_body)
        if not isinstance(request, dict) or set(request) != {"merchant_id"}:
            raise ValueError("Request must contain only merchant_id")

        merchant_id = request["merchant_id"]
        if (
            not isinstance(merchant_id, str)
            or re.fullmatch(r"[A-Za-z0-9_-]{1,64}", merchant_id) is None
        ):
            raise ValueError("merchant_id has an invalid format")

    except (ValueError, UnicodeError):
        return response(
            400,
            {"code": "INVALID_REQUEST", "message": "Invalid merchant lookup request"},
        )

    if merchant_id not in COMPONENT_A_MERCHANTS:
        return response(
            404,
            {"code": "MERCHANT_NOT_FOUND", "message": "Merchant not found"},
        )

    return response(
        200,
        {
            "merchant_id": merchant_id,
            "status": COMPONENT_A_MERCHANTS[merchant_id],
            **COMPONENT_A_PROFILES[merchant_id],
        },
    )
