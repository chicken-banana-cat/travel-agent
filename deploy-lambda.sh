#!/bin/bash

FUNCTION_NAME="travel-agent-worker"
AWS_REGION="ap-northeast-2"

echo "Creating deployment package..."
zip -r function.zip lambda_function.py travel_agent/

echo "Updating Lambda function..."
aws lambda update-function-code \
    --function-name $FUNCTION_NAME \
    --zip-file fileb://function.zip \
    --region $AWS_REGION

# Clean up
rm function.zip

echo "✅ Deployment completed!" 