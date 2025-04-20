#!/bin/bash
# configure-admin-portal.sh
# Script to configure the Azure Function App to serve the admin portal
# Usage: ./configure-admin-portal.sh <resource-group-name> <function-app-name>

# Check if the Azure CLI is installed
if ! command -v az &> /dev/null; then
    echo "Azure CLI is not installed. Please install it first."
    exit 1
fi

# Check if logged in to Azure
az account show &> /dev/null
if [ $? -ne 0 ]; then
    echo "Not logged in to Azure. Please run 'az login' first."
    exit 1
fi

# Check parameters
if [ $# -lt 2 ]; then
    echo "Usage: $0 <resource-group-name> <function-app-name>"
    exit 1
fi

RESOURCE_GROUP=$1
FUNCTION_APP_NAME=$2

echo "Configuring admin portal for Function App: $FUNCTION_APP_NAME in Resource Group: $RESOURCE_GROUP"

# Step 1: Update app kind to support web app functionality
echo "Setting app kind to 'app,linux'..."
az resource update --resource-group $RESOURCE_GROUP --name $FUNCTION_APP_NAME \
    --resource-type "Microsoft.Web/sites" --set kind="app,linux" > /dev/null

if [ $? -ne 0 ]; then
    echo "Failed to update app kind. Check if the resource group and function app name are correct."
    exit 1
fi

# Step 2: Configure app settings
echo "Configuring app settings..."
az webapp config appsettings set --resource-group $RESOURCE_GROUP --name $FUNCTION_APP_NAME \
    --settings FLASK_APP=main.py WEBSITES_PORT=5000 ADMIN_PORTAL_ENABLED=true > /dev/null

if [ $? -ne 0 ]; then
    echo "Failed to configure app settings."
    exit 1
fi

# Step 3: Set Python as the runtime stack
echo "Setting Python as the runtime stack..."
az webapp config set --resource-group $RESOURCE_GROUP --name $FUNCTION_APP_NAME \
    --linux-fx-version "PYTHON|3.11" > /dev/null

if [ $? -ne 0 ]; then
    echo "Failed to set Python runtime stack."
    exit 1
fi

# Step 4: Set startup command
echo "Setting startup command..."
az webapp config set --resource-group $RESOURCE_GROUP --name $FUNCTION_APP_NAME \
    --startup-file "gunicorn --bind=0.0.0.0:5000 --timeout 600 main:app" > /dev/null

if [ $? -ne 0 ]; then
    echo "Failed to set startup command."
    exit 1
fi

# Step 5: Configure default documents
echo "Configuring default documents..."
az webapp config set --resource-group $RESOURCE_GROUP --name $FUNCTION_APP_NAME \
    --generic-configurations "{'defaultDocuments': ['index.html', 'default.html', 'index.htm', 'default.htm']}" > /dev/null

if [ $? -ne 0 ]; then
    echo "Failed to configure default documents."
    exit 1
fi

# Step 6: Configure HTTP platform handler
echo "Configuring HTTP platform handler..."
az webapp config set --resource-group $RESOURCE_GROUP --name $FUNCTION_APP_NAME \
    --generic-configurations "{'handlerMappings': [{'extensionless': 'true', 'scriptProcessor': 'python', 'arguments': ''}]}" > /dev/null

if [ $? -ne 0 ]; then
    echo "Failed to configure HTTP platform handler."
    exit 1
fi

# Step 7: Restart the function app
echo "Restarting Function App..."
az webapp restart --resource-group $RESOURCE_GROUP --name $FUNCTION_APP_NAME > /dev/null

if [ $? -ne 0 ]; then
    echo "Failed to restart Function App."
    exit 1
fi

echo "Admin portal configuration completed successfully!"
echo "Your admin portal should now be accessible at: https://$FUNCTION_APP_NAME.azurewebsites.net/"
echo "If you still encounter issues, check the logs in the Azure Portal."