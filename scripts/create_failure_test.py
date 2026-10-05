import argparse
import os
import uuid
from datetime import datetime, timezone

import boto3

parser = argparse.ArgumentParser()
parser.add_argument("--fail-attempts", type=int, default=1)
args = parser.parse_args()
if args.fail_attempts < 0:
    parser.error("--fail-attempts must be nonnegative")

region = os.environ.get("AWS_REGION", "us-east-1")
cf = boto3.client("cloudformation", region_name=region)
stack = cf.describe_stacks(StackName="partner-api-async")["Stacks"][0]
outputs = {
    item["OutputKey"]: item["OutputValue"]
    for item in stack["Outputs"]
}

table = boto3.resource("dynamodb", region_name=region).Table(
    outputs["RequestTableName"]
)
request_id = f"req-{uuid.uuid4()}"

table.put_item(
    Item={
        "pk": f"REQUEST#{request_id}",
        "recordType": "REQUEST",
        "requestId": request_id,
        "clientId": "internal-failure-test",
        "merchantId": "merchant-1001",
        "component": "COMPONENT_A",
        "status": "PENDING",
        "dispatchStatus": "PENDING",
        "testFailAttempts": args.fail_attempts,
        "createdAt": datetime.now(timezone.utc).isoformat(),
    },
    ConditionExpression="attribute_not_exists(pk)",
)

print(request_id)
