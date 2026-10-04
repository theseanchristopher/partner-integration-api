import json
import logging
import os

import boto3
from boto3.dynamodb.types import TypeDeserializer

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def lambda_handler(event, context):
    table_name = os.environ["REQUEST_TABLE_NAME"]
    queue_url = os.environ["PROCESSING_QUEUE_URL"]

    db = boto3.client("dynamodb")
    sqs = boto3.client("sqs")
    deserializer = TypeDeserializer()
    failures = []

    for record in event["Records"]:
        try:
            # Status updates must not create new jobs.
            if record["eventName"] != "INSERT":
                continue

            item = {
                key: deserializer.deserialize(value)
                for key, value in record["dynamodb"]["NewImage"].items()
            }

            # The table also contains idempotency records.
            if item.get("recordType") != "REQUEST":
                continue

            sqs.send_message(
                QueueUrl=queue_url,
                MessageBody=json.dumps({
                    "requestId": item["requestId"]
                }),
            )

            db.update_item(
                TableName=table_name,
                Key={"pk": {"S": item["pk"]}},
                UpdateExpression="SET dispatchStatus = :sent",
                ConditionExpression="attribute_exists(pk)",
                ExpressionAttributeValues={
                    ":sent": {"S": "SENT"}
                },
            )

            logger.info("Forwarded request %s", item["requestId"])

        except Exception:
            logger.exception(
                "Failed to forward stream record %s",
                record.get("eventID"),
            )
            failures.append({
                "itemIdentifier": record["dynamodb"]["SequenceNumber"]
            })

    return {"batchItemFailures": failures}
