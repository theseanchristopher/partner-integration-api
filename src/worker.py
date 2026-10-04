import json
import logging
import os
import uuid

from async_store import AsyncStore
from backends import MerchantNotFoundError
from service import check_eligibility, InvalidRequestError

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def lambda_handler(event, context):
    store = AsyncStore(os.environ["REQUEST_TABLE_NAME"])
    failures = []

    for message in event["Records"]:
        request_id = None
        worker_token = str(uuid.uuid4())
        claimed = False

        try:
            body = json.loads(message["body"])
            request_id = body["requestId"]
            if not isinstance(request_id, str) or not request_id:
                raise ValueError("Invalid request ID in queue message")

            record = store.claim_request(request_id, worker_token)
            if record is None:
                logger.info("Skipped completed request %s", request_id)
                continue

            claimed = True
            request = {
                "merchantId": record["merchantId"],
                "component": record["component"],
            }

            try:
                result = check_eligibility(request)
            except MerchantNotFoundError:
                store.complete_request(
                    request_id,
                    worker_token,
                    error={
                        "code": "MERCHANT_NOT_FOUND",
                        "message": "Merchant not found in selected component",
                    },
                )
            except InvalidRequestError:
                store.complete_request(
                    request_id,
                    worker_token,
                    error={
                        "code": "INVALID_REQUEST",
                        "message": "Stored request is invalid",
                    },
                )
            else:
                store.complete_request(
                    request_id, worker_token, result=result
                )

            logger.info("Recorded outcome for request %s", request_id)

        except Exception:
            logger.exception("Processing failed for request %s", request_id)

            if claimed:
                try:
                    store.release_request(request_id, worker_token)
                except Exception:
                    logger.exception(
                        "Could not release claim for request %s", request_id
                    )

            failures.append({"itemIdentifier": message["messageId"]})

    return {"batchItemFailures": failures}
