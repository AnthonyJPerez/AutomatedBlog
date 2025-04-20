#!/bin/bash
# deploy-minimal-test.sh
# Script to deploy a minimal test application to verify Azure App Service works
# Usage: ./deploy-minimal-test.sh <resource-group-name> <function-app-name>

if [ $# -lt 2 ]; then
    echo "Usage: $0 <resource-group-name> <function-app-name>"
    exit 1
fi

RESOURCE_GROUP=$1
FUNCTION_APP_NAME=$2

echo "====================================================="
echo "DEPLOYING MINIMAL TEST APP TO AZURE APP SERVICE"
echo "Resource Group: $RESOURCE_GROUP"
echo "App Name: $FUNCTION_APP_NAME"
echo "====================================================="

# Create a temporary deployment package directory
TEMP_DIR=$(mktemp -d)
echo "Creating deployment package in: $TEMP_DIR"

# Copy the minimal app to the temp directory
cp minimal_app.py $TEMP_DIR/app.py
echo "Created app.py in deployment package"

# Create a simple requirements.txt
cat > $TEMP_DIR/requirements.txt << EOF
flask==2.0.1
gunicorn==20.1.0
EOF
echo "Created requirements.txt in deployment package"

# Create a simple web.config file
cat > $TEMP_DIR/web.config << EOF
<?xml version="1.0" encoding="utf-8"?>
<configuration>
  <appSettings>
    <add key="FLASK_APP" value="app.py" />
    <add key="PYTHONPATH" value="%home%\site\wwwroot" />
  </appSettings>
  <system.webServer>
    <handlers>
      <add name="PythonHandler" path="*" verb="*" modules="FastCgiModule" scriptProcessor="%home%\Python\3.11\python.exe|%home%\Python\3.11\wfastcgi.py" resourceType="Unspecified" requireAccess="Script" />
    </handlers>
  </system.webServer>
</configuration>
EOF
echo "Created web.config in deployment package"

# Set the configuration of the web app
echo "Configuring app settings..."
az webapp config appsettings set --resource-group $RESOURCE_GROUP --name $FUNCTION_APP_NAME \
  --settings \
  FLASK_APP=app.py \
  WEBSITES_PORT=8000 \
  SCM_DO_BUILD_DURING_DEPLOYMENT=true

# Set the startup command
echo "Setting startup command..."
az webapp config set --resource-group $RESOURCE_GROUP --name $FUNCTION_APP_NAME \
  --startup-file "python -m flask run --host=0.0.0.0 --port=8000"

# Deploy the app using ZIP deployment
echo "Deploying application via ZIP..."
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
echo "DEPLOYMENT COMPLETE"
echo "Now visit: https://$FUNCTION_APP_NAME.azurewebsites.net/"
echo "This minimal app should display a simple success page."
echo "====================================================="