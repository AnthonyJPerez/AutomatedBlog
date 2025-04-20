#!/bin/bash
# Script to deploy the admin portal to an existing Function App

# Usage:
# ./deploy-admin-portal.sh <resource-group> <function-app-name>

if [ $# -lt 2 ]; then
  echo "Usage: $0 <resource-group> <function-app-name>"
  exit 1
fi

RESOURCE_GROUP=$1
FUNCTION_APP_NAME=$2

echo "Deploying admin portal to $FUNCTION_APP_NAME in resource group $RESOURCE_GROUP"

# Create a temporary deployment package
TEMP_DIR=$(mktemp -d)
echo "Creating deployment package in $TEMP_DIR"

# Copy necessary files
mkdir -p $TEMP_DIR/templates
mkdir -p $TEMP_DIR/static
mkdir -p $TEMP_DIR/src

# Copy function code
cp -r src/* $TEMP_DIR/src/

# Copy admin portal files
cp -r templates/* $TEMP_DIR/templates/
cp -r static/* $TEMP_DIR/static/

# Copy main application file
cp main.py $TEMP_DIR/

# Create a simple wsgi.py if it doesn't exist
echo "from main import app as application" > $TEMP_DIR/wsgi.py

# Create a minimal requirements.txt if it doesn't exist
if [ ! -f $TEMP_DIR/requirements.txt ]; then
  echo "Creating minimal requirements.txt"
  cat > $TEMP_DIR/requirements.txt << EOL
flask
gunicorn
azure-functions
azure-storage-blob
azure-keyvault-secrets
azure-identity
python-dotenv
openai
anthropic
requests
markdown
pyyaml
EOL
fi

# Create a zip package
ZIP_FILE="admin-portal-deploy.zip"
echo "Creating zip package $ZIP_FILE"
(cd $TEMP_DIR && zip -r ../$ZIP_FILE *)

# Deploy the package to Azure
echo "Deploying zip package to Azure..."
az webapp deployment source config-zip \
  --resource-group $RESOURCE_GROUP \
  --name $FUNCTION_APP_NAME \
  --src $ZIP_FILE

# Clean up
echo "Cleaning up temporary files..."
rm -rf $TEMP_DIR
rm $ZIP_FILE

echo "Deployment complete. Please wait a few minutes for the application to start."
echo "Your admin portal should be available at: https://$FUNCTION_APP_NAME.azurewebsites.net/"
echo "If the admin portal is not accessible, run the update-app-config.sh script to update the app configuration."