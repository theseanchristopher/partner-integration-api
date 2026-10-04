# Partner Integration API

Proof of concept demonstrating an authenticated, unified integration API across two simulated backend systems.

External clients use one request and response format. The service routes each request to COMPONENT_A or COMPONENT_B and maps that component's data into the unified response.

## Implemented
- OpenAPI contracts for the unified API and both components
- Synchronous eligibility lookup
- Asynchronous submission and status lookup
- DynamoDB request storage and atomic idempotency records
- Stream dispatcher and SQS worker with expiring processing claims
- Retry configuration and separate dispatch/processing failure queues
- Request validation, component routing, and data transformation
- Cognito OAuth 2.0 client credentials authentication
- API Gateway JWT validation and required scope enforcement
- Application authorization by client, merchant, and component
- CloudFormation stacks for authentication, deployment storage, synchronous service, and asynchronous processing
- CloudWatch API access logs and Lambda execution logs
- Deployment script verified against existing stacks
- Synchronous cleanup/recreation verified; scripts extended to manage asynchronous resources

## Planned
- Controlled failure testing, DLQ recovery, and safe replay
- Recovery of requests that remain pending after forwarding failures
- Webhook notifications and delivery failure handling
- Separate HTTP endpoints for simulated components

## Current backend scope
COMPONENT_A and COMPONENT_B are Python simulations inside the Lambda package.
The deployed API does not yet make HTTP requests to separate backend services.

## Local environment
```bash
conda activate partner-api
```

## AWS region
us-east-1

## Synchronous request flow

1. The external client authenticates with Cognito using its client ID and secret to obtain an access token.
2. The client sends POST /partner-eligibility with the token in the Authorization: Bearer header and a JSON request body.
3. API Gateway validates the JWT's signature, issuer, intended client, expiry, and required scope.
4. API Gateway invokes Lambda with the request body and validated token claims.
5. Lambda validates the request and checks whether the client may access the requested merchant and component.
6. The service maps the unified request into the selected component's format.
7. The simulated component returns its result.
8. The service maps that result into the unified response format.
9. Lambda returns an HTTP response through API Gateway to the client.

## Authentication and authorization

- Authentication identifies the calling client through Cognito and API Gateway JWT validation.
- Synchronous lookup and asynchronous status lookup require partner-api/eligibility.read.
- Asynchronous submission requires partner-api/eligibility.submit.
- Application authorization restricts each client to configured merchants and components.
- The demonstration client currently has access to merchant-1001 in COMPONENT_A and COMPONENT_B.
- Client secrets and access tokens must not be committed to the repository.

## Component mappings

The unified request contains merchantId and component.
The selected component determines which request and response mapping is used.

| Field | Unified API | COMPONENT_A | COMPONENT_B |
|---|---|---|---|
| Merchant identifier | merchantId | merchant_id | accountReference |
| Eligibility indicator | eligible: true or false | status: A or I | enabled: true or false |
| Normalized status | ACTIVE or INACTIVE | A maps to ACTIVE; I maps to INACTIVE | true maps to ACTIVE; false maps to INACTIVE |

An inactive merchant is a valid lookup result: HTTP 200 with eligible: false and status: INACTIVE.

## Source files

| File | Responsibility |
|---|---|
| contracts/unified-api.yaml | Synchronous API contract |
| contracts/async-api.yaml | Asynchronous submission and status contract |
| src/async_handler.py | Asynchronous HTTP submission and status lookup |
| src/async_store.py | Request storage, idempotency, and worker claims |
| src/dispatcher.py | Forward new request records to SQS |
| src/worker.py | Process queued requests and save outcomes |
| infrastructure/async.yaml | DynamoDB, queues, asynchronous Lambdas, and API routes |
| scripts/get_token.py | Operator helper for obtaining an access token |
| src/handler.py | API Gateway event parsing and HTTP responses |
| src/authorization.py | Client access checks for merchants and components |
| src/service.py | Request validation and component orchestration |
| src/mappings.py | Component request and response transformations |
| src/backends.py | Simulated component behavior and merchant records |
| infrastructure/auth.yaml | Cognito resources |
| infrastructure/artifacts.yaml | Private deployment package bucket |
| infrastructure/service.yaml | API Gateway, Lambda, IAM role, and log groups |
| scripts/deploy.sh | Package and deploy the proof of concept |
| scripts/cleanup.sh | Delete the proof of concept's AWS resources |

## Deployment

Prerequisites:
- Python 3.12; activate the partner-api environment
- AWS CLI with credentials for the target account
- Permissions to create the resources defined in the templates

Run from the project root:

```bash
bash scripts/deploy.sh
```

The script packages the Python modules, deploys the authentication and artifact stacks, uploads the ZIP, then deploys the service and asynchronous stacks.

Stack outputs supply the Cognito IDs and bucket name automatically.
A hash-based S3 object key allows CloudFormation to detect package changes.

The default region is us-east-1. Override it with AWS_REGION if needed.

## Cleanup

Run from the project root:

```bash
bash scripts/cleanup.sh
```

The script deletes the asynchronous stack first, followed by the service, authentication, and artifact stacks.
It empties the deployment bucket before deleting that stack.

Cleanup removes the API endpoint, Cognito client, DynamoDB records, queues and their messages, uploaded packages, and project log groups. Local files and the Git repository remain intact.

The current cleanup script expects the artifact stack to exist.
Deletion and recreation were verified for the synchronous deployment. A full cycle with the new asynchronous resources remains to be tested.

After recreation, retrieve the new endpoint and authentication outputs and obtain a new access token.

## Verified live behavior

| Scenario | Expected HTTP status | Verified |
|---|---|---|
| Missing access token | 401 | Yes |
| Authorized merchant through COMPONENT_A | 200 | Yes |
| Authorized merchant through COMPONENT_B | 200 | Yes |
| Merchant outside the client's access configuration | 403 | Yes |
| Invalid component value | 400 | Yes |

## Observability

CloudWatch log groups:
- /partner-api/partner-api-service/access
- /aws/lambda/partner-api-service-eligibility
- /aws/lambda/partner-api-async-api
- /aws/lambda/partner-api-async-dispatcher
- /aws/lambda/partner-api-async-worker

API access logs contain request IDs, HTTP status codes, latency, and integration errors.
Lambda logs contain execution reports and application errors.
All listed log groups have seven-day retention.

```bash
aws logs tail /partner-api/partner-api-service/access \
  --since 15m --region us-east-1 --no-cli-pager

aws logs tail /aws/lambda/partner-api-service-eligibility \
  --since 15m --region us-east-1 --no-cli-pager
```

## Obtain an access token

The helper retrieves the current Cognito client credentials using the operator's AWS permissions and requests an access token.

```bash
ACCESS_TOKEN=$(python scripts/get_token.py)
```

Capture the output as shown; running the helper directly displays the token.
External partners would use their securely provisioned credentials rather than retrieve them through our AWS account.

## Asynchronous request flow

1. The client submits POST /eligibility-requests with an access token, an Idempotency-Key header, and merchant/component details.
2. API Gateway validates the token and submission scope.
3. The API Lambda validates the body and checks merchant/component access.
4. A DynamoDB transaction creates the request and idempotency records together.
5. The API returns 202 with the request ID and status URL.
6. DynamoDB Streams captures the new request record.
7. The dispatcher sends its request ID to SQS and records dispatch status SENT.
8. The worker receives the message and atomically claims the request.
9. The worker calls the simulated component and records the result or terminal error.
10. Lambda's SQS integration deletes successfully handled messages.
11. The client calls GET /eligibility-requests/{requestId} to retrieve status and results.

Forwarding and processing can run before the client receives the 202 response.

Processing states are PENDING, PROCESSING, SUCCEEDED, and FAILED.
An inactive merchant is a successful lookup with eligible: false.
The status endpoint returns HTTP 200 when it retrieves a record, even when that record has processing status FAILED.

## Idempotency and duplicate protection

- Idempotency keys are scoped to the authenticated client.
- The same key and request body return the original request ID.
- The same key with a different body returns 409.
- A request-body hash compares parsed content rather than JSON formatting.
- Conditional transactional writes protect against concurrent duplicate submissions.
- Worker claims expire after 90 seconds; the worker timeout is 30 seconds.
- An already completed request is skipped on duplicate queue delivery.
- Idempotency records currently remain until the table is deleted; no expiration policy is implemented.

## Verified asynchronous behavior

| Scenario | Verified result |
|---|---|
| Authenticated submission | HTTP 202 with request ID and status URL |
| Status lookup after processing | HTTP 200 with SUCCEEDED and eligibility result |
| Duplicate submission with identical body | Original request ID returned |
| Same key with changed body | HTTP 409 |
| Unauthorized merchant submission | HTTP 403 |
| Duplicate SQS delivery after completion | Worker skips lookup; message removed |
| Local cross-client record lookup | Another client's request is not returned |

## Failure handling and remaining work

- The dispatcher has a stream failure destination, DispatchFailureQueue.
- ProcessingQueue has a separate ProcessingDLQ for exhausted message deliveries.
- Unexpected worker errors release the claim and report the message for retry.
- Merchant-not-found is a terminal business error: the worker saves FAILED and acknowledges the message.
- Failure queues and retry settings are configured; controlled failure/recovery testing remains.
- Requests reaching ProcessingDLQ are not yet automatically updated to FAILED.
- DispatchFailureQueue contains stream failure metadata; saved requests remain in DynamoDB.
- Pending-request reconciliation, alarms, and safe replay tooling remain to be implemented.
- Worker claims protect concurrent processing but do not guarantee exactly-once external side effects after a crash.
- Webhook notification is not yet implemented.

## Local SDK dependency

Local DynamoDB helpers require Boto3:

```bash
python -m pip install boto3
```
