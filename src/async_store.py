import hashlib
import json
import uuid
from datetime import datetime, timezone

import boto3
from boto3.dynamodb.types import TypeDeserializer, TypeSerializer
from botocore.exceptions import ClientError


class IdempotencyConflictError(Exception):
    pass


class AsyncStore:
    def __init__(self, table_name):
        self.table_name = table_name
        self.db = boto3.client("dynamodb")
        self.serializer = TypeSerializer()
        self.deserializer = TypeDeserializer()

    def _encode(self, item):
        return {
            key: self.serializer.serialize(value)
            for key, value in item.items()
        }

    def _get(self, key):
        response = self.db.get_item(
            TableName=self.table_name,
            Key={"pk": {"S": key}},
            ConsistentRead=True,
        )
        item = response.get("Item")
        if item is None:
            return None
        return {
            key: self.deserializer.deserialize(value)
            for key, value in item.items()
        }

    def _duplicate_result(self, record, body_hash):
        if record["bodyHash"] != body_hash:
            raise IdempotencyConflictError(
                "Idempotency key already used with a different body"
            )
        return record["requestId"]

    def create_request(self, client_id, idempotency_key, request):
        canonical_body = json.dumps(
            request, sort_keys=True, separators=(",", ":")
        )
        body_hash = hashlib.sha256(canonical_body.encode()).hexdigest()
        key = f"IDEMPOTENCY#{client_id}#{idempotency_key}"

        existing = self._get(key)
        if existing is not None:
            return self._duplicate_result(existing, body_hash)

        request_id = f"req-{uuid.uuid4()}"
        created_at = datetime.now(timezone.utc).isoformat()

        request_record = {
            "pk": f"REQUEST#{request_id}",
            "recordType": "REQUEST",
            "requestId": request_id,
            "clientId": client_id,
            "merchantId": request["merchantId"],
            "component": request["component"],
            "status": "PENDING",
            "dispatchStatus": "PENDING",
            "createdAt": created_at,
        }
        idempotency_record = {
            "pk": key,
            "recordType": "IDEMPOTENCY",
            "requestId": request_id,
            "bodyHash": body_hash,
            "createdAt": created_at,
        }

        writes = [
            {
                "Put": {
                    "TableName": self.table_name,
                    "Item": self._encode(record),
                    "ConditionExpression": "attribute_not_exists(pk)",
                }
            }
            for record in (request_record, idempotency_record)
        ]

        try:
            self.db.transact_write_items(TransactItems=writes)
        except ClientError as error:
            if error.response["Error"]["Code"] != "TransactionCanceledException":
                raise

            # Another submission may have created this key first.
            existing = self._get(key)
            if existing is None:
                # No committed winner is visible: let the caller retry.
                raise
            return self._duplicate_result(existing, body_hash)

        return request_id

    def get_request(self, client_id, request_id):
        record = self._get(f"REQUEST#{request_id}")
        if record is None or record["clientId"] != client_id:
            return None
        return record
