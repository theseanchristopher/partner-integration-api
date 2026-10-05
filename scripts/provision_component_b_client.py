import json
from pathlib import Path

import boto3

parameter_name = "/partner-api/component-b/mtls-client"
folder = Path(__file__).resolve().parents[1] / ".local" / "mtls"

value = json.dumps({
    "certificate": (folder / "client.crt").read_text(),
    "privateKey": (folder / "client.key").read_text(),
})

if len(value.encode("utf-8")) > 4096:
    raise SystemExit("Client credentials exceed the standard parameter size limit")

result = boto3.client("ssm", region_name="us-east-1").put_parameter(
    Name=parameter_name,
    Description="Client credentials for Component B mutual TLS",
    Type="SecureString",
    KeyId="alias/aws/ssm",
    Tier="Standard",
    Value=value,
    Overwrite=False,
)

print("Stored:", parameter_name)
print("Version:", result["Version"])
