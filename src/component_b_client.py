import json
import os
import ssl
import tempfile
import time
from pathlib import Path
from urllib.request import Request, urlopen

import boto3
from botocore.config import Config


_cached_context = None
_cached_parameter = None
_cache_expires = 0


def get_tls_context(parameter_name):
    global _cached_context, _cached_parameter, _cache_expires

    if (
        _cached_context is not None
        and _cached_parameter == parameter_name
        and time.monotonic() < _cache_expires
    ):
        return _cached_context

    region = os.environ.get("AWS_REGION", "us-east-1")
    ssm = boto3.client(
        "ssm",
        region_name=region,
        config=Config(
            connect_timeout=2,
            read_timeout=2,
            retries={"total_max_attempts": 1},
        ),
    )
    result = ssm.get_parameter(
        Name=parameter_name,
        WithDecryption=True,
    )
    credentials = json.loads(result["Parameter"]["Value"])

    if not isinstance(credentials, dict):
        raise ValueError("Invalid client credential configuration")
    for field in ("certificate", "privateKey"):
        if not isinstance(credentials.get(field), str) or not credentials[field]:
            raise ValueError("Missing client credential field")

    context = ssl.create_default_context()

    with tempfile.TemporaryDirectory(prefix="component-b-", dir="/tmp") as folder:
        certificate_path = Path(folder) / "client.crt"
        key_path = Path(folder) / "client.key"

        for path, field in (
            (certificate_path, "certificate"),
            (key_path, "privateKey"),
        ):
            with open(path, "x", opener=lambda name, flags: os.open(name, flags, 0o600)) as output:
                output.write(credentials[field])

        context.load_cert_chain(
            certfile=str(certificate_path),
            keyfile=str(key_path),
        )

    _cached_context = context
    _cached_parameter = parameter_name
    _cache_expires = time.monotonic() + 300
    return context


def call_component_b_http(request):
    url = os.environ.get("COMPONENT_B_URL")
    parameter_name = os.environ.get("COMPONENT_B_CLIENT_PARAMETER")
    if not url or not parameter_name:
        raise ValueError("Component B connection is not configured")

    context = get_tls_context(parameter_name)
    body = json.dumps(request).encode("utf-8")
    http_request = Request(
        url=url,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    with urlopen(http_request, context=context, timeout=3) as result:
        if result.status != 200:
            raise ValueError("Unexpected Component B response status")
        return json.loads(result.read().decode("utf-8"))
