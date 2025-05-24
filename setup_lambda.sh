#!/bin/bash

# Configuration
AWS_REGION="ap-northeast-2"
AWS_ACCOUNT_ID="426908610163"
ECR_REPOSITORY="travel-agent-worker"
LAMBDA_FUNCTION_NAME="travel-agent-worker"

# Get ECR login token and login
aws ecr get-login-password --region ${AWS_REGION} | docker login --username AWS --password-stdin ${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com

# Build and tag the Docker image
DOCKER_DEFAULT_PLATFORM=linux/amd64 docker build --platform linux/amd64 --provenance=false -t ${ECR_REPOSITORY} -f Dockerfile.worker .
docker tag ${ECR_REPOSITORY}:latest ${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/${ECR_REPOSITORY}:latest

# Push the image to ECR
docker push ${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/${ECR_REPOSITORY}:latest

# Update Lambda function with new image
aws lambda update-function-code \
    --function-name ${LAMBDA_FUNCTION_NAME} \
    --image-uri ${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/${ECR_REPOSITORY}:latest

# Wait for the update to complete
aws lambda wait function-updated --function-name ${LAMBDA_FUNCTION_NAME}

# Trigger Lambda deployment
aws lambda publish-version --function-name ${LAMBDA_FUNCTION_NAME}

echo "Deployment completed successfully!" 