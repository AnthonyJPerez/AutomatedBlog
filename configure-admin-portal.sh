#!/bin/bash
# configure-admin-portal.sh
# Script to configure the Azure Function App to serve the admin portal as a web app
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

# Create a temp directory for logs
TEMP_DIR=$(mktemp -d)
LOG_FILE="$TEMP_DIR/deployment.log"

# Track overall success
SUCCESS=true

# Helper function for logging with timestamp
log() {
    local timestamp=$(date +"%Y-%m-%d %H:%M:%S")
    echo "[$timestamp] $1" | tee -a "$LOG_FILE"
}

# Step 1: Convert to Web App (not Function App)
log "Converting to Web App configuration..."
az resource update --resource-group $RESOURCE_GROUP --name $FUNCTION_APP_NAME \
    --resource-type "Microsoft.Web/sites" --set kind="app,linux" --api-version "2021-02-01" >> "$LOG_FILE" 2>&1

if [ $? -ne 0 ]; then
    log "⚠️ Warning: Failed to update app kind."
    SUCCESS=false
else
    log "✓ App kind updated successfully"
fi

# Step 2: Configure comprehensive app settings
log "Configuring app settings..."
az webapp config appsettings set --resource-group $RESOURCE_GROUP --name $FUNCTION_APP_NAME \
    --settings \
    FLASK_APP=main.py \
    WEBSITES_PORT=5000 \
    ADMIN_PORTAL_ENABLED=true \
    SCM_DO_BUILD_DURING_DEPLOYMENT=true \
    ENABLE_ORYX_BUILD=true \
    FLASK_ENV=production \
    WSGI_HANDLER=main.app \
    PYTHONPATH=/home/site/wwwroot >> "$LOG_FILE" 2>&1

if [ $? -ne 0 ]; then
    log "⚠️ Warning: Failed to configure app settings."
    SUCCESS=false
else
    log "✓ App settings configured successfully"
fi

# Step 3: Set Python runtime and version
log "Setting Python runtime..."
az webapp config set --resource-group $RESOURCE_GROUP --name $FUNCTION_APP_NAME \
    --linux-fx-version "PYTHON|3.11" >> "$LOG_FILE" 2>&1

if [ $? -ne 0 ]; then
    log "⚠️ Warning: Failed to set Python runtime."
    SUCCESS=false
else
    log "✓ Python runtime set successfully"
fi

# Step 4: Remove any existing startup command to ensure web.config is used
log "Resetting startup command to use web.config..."
az webapp config set --resource-group $RESOURCE_GROUP --name $FUNCTION_APP_NAME \
    --startup-file "" >> "$LOG_FILE" 2>&1

if [ $? -ne 0 ]; then
    log "⚠️ Warning: Failed to reset startup command."
    SUCCESS=false
else
    log "✓ Startup command reset successfully"
fi

# Step 5: Configure proper web server settings
log "Configuring web server settings..."
az webapp config set --resource-group $RESOURCE_GROUP --name $FUNCTION_APP_NAME \
    --use-32bit-worker-process false \
    --http20-enabled true \
    --min-tls-version 1.2 \
    --ftps-state Disabled >> "$LOG_FILE" 2>&1

if [ $? -ne 0 ]; then
    log "⚠️ Warning: Failed to configure web server settings."
    SUCCESS=false
else
    log "✓ Web server settings configured successfully"
fi

# Step 6: Ensure handlers are properly configured
log "Configuring handlers..."
az webapp config set --resource-group $RESOURCE_GROUP --name $FUNCTION_APP_NAME \
    --generic-configurations "{'handlers': []}" >> "$LOG_FILE" 2>&1

if [ $? -ne 0 ]; then
    log "⚠️ Warning: Failed to reset handlers configuration. This is OK as web.config will override."
    SUCCESS=false
else
    log "✓ Handlers configuration reset successfully"
fi

# Step 7: Configure default documents
log "Configuring default documents..."
az webapp config set --resource-group $RESOURCE_GROUP --name $FUNCTION_APP_NAME \
    --generic-configurations "{'defaultDocuments': ['default.htm', 'default.html', 'index.htm', 'index.html', 'hostingstart.html']}" >> "$LOG_FILE" 2>&1

if [ $? -ne 0 ]; then
    log "⚠️ Warning: Failed to configure default documents."
    SUCCESS=false
else
    log "✓ Default documents configured successfully"
fi

# Step 8: Stop and start the app (more reliable than restart)
log "Stopping Function App..."
az webapp stop --resource-group $RESOURCE_GROUP --name $FUNCTION_APP_NAME >> "$LOG_FILE" 2>&1

if [ $? -ne 0 ]; then
    log "⚠️ Warning: Failed to stop the app."
    SUCCESS=false
else
    log "✓ App stopped successfully"
fi

log "Starting Function App..."
az webapp start --resource-group $RESOURCE_GROUP --name $FUNCTION_APP_NAME >> "$LOG_FILE" 2>&1

if [ $? -ne 0 ]; then
    log "⚠️ Warning: Failed to start the app."
    SUCCESS=false
else
    log "✓ App started successfully"
fi

# Print final status
if [ "$SUCCESS" = true ]; then
    log "✅ Admin portal configuration completed successfully!"
else
    log "⚠️ Admin portal configuration completed with some warnings."
    log "    The portal may still work correctly despite these warnings."
    log "    See deployment log for details: $LOG_FILE"
fi

log "Your admin portal should now be accessible at: https://$FUNCTION_APP_NAME.azurewebsites.net/"
log "If you encounter issues:"
log "    1. Check the logs: az webapp log tail --resource-group $RESOURCE_GROUP --name $FUNCTION_APP_NAME"
log "    2. Verify deployment: az webapp deployment list --resource-group $RESOURCE_GROUP --name $FUNCTION_APP_NAME"
log "    3. Review app settings: az webapp config appsettings list --resource-group $RESOURCE_GROUP --name $FUNCTION_APP_NAME"

# Provide final verification step
log "Checking if web app is accessible..."
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" "https://$FUNCTION_APP_NAME.azurewebsites.net/")
if [[ $HTTP_CODE -ge 200 && $HTTP_CODE -lt 400 ]]; then
    log "✅ Web app is responding with HTTP $HTTP_CODE - configuration successful!"
else 
    log "⚠️ Web app returned HTTP $HTTP_CODE - may need additional configuration or more time to start up."
fi