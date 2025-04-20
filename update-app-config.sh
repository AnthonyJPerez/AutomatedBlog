#!/bin/bash
# Script to update the Function App configuration for admin portal support

# Usage:
# ./update-app-config.sh <resource-group> <function-app-name>

if [ $# -lt 2 ]; then
  echo "Usage: $0 <resource-group> <function-app-name>"
  exit 1
fi

RESOURCE_GROUP=$1
FUNCTION_APP_NAME=$2

echo "Updating Function App configuration for $FUNCTION_APP_NAME in resource group $RESOURCE_GROUP"

# Update the application settings
echo "Updating app settings for admin portal support..."
az webapp config appsettings set \
  --resource-group $RESOURCE_GROUP \
  --name $FUNCTION_APP_NAME \
  --settings \
  SCM_DO_BUILD_DURING_DEPLOYMENT=true \
  ENABLE_ORYX_BUILD=true \
  FLASK_APP=main.py \
  WEBSITES_PORT=5000 \
  ADMIN_PORTAL_ENABLED=true

# Update the site configuration
echo "Updating site configuration..."
az webapp config set \
  --resource-group $RESOURCE_GROUP \
  --name $FUNCTION_APP_NAME \
  --linux-fx-version "PYTHON|3.11" \
  --startup-file "gunicorn --bind=0.0.0.0:5000 --timeout 600 main:app"

# Set the app to be a non-function app
echo "Setting app kind..."
az resource update \
  --resource-group $RESOURCE_GROUP \
  --name $FUNCTION_APP_NAME \
  --resource-type "Microsoft.Web/sites" \
  --set kind=app,linux

echo "Configuration update complete. Please wait a few minutes for changes to take effect."
echo "Your admin portal should be available at: https://$FUNCTION_APP_NAME.azurewebsites.net/"