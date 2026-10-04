#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."
REGION="${AWS_REGION:-us-east-1}"

stack_output() {
  local value
  value=$(aws cloudformation describe-stacks \
    --stack-name "$1" \
    --query "Stacks[0].Outputs[?OutputKey=='$2'].OutputValue | [0]" \
    --output text \
    --region "$REGION" \
    --no-cli-pager)

  if [[ -z "$value" || "$value" == "None" ]]; then
    echo "Missing output $2 from stack $1" >&2
    return 1
  fi
  printf '%s' "$value"
}

echo "Checking AWS access..."
aws sts get-caller-identity --region "$REGION" --no-cli-pager

echo "Packaging Lambda..."
mkdir -p build

python - <<'PY'
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED

files = sorted(Path("src").glob("*.py"))
if not files:
    raise SystemExit("No Python files found in src")

with ZipFile("build/partner-api.zip", "w", ZIP_DEFLATED) as package:
    for source in files:
        package.write(source, arcname=source.name)

print("Created build/partner-api.zip")
PY

echo "Deploying authentication..."
aws cloudformation deploy \
  --template-file infrastructure/auth.yaml \
  --stack-name partner-api-auth \
  --no-fail-on-empty-changeset \
  --region "$REGION" \
  --no-cli-pager

echo "Deploying artifact storage..."
aws cloudformation deploy \
  --template-file infrastructure/artifacts.yaml \
  --stack-name partner-api-artifacts \
  --no-fail-on-empty-changeset \
  --region "$REGION" \
  --no-cli-pager

CODE_BUCKET=$(stack_output partner-api-artifacts CodeBucket)
USER_POOL_ID=$(stack_output partner-api-auth UserPoolId)
PARTNER_CLIENT_ID=$(stack_output partner-api-auth ClientId)

PACKAGE_HASH=$(python - <<'PY'
import hashlib
from pathlib import Path
print(hashlib.sha256(Path("build/partner-api.zip").read_bytes()).hexdigest())
PY
)
CODE_KEY="lambda/partner-api-${PACKAGE_HASH}.zip"

echo "Uploading Lambda package..."
aws s3 cp build/partner-api.zip \
  "s3://${CODE_BUCKET}/${CODE_KEY}" \
  --region "$REGION" \
  --no-cli-pager

echo "Deploying API service..."
aws cloudformation deploy \
  --template-file infrastructure/service.yaml \
  --stack-name partner-api-service \
  --parameter-overrides \
    UserPoolId="$USER_POOL_ID" \
    PartnerClientId="$PARTNER_CLIENT_ID" \
    CodeBucket="$CODE_BUCKET" \
    CodeKey="$CODE_KEY" \
  --capabilities CAPABILITY_IAM \
  --no-fail-on-empty-changeset \
  --region "$REGION" \
  --no-cli-pager

API_ID=$(stack_output partner-api-service ApiId)
JWT_AUTHORIZER_ID=$(stack_output partner-api-service JwtAuthorizerId)

echo "Deploying asynchronous resources..."
aws cloudformation deploy \
  --template-file infrastructure/async.yaml \
  --stack-name partner-api-async \
  --parameter-overrides \
    CodeBucket="$CODE_BUCKET" \
    CodeKey="$CODE_KEY" \
    ApiId="$API_ID" \
    JwtAuthorizerId="$JWT_AUTHORIZER_ID" \
    PartnerClientId="$PARTNER_CLIENT_ID" \
  --capabilities CAPABILITY_IAM \
  --no-fail-on-empty-changeset \
  --region "$REGION" \
  --no-cli-pager

echo "Deployment complete. API endpoint:"
stack_output partner-api-service EligibilityUrl
printf '\n'
