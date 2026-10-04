import base64
import json
import subprocess
import urllib.parse
import urllib.request

def aws_json(*args):
    return json.loads(subprocess.check_output(
        ["aws", *args, "--region", "us-east-1",
         "--output", "json", "--no-cli-pager"],
        text=True
    ))

stack = aws_json(
    "cloudformation", "describe-stacks",
    "--stack-name", "partner-api-auth"
)
outputs = {
    item["OutputKey"]: item["OutputValue"]
    for item in stack["Stacks"][0]["Outputs"]
}

client = aws_json(
    "cognito-idp", "describe-user-pool-client",
    "--user-pool-id", outputs["UserPoolId"],
    "--client-id", outputs["ClientId"]
)["UserPoolClient"]

credentials = base64.b64encode(
    f'{outputs["ClientId"]}:{client["ClientSecret"]}'.encode()
).decode()

request = urllib.request.Request(
    outputs["TokenUrl"],
    data=urllib.parse.urlencode({
        "grant_type": "client_credentials",
        "scope": outputs["RequiredScope"]
    }).encode(),
    headers={
        "Authorization": f"Basic {credentials}",
        "Content-Type": "application/x-www-form-urlencoded"
    },
    method="POST"
)

with urllib.request.urlopen(request, timeout=20) as response:
    print(json.load(response)["access_token"])
