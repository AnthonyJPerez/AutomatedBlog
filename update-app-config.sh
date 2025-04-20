#!/bin/bash
# update-app-config.sh
# Script to directly update Azure App Service configuration for admin portal
# Usage: ./update-app-config.sh <resource-group-name> <function-app-name>

if [ $# -lt 2 ]; then
    echo "Usage: $0 <resource-group-name> <function-app-name>"
    exit 1
fi

RESOURCE_GROUP=$1
FUNCTION_APP_NAME=$2

echo "====================================================="
echo "UPDATING AZURE APP SERVICE CONFIGURATION"
echo "Resource Group: $RESOURCE_GROUP"
echo "App Name: $FUNCTION_APP_NAME"
echo "====================================================="

# Convert function app to web app
echo "Converting function app to web app..."
az resource update --resource-group $RESOURCE_GROUP --name $FUNCTION_APP_NAME \
    --resource-type "Microsoft.Web/sites" --set kind="app,linux" --api-version "2021-02-01"

# Configure app settings
echo "Setting critical app settings..."
az webapp config appsettings set --resource-group $RESOURCE_GROUP --name $FUNCTION_APP_NAME \
    --settings \
    FLASK_APP=main.py \
    WEBSITES_PORT=8000 \
    PORT=8000 \
    SCM_DO_BUILD_DURING_DEPLOYMENT=true \
    WSGI_LOG=D:\\home\\LogFiles\\application.log

# Configure the startup command
echo "Setting startup command to use Gunicorn..."
az webapp config set --resource-group $RESOURCE_GROUP --name $FUNCTION_APP_NAME \
    --startup-file "gunicorn --bind=0.0.0.0:8000 --timeout 600 wsgi:application"

# Configure Python version
echo "Ensuring Python 3.11 is used..."
az webapp config set --resource-group $RESOURCE_GROUP --name $FUNCTION_APP_NAME \
    --linux-fx-version "PYTHON|3.11"

# Force HTTPS
echo "Enforcing HTTPS for all traffic..."
az webapp update --resource-group $RESOURCE_GROUP --name $FUNCTION_APP_NAME \
    --https-only true

# Configure default documents
echo "Setting default documents..."
az webapp config set --resource-group $RESOURCE_GROUP --name $FUNCTION_APP_NAME \
    --generic-configurations "{'defaultDocuments': ['index.html','default.htm','hostingstart.html']}"

# Stop the app
echo "Stopping the app..."
az webapp stop --resource-group $RESOURCE_GROUP --name $FUNCTION_APP_NAME

# Start the app
echo "Starting the app..."
az webapp start --resource-group $RESOURCE_GROUP --name $FUNCTION_APP_NAME

echo "====================================================="
echo "APP CONFIGURATION UPDATE COMPLETE"
echo "Now visit: https://$FUNCTION_APP_NAME.azurewebsites.net/"
echo "If the admin portal still doesn't display, try running deploy-admin-portal.sh"
echo "====================================================="