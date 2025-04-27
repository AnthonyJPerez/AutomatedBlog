#!/bin/bash
# Script to redeploy the function app with proper Poetry configuration
# This addresses deployment errors related to Python configuration

# Set variables based on environment
ENVIRONMENT="${1:-prod}"  # Default to prod if not specified
RESOURCE_GROUP="blogauto-${ENVIRONMENT}-rg"
FUNCTION_APP_NAME="blogauto-${ENVIRONMENT}-function"

# Echo current settings
echo "Redeploying function app with proper Poetry configuration"
echo "Environment: $ENVIRONMENT"
echo "Resource Group: $RESOURCE_GROUP"
echo "Function App: $FUNCTION_APP_NAME"

# First, ensure we're logged in to Azure
echo "Checking Azure login status..."
az account show &> /dev/null
if [ $? -ne 0 ]; then
  echo "ERROR: Not logged in to Azure. Please run 'az login' first."
  exit 1
fi

# Prepare a temporary directory for deployment
echo "Preparing deployment files..."
TEMP_DIR=$(mktemp -d)

# Copy Poetry-compatible pyproject.toml and requirements.txt
cp deployment-templates/pyproject.toml $TEMP_DIR/
cp deployment-templates/requirements.txt $TEMP_DIR/

# Copy function app files
echo "Copying function app files..."
cp -r function_app $TEMP_DIR/
cp -r functions $TEMP_DIR/
cp -r shared $TEMP_DIR/

# Create a minimal host.json if it doesn't exist
if [ ! -f "host.json" ]; then
  echo "Creating minimal host.json..."
  cat > $TEMP_DIR/host.json << 'EOF'
{
  "version": "2.0",
  "logging": {
    "applicationInsights": {
      "samplingSettings": {
        "isEnabled": true,
        "excludedTypes": "Request"
      }
    }
  },
  "extensionBundle": {
    "id": "Microsoft.Azure.Functions.ExtensionBundle",
    "version": "[3.*, 4.0.0)"
  }
}
EOF
else
  cp host.json $TEMP_DIR/
fi

# Create a minimal local.settings.json
echo "Creating minimal local.settings.json..."
cat > $TEMP_DIR/local.settings.json << 'EOF'
{
  "IsEncrypted": false,
  "Values": {
    "FUNCTIONS_WORKER_RUNTIME": "python",
    "AzureWebJobsStorage": ""
  }
}
EOF

# Create a zip file for deployment
echo "Creating deployment zip file..."
cd $TEMP_DIR
zip -r deploy.zip ./*
cd - > /dev/null

# Check if the function app exists
echo "Checking if function app exists..."
APP_EXISTS=$(az functionapp show --name $FUNCTION_APP_NAME --resource-group $RESOURCE_GROUP &> /dev/null && echo "yes" || echo "no")

if [ "$APP_EXISTS" == "yes" ]; then
  # Deploy using the zip file
  echo "Deploying files to function app..."
  az functionapp deployment source config-zip --resource-group $RESOURCE_GROUP --name $FUNCTION_APP_NAME --src $TEMP_DIR/deploy.zip
  
  # Restart the function app
  echo "Restarting the function app..."
  az functionapp restart --resource-group $RESOURCE_GROUP --name $FUNCTION_APP_NAME
  
  echo "Deployment completed. The function app should be accessible at: https://$FUNCTION_APP_NAME.azurewebsites.net/"
else
  echo "ERROR: Function app '$FUNCTION_APP_NAME' not found in resource group '$RESOURCE_GROUP'."
  echo "Please check the name and resource group or deploy the infrastructure first."
  exit 1
fi

# Clean up
echo "Cleaning up temporary files..."
rm -rf $TEMP_DIR

echo "Done!"