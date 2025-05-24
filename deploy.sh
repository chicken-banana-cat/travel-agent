SERVICE_NAME="travel-agent-api"
AWS_REGION="ap-northeast-1"
ECR_REPO_NAME="travel-agent"
IMAGE_TAG="latest"

# Get AWS account ID
AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)

# Login to ECR
aws ecr get-login-password --region ${AWS_REGION} | \
    docker login --username AWS --password-stdin ${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com

# Build the Docker image
echo "Building Docker image..."
docker build \
    --platform=linux/amd64 \
    --load \
    --provenance=false \
    -t ${ECR_REPO_NAME}:${IMAGE_TAG} .

# Tag the image
docker tag ${ECR_REPO_NAME}:${IMAGE_TAG} ${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/${ECR_REPO_NAME}:${IMAGE_TAG}

# Delete existing image from ECR if it exists
echo "Cleaning up existing image from ECR..."
aws ecr batch-delete-image --repository-name ${ECR_REPO_NAME} --image-ids imageTag=${IMAGE_TAG} --region ${AWS_REGION} || true

# Push the image to ECR
echo "Pushing image to ECR..."
docker push ${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/${ECR_REPO_NAME}:${IMAGE_TAG}

# Wait for image to be available
echo "Waiting for image to be available..."
sleep 10

echo "Starting new deployment..."
aws apprunner start-deployment \
    --service-arn $(aws apprunner list-services --region ${AWS_REGION} --query "ServiceSummaryList[?ServiceName=='${SERVICE_NAME}'].ServiceArn" --output text) \
    --region ${AWS_REGION}

# Check deployment status
if [ $? -eq 0 ]; then
    echo "✅ Deployment successful!"
    echo "Service URL: $(aws apprunner list-services --region ${AWS_REGION} --query "ServiceSummaryList[?ServiceName=='${SERVICE_NAME}'].ServiceUrl" --output text)"
else
    echo "❌ Deployment failed!"
fi 