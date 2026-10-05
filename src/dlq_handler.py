import json
import logging
import os
from datetime import datetime, timezone

import boto3
from boto3.dynamodb.types import TypeDeserializer, TypeSerializer

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def lambda_handler(event, context):
    db = boto3.client("dynamodb")
    table_name = os.environ["REQUEST_TABLE_NAME"]
    serializer = TypeSerializer()
    deserializer = TypeDeserializer()
    failures = []

    def encode(item):
        return {
            key: serializer.serialize(value)
            for key, value in item.items()
        }

    for message in event["Records"]:
        request_id = None

        try:
            body = json.loads(message["body"])
            request_id = body["requestId"]
            if not isinstance(request_id, str) or not request_id:
                raise ValueError("Invalid request ID")

            response = db.get_item(
                TableName=table_name,
                Key={"pk": {"S": f"REQUEST#{request_id}"}},
                ConsistentRead=True,
            )
            record = {
                key: deserializer.deserialize(value)
                for key, value in response.get("Item", {}).items()
            }

            archive = {
                "pk": f"DLQ#{message['messageId']}",
                "recordType": "DLQ_ARCHIVE",
                "requestId": request_id,
                "messageId": message["messageId"],
                "messageBody": message["body"],
                "sourceQueueArn": message["eventSourceARN"],
                "archivedAt": datetime.now(timezone.utc).isoformat(),
            }

            if not record or record["status"] in ("SUCCEEDED", "FAILED"):
                # Preserve existing outcomes; archive the message only.
                db.put_item(
                    TableName=table_name,
                    Item=encode(archive),
                )
                logger.info(
                    "Archived DLQ message without changing request %s",
                    request_id,
                )
                continue

            now = int(datetime.now(timezone.utc).timestamp())
            db.transact_write_items(TransactItems=[
                {
                    "Put": {
                        "TableName": table_name,
                        "Item": encode(archive),
                    }
                },
                {
                    "Update": {
                        "TableName": table_name,
                        "Key": {"pk": {"S": f"REQUEST#{request_id}"}},
                        "UpdateExpression": (
                            "SET #status = :failed, #error = :error "
                            "REMOVE workerToken, leaseUntil"
                        ),
                        "ConditionExpression": (
                            "attribute_exists(pk) AND "
                            "(#status = :pending OR "
                            "(#status = :processing AND leaseUntil <= :now))"
                        ),
                        "ExpressionAttributeNames": {
                            "#status": "status",
                            "#error": "error",
                        },
                        "ExpressionAttributeValues": {
                            ":failed": {"S": "FAILED"},
                            ":pending": {"S": "PENDING"},
                            ":processing": {"S": "PROCESSING"},
                            ":now": {"N": str(now)},
                            ":error": serializer.serialize({
                                "code": "PROCESSING_RETRIES_EXHAUSTED",
                                "message": "Processing retries exhausted",
                            }),
                        },
                    }
                },
            ])

            logger.info(
                "Archived DLQ message and marked request %s FAILED",
                request_id,
            )

        except Exception:
            logger.exception("DLQ handling failed for request %s", request_id)
            failures.append({"itemIdentifier": message["messageId"]})

    return {"batchItemFailures": failures}
