#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."
REGION="${AWS_REGION:-us-east-1}"

echo "Checking AWS access..."
aws sts get-caller-identity --region "$REGION" --no-cli-pager

CODE_BUCKET=$(aws cloudformation describe-stacks \
  --stack-name partner-api-artifacts \
  --query "Stacks[0].Outputs[?OutputKey=='CodeBucket'].OutputValue | [0]" \
  --output text \
  --region "$REGION" \
  --no-cli-pager)

case "$CODE_BUCKET" in
  partner-api-artifacts-deploymentbucket-*) ;;
  *)
    echo "Unexpected deployment bucket: $CODE_BUCKET" >&2
    exit 1
    ;;
esac

echo "Deleting asynchronous resources..."
aws cloudformation delete-stack \
  --stack-name partner-api-async \
  --region "$REGION" \
  --no-cli-pager

aws cloudformation wait stack-delete-complete \
  --stack-name partner-api-async \
  --region "$REGION"

echo "Deleting API service..."
aws cloudformation delete-stack \
  --stack-name partner-api-service \
  --region "$REGION" \
  --no-cli-pager

aws cloudformation wait stack-delete-complete \
  --stack-name partner-api-service \
  --region "$REGION"

echo "Deleting component endpoints..."
aws cloudformation delete-stack \
  --stack-name partner-api-components \
  --region "$REGION" \
  --no-cli-pager

aws cloudformation wait stack-delete-complete \
  --stack-name partner-api-components \
  --region "$REGION"

echo "Deleting authentication..."
aws cloudformation delete-stack \
  --stack-name partner-api-auth \
  --region "$REGION" \
  --no-cli-pager

aws cloudformation wait stack-delete-complete \
  --stack-name partner-api-auth \
  --region "$REGION"

echo "Emptying deployment bucket..."
aws s3 rm "s3://${CODE_BUCKET}" \
  --recursive \
  --region "$REGION" \
  --no-cli-pager

echo "Deleting artifact storage..."
aws cloudformation delete-stack \
  --stack-name partner-api-artifacts \
  --region "$REGION" \
  --no-cli-pager

aws cloudformation wait stack-delete-complete \
  --stack-name partner-api-artifacts \
  --region "$REGION"

echo "Project AWS resources deleted."
