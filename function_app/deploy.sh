#!/bin/bash
# Deploy script for Azure Functions v2 app

# This script deploys the Function App to Azure
# Usage: ./deploy.sh <function-app-name> <resource-group-name>

# Check if Azure CLI is installed
if ! command -v az &> /dev/null; then
    echo "Azure CLI not found. Please install it following the instructions at:"
    echo "https://docs.microsoft.com/en-us/cli/azure/install-azure-cli"
    exit 1
fi

# Check if parameters are provided
if [ "$#" -ne 2 ]; then
    echo "Usage: $0 <function-app-name> <resource-group-name>"
    exit 1
fi

FUNCTION_APP_NAME=$1
RESOURCE_GROUP=$2

echo "Deploying function app '$FUNCTION_APP_NAME' to resource group '$RESOURCE_GROUP'..."

# Check if the user is logged in to Azure
if ! az account show &> /dev/null; then
    echo "You are not logged in to Azure. Please run 'az login' first."
    exit 1
fi

# Check if the function app exists
if ! az functionapp show --name "$FUNCTION_APP_NAME" --resource-group "$RESOURCE_GROUP" &> /dev/null; then
    echo "Function app '$FUNCTION_APP_NAME' does not exist in resource group '$RESOURCE_GROUP'."
    echo "Creating it first with the Azure Bicep templates is recommended."
    exit 1
fi

# Package the function app
echo "Packaging the function app..."
mkdir -p dist
zip -r "dist/function-app.zip" . -x "*.git*" -x "dist/*" -x "*.venv*" -x "*.vscode*" -x "*.pytest_cache*" -x "*__pycache__*" -x "*.env"

# Deploy the package to Azure
echo "Deploying package to Azure..."
az functionapp deployment source config-zip \
    --resource-group "$RESOURCE_GROUP" \
    --name "$FUNCTION_APP_NAME" \
    --src "dist/function-app.zip" \
    --build-remote true \
    --verbose

# Check the deployment status
if [ $? -eq 0 ]; then
    echo "Deployment completed successfully."
    echo "Function app is available at: https://$FUNCTION_APP_NAME.azurewebsites.net"
else
    echo "Deployment failed. Please check the error messages above."
    exit 1
fi