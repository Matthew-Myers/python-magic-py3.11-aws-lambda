#!/bin/bash

# CSV Validator Lambda Deployment Script

set -e

STAGE=${1:-dev}

echo "🚀 Deploying CSV Validator Lambda to $STAGE..."

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo "❌ Docker is not running. Please start Docker first."
    exit 1
fi

# Check if AWS CLI is configured
if ! aws sts get-caller-identity > /dev/null 2>&1; then
    echo "❌ AWS CLI not configured. Please run 'aws configure' first."
    exit 1
fi

# Check if layer exists, if not build and deploy it
if [ ! -f "layer_info.json" ]; then
    echo "🏗️  Building Lambda Layer (first time setup)..."
    ./build_layer.sh
    echo "🚀 Deploying Lambda Layer..."
    ./deploy_layer.sh $STAGE
fi

# Check if serverless is installed
if ! command -v serverless &> /dev/null; then
    echo "Installing Serverless Framework..."
    npm install -g serverless
fi

# Install npm dependencies
echo "📦 Installing dependencies..."
npm install

# Deploy the function
echo "⚡ Deploying Lambda function to $STAGE..."
serverless deploy --stage $STAGE

echo "✅ Deployment complete!"
echo ""
echo "🔗 Your API endpoint should be displayed above."
echo ""
echo "Test your endpoint with:"
echo "curl -X POST \\"
echo "  \$YOUR_ENDPOINT_URL \\"
echo "  -H \"Content-Type: application/json\" \\"
echo "  -d @test_payload.json"
