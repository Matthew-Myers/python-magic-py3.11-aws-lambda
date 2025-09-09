#!/bin/bash

# Build Lambda Layer for python-magic with libmagic
# This script uses Docker to build dependencies for Linux (Amazon Linux 2)

set -e

echo "🏗️  Building Lambda Layer for python-magic..."

# Architecture (default x86_64). Use "arm64" to target Graviton.
ARCH=${1:-x86_64}
case "$ARCH" in
  x86_64)
    PLATFORM="linux/amd64"
    ;;
  arm64)
    PLATFORM="linux/arm64"
    ;;
  *)
    echo "❌ Unknown ARCH: $ARCH (expected x86_64 or arm64)" && exit 1
    ;;
esac

echo "🧭 Target architecture: $ARCH ($PLATFORM)"

# Clean previous builds
rm -rf layer/python/*
rm -f python-magic-layer.zip

echo "📦 Building Python dependencies for Linux..."

# Use Docker to build for Amazon Linux 2 (Lambda base)
docker run --rm --platform "$PLATFORM" \
  -v "$PWD/layer:/var/layer" \
  -v "$PWD/layer/requirements.txt:/var/requirements.txt" \
  amazonlinux:2 \
  bash -c "
    set -euo pipefail
    yum update -y && \
    yum install -y python3 python3-pip file file-libs file-devel gcc python3-devel && \

    # Install python dependencies (pure-Python for python-magic)
    mkdir -p /var/layer/python && \
    pip3 install --upgrade pip && \
    pip3 install --no-cache-dir --target /var/layer/python -r /var/requirements.txt && \

    # Install/copy libmagic and dependencies
    mkdir -p /var/layer/lib /var/layer/lib64 /var/layer/share && \
    cp -f /usr/lib64/libmagic.so* /var/layer/lib/ 2>/dev/null || true && \
    cp -f /usr/lib64/libmagic.so* /var/layer/lib64/ 2>/dev/null || true && \
    cp -f /lib64/libmagic.so* /var/layer/lib/ 2>/dev/null || true && \
    cp -f /lib64/libmagic.so* /var/layer/lib64/ 2>/dev/null || true && \
    # zlib is commonly required as a transitive dep
    cp -f /usr/lib64/libz.so* /var/layer/lib/ 2>/dev/null || true && \
    cp -f /usr/lib64/libz.so* /var/layer/lib64/ 2>/dev/null || true && \
    cp -f /lib64/libz.so* /var/layer/lib/ 2>/dev/null || true && \
    cp -f /lib64/libz.so* /var/layer/lib64/ 2>/dev/null || true && \

    # Magic database
    cp -r /usr/share/misc /var/layer/share/ 2>/dev/null || true && \
    cp -r /usr/share/file /var/layer/share/ 2>/dev/null || true && \

    # Ensure libmagic.so.1 symlink exists (some distros only ship .so.1.xx)
    (cd /var/layer/lib 2>/dev/null && {
      [ -f libmagic.so.1 ] || {
        target=$(ls -1 libmagic.so* 2>/dev/null | head -n1 || true); \
        [ -n "$target" ] && ln -sf "$target" libmagic.so.1 || true; \
      }
    }) && \
    (cd /var/layer/lib64 2>/dev/null && {
      [ -f libmagic.so.1 ] || {
        target=$(ls -1 libmagic.so* 2>/dev/null | head -n1 || true); \
        [ -n "$target" ] && ln -sf "$target" libmagic.so.1 || true; \
      }
    }) && \

    chmod -R 755 /var/layer/
  "

echo "📁 Creating layer zip file..."
cd layer
zip -r ../python-magic-layer.zip . -x "*.pyc" "*/__pycache__/*"
cd ..

echo "✅ Lambda Layer built successfully!"
echo "📦 Layer package: python-magic-layer.zip"
echo "📏 Size: $(du -h python-magic-layer.zip | cut -f1)"

echo ""
echo "Next steps:"
echo "1. Deploy the layer: ./deploy_layer.sh"
echo "2. Deploy the Lambda function: ./deploy.sh"
