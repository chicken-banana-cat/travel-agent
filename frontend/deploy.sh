#!/bin/bash

# Build the project
echo "Building the project..."
npm run build

# Use existing bucket name
BUCKET_NAME="travel-agent-frontend"

# Check if bucket exists
if ! aws s3api head-bucket --bucket $BUCKET_NAME 2>/dev/null; then
    echo "Creating S3 bucket..."
    aws s3api create-bucket \
        --bucket $BUCKET_NAME \
        --region ap-northeast-2 \
        --create-bucket-configuration LocationConstraint=ap-northeast-2

    # Enable static website hosting
    aws s3api put-bucket-website \
        --bucket $BUCKET_NAME \
        --website-configuration '{
            "IndexDocument": {"Suffix": "index.html"},
            "ErrorDocument": {"Key": "index.html"}
        }'

    # Add bucket policy for public access
    aws s3api put-bucket-policy \
        --bucket $BUCKET_NAME \
        --policy '{
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Sid": "PublicReadGetObject",
                    "Effect": "Allow",
                    "Principal": "*",
                    "Action": "s3:GetObject",
                    "Resource": "arn:aws:s3:::'$BUCKET_NAME'/*"
                }
            ]
        }'
fi

# Upload files
echo "Uploading files to S3..."
aws s3 sync dist/ s3://$BUCKET_NAME/ --delete

# Check if CloudFront distribution exists
DISTRIBUTION_ID='E1534QXOKU44H0'

# Get CloudFront domain
CLOUDFRONT_DOMAIN=$(aws cloudfront get-distribution --id $DISTRIBUTION_ID --query 'Distribution.DomainName' --output text)
aws cloudfront create-invalidation --distribution-id $DISTRIBUTION_ID --paths "/*"
echo "Deployment complete!"
echo "Your app is available at: https://$CLOUDFRONT_DOMAIN"
echo "S3 Bucket: $BUCKET_NAME"
echo "CloudFront Distribution ID: $DISTRIBUTION_ID" 