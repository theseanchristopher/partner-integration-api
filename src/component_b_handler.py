import base64
import json
import re

from backends import COMPONENT_B_ACCOUNTS
from merchant_profiles import COMPONENT_B_PROFILES


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
        if not isinstance(request, dict) or set(request) != {"accountReference"}:
            raise ValueError("Request must contain only accountReference")

        account_reference = request["accountReference"]
        if (
            not isinstance(account_reference, str)
            or re.fullmatch(r"[A-Za-z0-9_-]{1,64}", account_reference) is None
        ):
            raise ValueError("accountReference has an invalid format")

    except (ValueError, UnicodeError):
        return response(
            400,
            {"code": "INVALID_REQUEST", "message": "Invalid account lookup request"},
        )

    if account_reference not in COMPONENT_B_ACCOUNTS:
        return response(
            404,
            {"code": "MERCHANT_NOT_FOUND", "message": "Account not found"},
        )

    return response(
        200,
        {
            "accountReference": account_reference,
            "enabled": COMPONENT_B_ACCOUNTS[account_reference],
            **COMPONENT_B_PROFILES[account_reference],
        },
    )
