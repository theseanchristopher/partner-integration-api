import json
import os
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import boto3
from botocore.exceptions import BotoCoreError, ClientError

from component_b_client import call_component_b_http
from botocore.auth import SigV4Auth
from botocore.awsrequest import AWSRequest


class MerchantNotFoundError(Exception):
    pass


class ComponentConnectionError(Exception):
    pass


COMPONENT_A_MERCHANTS = {
    "merchant-1001": "A",
    "merchant-1002": "I",
}

COMPONENT_B_ACCOUNTS = {
    "merchant-1001": True,
    "merchant-1002": False,
}


def call_component_a(request):
    url = os.environ.get("COMPONENT_A_URL")
    if not url:
        raise ComponentConnectionError("Component A endpoint is not configured")

    session = boto3.Session()
    region = session.region_name or os.environ.get("AWS_REGION", "us-east-1")
    credentials = session.get_credentials()
    if credentials is None:
        raise ComponentConnectionError("AWS credentials are unavailable")

    body = json.dumps(request).encode("utf-8")
    signed_request = AWSRequest(
        method="POST",
        url=url,
        data=body,
        headers={"Content-Type": "application/json"},
    )
    SigV4Auth(
        credentials.get_frozen_credentials(), "execute-api", region
    ).add_auth(signed_request)

    http_request = Request(
        url=url,
        data=body,
        headers=dict(signed_request.headers.items()),
        method="POST",
    )

    try:
        with urlopen(http_request, timeout=3) as result:
            if result.status != 200:
                raise ComponentConnectionError(
                    "Unexpected Component A response status"
                )
            return json.loads(result.read().decode("utf-8"))
    except HTTPError as error:
        if error.code == 404:
            raise MerchantNotFoundError(
                "Merchant not found in Component A"
            ) from error
        raise ComponentConnectionError(
            f"Component A returned HTTP {error.code}"
        ) from error
    except (URLError, TimeoutError, ValueError, UnicodeError) as error:
        raise ComponentConnectionError(
            "Component A call failed or returned invalid JSON"
        ) from error


def call_component_b(request):
    try:
        return call_component_b_http(request)
    except HTTPError as error:
        if error.code == 404:
            raise MerchantNotFoundError(
                "Merchant not found in Component B"
            ) from error
        raise ComponentConnectionError(
            f"Component B returned HTTP {error.code}"
        ) from error
    except (BotoCoreError, ClientError, OSError, ValueError) as error:
        raise ComponentConnectionError(
            "Component B connection or credential loading failed"
        ) from error
