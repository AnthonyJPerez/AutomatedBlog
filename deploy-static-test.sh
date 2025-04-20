#!/bin/bash
# deploy-static-test.sh
# Script to deploy a static test page to verify Azure App Service basics
# Usage: ./deploy-static-test.sh <resource-group-name> <function-app-name>

if [ $# -lt 2 ]; then
    echo "Usage: $0 <resource-group-name> <function-app-name>"
    exit 1
fi

RESOURCE_GROUP=$1
FUNCTION_APP_NAME=$2

echo "====================================================="
echo "DEPLOYING STATIC TEST PAGE TO AZURE APP SERVICE"
echo "Resource Group: $RESOURCE_GROUP"
echo "App Name: $FUNCTION_APP_NAME"
echo "====================================================="

# Create a temporary deployment package directory
TEMP_DIR=$(mktemp -d)
echo "Creating deployment package in: $TEMP_DIR"

# Copy the static test files to the temp directory
cp -r static-test/* $TEMP_DIR/
echo "Copied static test files to deployment package"

# Create a simple web.config file that just serves static files
cat > $TEMP_DIR/web.config << EOF
<?xml version="1.0" encoding="utf-8"?>
<configuration>
  <system.webServer>
    <staticContent>
      <mimeMap fileExtension=".html" mimeType="text/html" />
      <mimeMap fileExtension=".css" mimeType="text/css" />
      <mimeMap fileExtension=".js" mimeType="application/javascript" />
    </staticContent>
    <defaultDocument>
      <files>
        <add value="index.html" />
      </files>
    </defaultDocument>
  </system.webServer>
</configuration>
EOF
echo "Created web.config in deployment package"

# Configure the app to be a basic web app (not a function app)
echo "Configuring app as web app..."
az resource update --resource-group $RESOURCE_GROUP --name $FUNCTION_APP_NAME \
  --resource-type "Microsoft.Web/sites" --set kind="app,linux" --api-version "2021-02-01"

# Remove any startup commands to just serve static files
echo "Clearing startup command to serve static files..."
az webapp config set --resource-group $RESOURCE_GROUP --name $FUNCTION_APP_NAME --startup-file ""

# Deploy the app using ZIP deployment
echo "Deploying static files via ZIP..."
cd $TEMP_DIR
zip -r app.zip ./*
az webapp deployment source config-zip \
  --resource-group $RESOURCE_GROUP \
  --name $FUNCTION_APP_NAME \
  --src app.zip

# Clean up
cd -
rm -rf $TEMP_DIR

# Restart the app
echo "Restarting app..."
az webapp restart --resource-group $RESOURCE_GROUP --name $FUNCTION_APP_NAME

# Wait for restart
echo "Waiting 15 seconds for app to restart..."
sleep 15

# Check status
echo "Checking app status..."
STATUS=$(az webapp show --resource-group $RESOURCE_GROUP --name $FUNCTION_APP_NAME --query state -o tsv)
echo "App status: $STATUS"

echo "====================================================="
echo "STATIC DEPLOYMENT COMPLETE"
echo "Now visit: https://$FUNCTION_APP_NAME.azurewebsites.net/"
echo "You should see a simple static test page."
echo "If this works but the Flask app doesn't, the issue is with the Flask configuration."
echo "====================================================="