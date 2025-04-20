#!/bin/bash
# Comprehensive script to configure the Function App for admin portal use
# This script handles all necessary configuration changes to make the admin portal
# the default application at the root URL of the Function App

# Usage:
# ./configure-admin-portal.sh <resource-group> <function-app-name>

if [ $# -lt 2 ]; then
  echo "Usage: $0 <resource-group> <function-app-name>"
  exit 1
fi

RESOURCE_GROUP=$1
FUNCTION_APP_NAME=$2

echo "=========================================================="
echo "Configuring Function App for admin portal: $FUNCTION_APP_NAME"
echo "Resource Group: $RESOURCE_GROUP"
echo "=========================================================="

# Step 1: Update app kind to "app,linux" for web app functionality
echo "Setting app kind to 'app,linux'..."
az resource update \
  --resource-group $RESOURCE_GROUP \
  --name $FUNCTION_APP_NAME \
  --resource-type "Microsoft.Web/sites" \
  --set kind=app,linux

# Step 2: Update application settings for Flask web app
echo "Updating application settings..."
az webapp config appsettings set \
  --resource-group $RESOURCE_GROUP \
  --name $FUNCTION_APP_NAME \
  --settings \
  SCM_DO_BUILD_DURING_DEPLOYMENT=true \
  ENABLE_ORYX_BUILD=true \
  FLASK_APP=main.py \
  WEBSITES_PORT=5000 \
  ADMIN_PORTAL_ENABLED=true

# Step 3: Configure Python runtime and startup command
echo "Setting Python runtime and startup command..."
az webapp config set \
  --resource-group $RESOURCE_GROUP \
  --name $FUNCTION_APP_NAME \
  --linux-fx-version "PYTHON|3.11" \
  --startup-file "gunicorn --bind=0.0.0.0:5000 --timeout 600 main:app"

# Step 4: Set default documents for root URL
echo "Configuring default documents..."
az webapp config set \
  --resource-group $RESOURCE_GROUP \
  --name $FUNCTION_APP_NAME \
  --default-documents "index.html" "index.htm" "default.html" "default.htm" "hostingstart.html"

# Step 5: Enable HTTP logging for troubleshooting
echo "Enabling HTTP logging..."
az webapp log config \
  --resource-group $RESOURCE_GROUP \
  --name $FUNCTION_APP_NAME \
  --web-server-logging filesystem

# Step 6: Configure routing to serve the admin portal at root
echo "Configuring site routing..."
az webapp config set \
  --resource-group $RESOURCE_GROUP \
  --name $FUNCTION_APP_NAME \
  --generic-configurations '{"httpLoggingEnabled": true, "detailedErrorLoggingEnabled": true}'

# Step 7: Configure site extensions for Python web app
echo "Configuring site extensions..."
az webapp config set \
  --resource-group $RESOURCE_GROUP \
  --name $FUNCTION_APP_NAME \
  --always-on true \
  --http20-enabled true \
  --min-tls-version 1.2

# Step 8: Create an empty web.config file to ensure Azure uses the correct startup command
echo "Updating deployment options..."
az webapp config set \
  --resource-group $RESOURCE_GROUP \
  --name $FUNCTION_APP_NAME \
  --ftps-state Disabled

# Step 9: Create a proper web.config file if needed
echo "Creating proper web.config file..."
TMP_DIR=$(mktemp -d)
WEB_CONFIG_PATH="$TMP_DIR/web.config"

cat > "$WEB_CONFIG_PATH" << 'EOL'
<?xml version="1.0" encoding="utf-8"?>
<configuration>
  <system.webServer>
    <handlers>
      <add name="PythonHandler" path="*" verb="*" modules="httpPlatformHandler" resourceType="Unspecified" />
    </handlers>
    <httpPlatform processPath="%home%\site\wwwroot\startup.sh"
                  arguments=""
                  stdoutLogEnabled="true"
                  stdoutLogFile="%home%\LogFiles\stdout.log"
                  startupTimeLimit="600">
      <environmentVariables>
        <environmentVariable name="PYTHONPATH" value="%home%\site\wwwroot" />
        <environmentVariable name="PORT" value="%HTTP_PLATFORM_PORT%" />
      </environmentVariables>
    </httpPlatform>
  </system.webServer>
</configuration>
EOL

# Create startup.sh script
STARTUP_SH_PATH="$TMP_DIR/startup.sh"

cat > "$STARTUP_SH_PATH" << 'EOL'
#!/bin/bash
echo "Starting admin portal application..."
cd $HOME/site/wwwroot
gunicorn --bind=0.0.0.0:$PORT --timeout 600 main:app
EOL

# Make startup.sh executable
chmod +x "$STARTUP_SH_PATH"

# Deploy the files
echo "Deploying web.config and startup.sh..."
az webapp deploy --resource-group $RESOURCE_GROUP --name $FUNCTION_APP_NAME --src-path "$WEB_CONFIG_PATH" --target-path "/home/site/wwwroot/web.config" --type static
az webapp deploy --resource-group $RESOURCE_GROUP --name $FUNCTION_APP_NAME --src-path "$STARTUP_SH_PATH" --target-path "/home/site/wwwroot/startup.sh" --type static

# Clean up temp dir
rm -rf "$TMP_DIR"

# Step 10: Restart the web app to apply all changes
echo "Restarting the web app to apply changes..."
az webapp restart --resource-group $RESOURCE_GROUP --name $FUNCTION_APP_NAME

echo "=========================================================="
echo "Configuration completed successfully."
echo "Your admin portal should be available at: https://$FUNCTION_APP_NAME.azurewebsites.net/"
echo "Please allow a few minutes for all changes to take effect."
echo "=========================================================="