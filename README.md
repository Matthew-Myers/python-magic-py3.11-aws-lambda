# CSV Validator Lambda

A simple AWS Lambda function that validates if an uploaded file is a CSV using python-magic library.

## Features

- Validates file MIME type using python-magic
- Supports multiple CSV MIME types (text/csv, text/plain, application/csv)
- Additional content validation for files detected as text/plain
- Returns structured response with validation result

## Prerequisites

- Node.js and npm
- Docker (for building Linux dependencies)
- AWS CLI configured with appropriate credentials
- Serverless Framework

## Architecture

This Lambda function uses a **Lambda Layer** for the python-magic library and libmagic system dependencies. The layer is built using Docker to ensure Linux compatibility.

## Setup

### Option 1: Automated Deployment (Recommended)
```bash
# This will automatically build the layer and deploy everything
./deploy.sh          # Deploy to dev
./deploy.sh prod      # Deploy to production
```

### Option 2: Manual Step-by-Step Deployment
```bash
# 1. Build the Lambda Layer (Linux dependencies)
./build_layer.sh

# 2. Deploy the Layer to AWS
./deploy_layer.sh dev    # or 'prod'

# 3. Install npm dependencies
npm install

# 4. Deploy the Lambda function
serverless deploy --stage dev
```

## Usage

The Lambda function expects a POST request with the following JSON payload:

```json
{
  "file_content": "base64-encoded-file-content",
  "filename": "example.csv"
}
```

### Response Format

```json
{
  "statusCode": 200,
  "body": {
    "success": true,
    "message": "File is a valid CSV",
    "mimetype": "text/csv",
    "filename": "example.csv"
  }
}
```

## Local Testing

### Test the Lambda Layer Build
```bash
# After building the layer, test if it works
./test_layer.py
```

### Test the Lambda Function Logic
```bash
# Activate virtual environment and test
source .venv/bin/activate
python test_local.py
```

### Test with Simple Payload
```bash
python lambda_function.py
```

## Test Payload

Use the provided `test_payload.json` file which contains a base64-encoded CSV:
- Original content: "name,age,city\nJohn,30,New York\nJane,25,Los Angeles"

## API Endpoint

After deployment, you'll get an API Gateway endpoint:
```
POST https://your-api-id.execute-api.region.amazonaws.com/dev/validate
```

## Example cURL Request

```bash
curl -X POST \
  https://your-api-id.execute-api.region.amazonaws.com/dev/validate \
  -H "Content-Type: application/json" \
  -d @test_payload.json
```

## Supported MIME Types

The function validates the following MIME types as CSV:
- `text/csv`
- `application/csv`
- `text/comma-separated-values`
- `text/plain` (only if content has consistent CSV structure with 80%+ lines containing commas)

## Validation Logic

1. **Primary Check**: Uses python-magic to detect MIME type
2. **Secondary Check**: For `text/plain` files, performs content analysis:
   - Requires 80%+ of lines to contain commas
   - Checks for consistent field structure across lines
   - Validates that comma patterns are consistent (not random punctuation)

## Troubleshooting

### Common Issues

1. **Docker not running**
   ```bash
   # Start Docker Desktop or Docker daemon
   docker info  # Should not show errors
   ```

2. **Layer import errors**
   - Ensure the layer was built for Linux using Docker
   - Check that layer_info.json exists after layer deployment
   - Verify the layer ARN in serverless.yml

3. **libmagic errors in Lambda**
   - The layer includes libmagic shared libraries
   - Environment variables are set for library paths
   - Built specifically for Amazon Linux 2 compatibility

### Manual Layer Testing
```bash
# Test the layer contents after building
cd layer && find . -name "*.so*" -o -name "magic*"
```

## Cleanup

To remove the deployed resources:
```bash
# Remove Lambda function
serverless remove --stage dev

# Remove Lambda Layer (manual via AWS Console or CLI)
aws lambda delete-layer-version --layer-name python-magic-layer-dev --version-number X
```
