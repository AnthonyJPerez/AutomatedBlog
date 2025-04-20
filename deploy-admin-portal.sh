#!/bin/bash
# Script to directly deploy the admin portal to Azure Web App
# Usage: ./deploy-admin-portal.sh <resource-group> <webapp-name>

# Configuration
RESOURCE_GROUP=${1:-"blogauto-prod-rg"}
WEBAPP_NAME=${2:-"blogauto-prod-admin"}

echo "Deploying admin portal to $WEBAPP_NAME in resource group $RESOURCE_GROUP"

# Create a deployment package
echo "Creating deployment package..."
mkdir -p admin-package
mkdir -p admin-package/data
mkdir -p admin-package/static
mkdir -p admin-package/templates
mkdir -p admin-package/src

# Copy application files
cp main.py admin-package/
cp wsgi.py admin-package/
cp web.config admin-package/
cp -r static/* admin-package/static/ 2>/dev/null || true
cp -r templates/* admin-package/templates/ 2>/dev/null || true
cp -r src/* admin-package/src/ 2>/dev/null || true

# Copy data directory if it exists
if [ -d "data" ]; then
  cp -r data/* admin-package/data/ 2>/dev/null || true
fi

# Create a requirements.txt file if it doesn't exist
if [ ! -f "requirements.txt" ]; then
  cat > admin-package/requirements.txt << EOF
flask==2.0.3
gunicorn==20.1.0
python-dotenv==0.21.1
werkzeug==2.0.3
azure-functions==1.15.0
azure-identity==1.12.0
azure-keyvault-secrets==4.6.0
azure-storage-blob==12.16.0
requests==2.29.0
markdown==3.4.3
pygments==2.15.1
langdetect==1.0.9
trafilatura==1.6.1
azure-mgmt-storage==21.0.0
azure-mgmt-resource==22.0.0
Flask-SQLAlchemy==3.0.3
sqlalchemy==2.0.12
psycopg2-binary==2.9.6
EOF
else
  cp requirements.txt admin-package/
fi

# First, stop the web app
echo "Stopping the web app..."
az webapp stop --resource-group "$RESOURCE_GROUP" --name "$WEBAPP_NAME"

# Get publishing credentials
echo "Getting publishing credentials..."
CREDS=$(az webapp deployment list-publishing-credentials \
  --resource-group "$RESOURCE_GROUP" \
  --name "$WEBAPP_NAME" \
  --output json)

PUBLISH_USER=$(echo $CREDS | jq -r '.publishingUserName')
PUBLISH_PWD=$(echo $CREDS | jq -r '.publishingPassword')
KUDU_URL="https://$WEBAPP_NAME.scm.azurewebsites.net"

# Clean wwwroot directory
echo "Cleaning wwwroot directory..."
curl -X DELETE -u "$PUBLISH_USER:$PUBLISH_PWD" \
  "$KUDU_URL/api/vfs/site/wwwroot/hostingstart.html"

curl -X DELETE -u "$PUBLISH_USER:$PUBLISH_PWD" \
  "$KUDU_URL/api/vfs/site/wwwroot/output.tar.gz"

# Create a zip file of the application
echo "Creating zip file..."
(cd admin-package && zip -r ../admin-portal.zip *)

# Deploy using REST API
echo "Deploying using REST API..."
curl -X POST -u "$PUBLISH_USER:$PUBLISH_PWD" \
  --data-binary @admin-portal.zip \
  "$KUDU_URL/api/zipdeploy"

echo "Setting app configuration..."
az webapp config set \
  --resource-group "$RESOURCE_GROUP" \
  --name "$WEBAPP_NAME" \
  --startup-file "gunicorn --bind=0.0.0.0:5000 --timeout 600 wsgi:application" \
  --linux-fx-version "PYTHON|3.11"

# Set additional app settings
az webapp config appsettings set \
  --resource-group "$RESOURCE_GROUP" \
  --name "$WEBAPP_NAME" \
  --settings \
  PYTHONPATH="/home/site/wwwroot" \
  SCM_DO_BUILD_DURING_DEPLOYMENT=true \
  WEBSITES_ENABLE_APP_SERVICE_STORAGE=true \
  ENABLE_ORYX_BUILD=true \
  FLASK_APP=main.py \
  FLASK_ENV=production

# Start the web app
echo "Starting the web app..."
az webapp start --resource-group "$RESOURCE_GROUP" --name "$WEBAPP_NAME"

# Cleanup
rm -rf admin-package
rm -f admin-portal.zip

echo "Deployment complete!"
echo "Web app URL: https://$WEBAPP_NAME.azurewebsites.net/"