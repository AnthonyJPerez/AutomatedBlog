#!/bin/bash
# fix-webapp-directly.sh
# Direct intervention script to fix admin portal issues
# Usage: ./fix-webapp-directly.sh <resource-group-name> <function-app-name>

if [ $# -lt 2 ]; then
    echo "Usage: $0 <resource-group-name> <function-app-name>"
    exit 1
fi

RESOURCE_GROUP=$1
FUNCTION_APP_NAME=$2

echo "====================================================="
echo "DIRECT FIX SCRIPT FOR ADMIN PORTAL"
echo "Resource Group: $RESOURCE_GROUP"
echo "App Name: $FUNCTION_APP_NAME"
echo "====================================================="

# STEP 1: Completely reset the app to a known, good state as a Web App
echo "Step 1: Resetting app to known good state..."
az resource update --resource-group $RESOURCE_GROUP --name $FUNCTION_APP_NAME \
    --resource-type "Microsoft.Web/sites" --set kind="app,linux" --api-version "2021-02-01"

# STEP 2: Set the most basic, direct startup command
echo "Step 2: Setting direct startup command..."
az webapp config set --resource-group $RESOURCE_GROUP --name $FUNCTION_APP_NAME \
    --startup-file "python -m flask run --host=0.0.0.0 --port=8000"

# STEP 3: Update to critical app settings (using port 8000 for clarity)
echo "Step 3: Setting critical app settings..."
az webapp config appsettings set --resource-group $RESOURCE_GROUP --name $FUNCTION_APP_NAME \
    --settings \
    FLASK_APP=main.py \
    WEBSITES_PORT=8000 \
    PORT=8000 \
    FLASK_DEBUG=1 \
    SCM_DO_BUILD_DURING_DEPLOYMENT=true \
    PYTHONPATH=/home/site/wwwroot

# STEP 4: Stop the app
echo "Step 4: Stopping app..."
az webapp stop --resource-group $RESOURCE_GROUP --name $FUNCTION_APP_NAME

# Wait a moment to ensure stop completes
sleep 10

# STEP 5: Start the app
echo "Step 5: Starting app..."
az webapp start --resource-group $RESOURCE_GROUP --name $FUNCTION_APP_NAME

# Wait for startup
echo "Waiting 30 seconds for app to start..."
sleep 30

# STEP 6: Check status
echo "Step 6: Checking app status..."
STATUS=$(az webapp show --resource-group $RESOURCE_GROUP --name $FUNCTION_APP_NAME --query state -o tsv)
echo "App status: $STATUS"

# STEP 7: Try to get HTTP response
echo "Step 7: Checking HTTP response..."
HTTP_RESPONSE=$(curl -s -o /dev/null -w "%{http_code}" https://$FUNCTION_APP_NAME.azurewebsites.net/)
echo "HTTP response: $HTTP_RESPONSE"

# Show deployment logs
echo "Step 8: Showing deployment logs (last 10 lines)..."
az webapp log deployment show --resource-group $RESOURCE_GROUP --name $FUNCTION_APP_NAME | tail -10

echo "====================================================="
echo "Now please check: https://$FUNCTION_APP_NAME.azurewebsites.net/"
echo "If still not working, try the direct diagnostic portal:"
echo "https://$FUNCTION_APP_NAME.scm.azurewebsites.net/DebugConsole"
echo "====================================================="