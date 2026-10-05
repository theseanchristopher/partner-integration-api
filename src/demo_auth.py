import base64
import json
import os
import time
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import boto3
from botocore.config import Config


_cached_token = None
_token_expires = 0


def get_demo_token():
    global _cached_token, _token_expires

    if _cached_token and time.monotonic() < _token_expires:
        return _cached_token

    client_id = os.environ["PARTNER_CLIENT_ID"]
    user_pool_id = os.environ["USER_POOL_ID"]
    token_url = os.environ["TOKEN_URL"]

    cognito = boto3.client(
        "cognito-idp",
        config=Config(
            connect_timeout=2,
            read_timeout=2,
            retries={"total_max_attempts": 1},
        ),
    )
    client = cognito.describe_user_pool_client(
        UserPoolId=user_pool_id,
        ClientId=client_id,
    )["UserPoolClient"]

    credentials = base64.b64encode(
        f'{client_id}:{client["ClientSecret"]}'.encode()
    ).decode()

    request = Request(
        token_url,
        data=urlencode({
            "grant_type": "client_credentials",
            "scope": (
                "partner-api/eligibility.read "
                "partner-api/eligibility.submit"
            ),
        }).encode(),
        headers={
            "Authorization": f"Basic {credentials}",
            "Content-Type": "application/x-www-form-urlencoded",
        },
        method="POST",
    )

    with urlopen(request, timeout=3) as response:
        result = json.load(response)

    token = result["access_token"]
    lifetime = int(result["expires_in"])
    if not isinstance(token, str) or not token or lifetime <= 0:
        raise ValueError("Invalid token response")

    _cached_token = token
    _token_expires = time.monotonic() + max(0, lifetime - 60)
    return token
