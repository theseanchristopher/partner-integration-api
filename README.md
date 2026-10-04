# Partner Integration API

Proof of concept demonstrating an authenticated, unified integration API across two simulated backend systems.

External clients use one request and response format. The service routes each request to COMPONENT_A or COMPONENT_B and maps that component's data into the unified response.

## Implemented
- OpenAPI contracts for the unified API and both components
- Synchronous eligibility lookup
- Request validation, component routing, and data transformation
- Cognito OAuth 2.0 client credentials authentication
- API Gateway JWT validation and required scope enforcement
- Application authorization by client, merchant, and component
- CloudFormation stacks for authentication, deployment storage, and API service
- CloudWatch API access logs and Lambda execution logs
- Deployment script verified against existing stacks
- Cleanup and recreation verified, including authenticated API access

## Planned
- Asynchronous processing with SQS
- Idempotency, retries, and dead-letter queues
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
- The required OAuth scope is partner-api/eligibility.read.
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
| contracts/unified-api.yaml | External API contract |
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

The script packages the Python modules, deploys the authentication and artifact stacks, uploads the ZIP, and deploys the service stack.

Stack outputs supply the Cognito IDs and bucket name automatically.
A hash-based S3 object key allows CloudFormation to detect package changes.

The default region is us-east-1. Override it with AWS_REGION if needed.

## Cleanup

Run from the project root:

```bash
bash scripts/cleanup.sh
```

The script deletes the service stack, authentication stack, and artifact stack.
It empties the deployment bucket before deleting that stack.

Cleanup removes the API endpoint, Cognito client, uploaded packages, and project log groups. Local files and the Git repository remain intact.

The current cleanup script expects the artifact stack to exist.
A complete deletion and recreation cycle has been verified, followed by successful authenticated API access.

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

API access logs contain request IDs, HTTP status codes, latency, and integration errors.
Lambda logs contain execution reports and application errors.
Both log groups have seven-day retention.

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
