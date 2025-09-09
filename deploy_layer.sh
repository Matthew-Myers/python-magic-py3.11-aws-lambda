#!/bin/bash

# Deploy Lambda Layer for python-magic

set -e

echo "🚀 Deploying Lambda Layer..."

# Check if layer zip exists
if [ ! -f "python-magic-layer.zip" ]; then
    echo "❌ Layer zip not found. Run ./build_layer.sh first."
    exit 1
fi

# Set default stage and architecture
STAGE=${1:-dev}
ARCH=${2:-x86_64}
LAYER_NAME="python-magic-layer-$STAGE"

case "$ARCH" in
  x86_64|arm64)
    COMPAT_ARCHS="$ARCH"
    ;;
  both)
    COMPAT_ARCHS="x86_64 arm64"
    ;;
  *)
    echo "❌ Unknown ARCH: $ARCH (expected x86_64, arm64, or both)" && exit 1
    ;;
esac

echo "📦 Deploying layer: $LAYER_NAME"

# Deploy using AWS CLI
echo "🏷️  Compatible architectures: $COMPAT_ARCHS"
LAYER_VERSION=$(aws lambda publish-layer-version \
    --layer-name "$LAYER_NAME" \
    --description "Python-magic library with libmagic for CSV validation" \
    --zip-file fileb://python-magic-layer.zip \
    --compatible-runtimes python3.11 python3.10 python3.9 \
    --compatible-architectures $COMPAT_ARCHS \
    --query 'Version' \
    --output text)

echo "✅ Layer deployed successfully!"
echo "📋 Layer ARN: arn:aws:lambda:$(aws configure get region):$(aws sts get-caller-identity --query Account --output text):layer:$LAYER_NAME:$LAYER_VERSION"
echo "📝 Layer Version: $LAYER_VERSION"

# Save layer info for serverless deployment
cat > layer_info.json << EOF
{
  "layerName": "$LAYER_NAME",
  "layerVersion": $LAYER_VERSION,
  "layerArn": "arn:aws:lambda:$(aws configure get region):$(aws sts get-caller-identity --query Account --output text):layer:$LAYER_NAME:$LAYER_VERSION"
}
EOF

echo ""
echo "🔗 Layer info saved to layer_info.json"
echo "Now you can deploy the Lambda function with: ./deploy.sh $STAGE"
