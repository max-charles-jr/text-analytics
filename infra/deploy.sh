#!/usr/bin/env bash
# Build, push, and deploy the CLD-410 text-analytics Django app to the
# ECS Fargate service that was provisioned via the AWS CLI (cluster, ALB,
# target group, security groups, IAM roles, log group -- see the SWDD
# Section 7 for the full list of resources and their ARNs).
#
# Run this from your real Mac terminal (needs Docker Desktop + AWS CLI
# with your `mcharles` credentials configured). Run it from the
# cld410-text-analytics/ directory, or set PROJECT_DIR below.
set -euo pipefail

ACCOUNT_ID=638039899567
REGION=us-east-1
REPO_NAME=cld410-textlab
CLUSTER_NAME=cld410-textlab-clustercld-mc-ta
SERVICE_NAME=cld410-textlab-service
TASK_FAMILY=cld410-textlab
SUBNETS="subnet-06c7d870262a6727c,subnet-005c9cc21ff728e40"
TASK_SG=sg-0d977e6a52d65ca72
TARGET_GROUP_ARN="arn:aws:elasticloadbalancing:us-east-1:638039899567:targetgroup/cld-mc-ta-tg/d23c707225ba84a7"
CONTAINER_NAME=textlab
CONTAINER_PORT=8000

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
APP_DIR="$PROJECT_DIR/app"
INFRA_DIR="$PROJECT_DIR/infra"
REPO_URI="${ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com/${REPO_NAME}"
TAG="$(date +%Y%m%d-%H%M%S)"

echo "==> One-time: create a Django secret key in SSM Parameter Store (skip if it already exists)"
aws ssm get-parameter --name /cld410-textlabcld-mc-ta/django-secret-key --region "$REGION" >/dev/null 2>&1 || \
  aws ssm put-parameter --name /cld410-textlabcld-mc-ta/django-secret-key --type SecureString \
    --value "$(python3 -c 'import secrets; print(secrets.token_urlsafe(50))')" --region "$REGION"

echo "==> Building image"
docker build -t "${REPO_NAME}:${TAG}" "$APP_DIR"
docker tag "${REPO_NAME}:${TAG}" "${REPO_URI}:${TAG}"
docker tag "${REPO_NAME}:${TAG}" "${REPO_URI}:latest"

echo "==> Logging in to ECR and pushing"
aws ecr get-login-password --region "$REGION" | docker login --username AWS --password-stdin "${ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com"
docker push "${REPO_URI}:${TAG}"
docker push "${REPO_URI}:latest"

echo "==> Registering task definition revision (image pinned to this build's tag, not :latest)"
sed "s#__IMAGE_URI__#${REPO_URI}:${TAG}#" "$INFRA_DIR/task-def.template.json" > /tmp/cld410-task-def.json
aws ecs register-task-definition --cli-input-json file:///tmp/cld410-task-def.json --region "$REGION"

echo "==> Creating or updating the ECS service"
if aws ecs describe-services --cluster "$CLUSTER_NAME" --services "$SERVICE_NAME" --region "$REGION" \
    --query "services[?status=='ACTIVE'] | length(@)" --output text | grep -q '^1$'; then
  aws ecs update-service --cluster "$CLUSTER_NAME" --service "$SERVICE_NAME" \
    --task-definition "$TASK_FAMILY" --force-new-deployment --region "$REGION"
else
  aws ecs create-service --cluster "$CLUSTER_NAME" --service-name "$SERVICE_NAME" \
    --task-definition "$TASK_FAMILY" --desired-count 1 --launch-type FARGATE \
    --network-configuration "awsvpcConfiguration={subnets=[${SUBNETS}],securityGroups=[${TASK_SG}],assignPublicIp=ENABLED}" \
    --load-balancers "targetGroupArn=${TARGET_GROUP_ARN},containerName=${CONTAINER_NAME},containerPort=${CONTAINER_PORT}" \
    --region "$REGION"
fi

echo "==> Waiting for the service to stabilize (this can take a few minutes)"
aws ecs wait services-stable --cluster "$CLUSTER_NAME" --services "$SERVICE_NAME" --region "$REGION"

echo "==> Done. App URL:"
aws elbv2 describe-load-balancers --names cld-mc-ta-alb --region "$REGION" \
  --query 'LoadBalancers[0].DNSName' --output text
