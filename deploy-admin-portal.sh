#!/bin/bash
# -----------------------------
# Azure Web App: Zip‑deploy Flask admin portal
# -----------------------------

# Variables — adjust to match your setup
RESOURCE_GROUP="${RESOURCE_GROUP:-blogauto-prod-rg}"
APP_NAME="${APP_NAME:-blogauto-prod-admin}"
ZIP_PATH="admin-portal-package.zip"   # Path to your built ZIP
PYTHON_VERSION="${PYTHON_VERSION:-3.11}"

# Create a deployment package
create_deployment_package() {
  echo "📦 Creating deployment package..."
  
  # Create a temporary directory
  mkdir -p deploy_tmp
  
  # Copy the necessary files to the temporary directory
  cp -r *.py templates static shared data deploy_tmp/ 2>/dev/null || :
  cp -r __init__.py requirements.txt deploy_tmp/ 2>/dev/null || :
  
  # Create the web.config file for Azure App Service
  cat > deploy_tmp/web.config << EOF
<?xml version="1.0" encoding="utf-8"?>
<configuration>
  <system.webServer>
    <handlers>
      <add name="PythonHandler" path="*" verb="*" modules="httpPlatformHandler" resourceType="Unspecified"/>
    </handlers>
    <httpPlatform processPath="python" arguments="-m gunicorn --bind=0.0.0.0:5000 main:app" 
                  stdoutLogEnabled="true" stdoutLogFile="\\\\?\\%home%\\LogFiles\\stdout"
                  startupTimeLimit="60"/>
  </system.webServer>
</configuration>
EOF
  
  # Create a ZIP file
  cd deploy_tmp
  zip -r ../$ZIP_PATH * >/dev/null
  cd ..
  
  # Clean up
  rm -rf deploy_tmp
  
  echo "✅ Created deployment package: $ZIP_PATH"
}

# 1) Create the deployment package
create_deployment_package

# 2) Enable "run from package" (deploys your ZIP directly, mounts it read‑only)
echo "🔧 Configuring app service settings..."
az webapp config appsettings set \
  --resource-group $RESOURCE_GROUP \
  --name $APP_NAME \
  --settings WEBSITE_RUN_FROM_PACKAGE=1

# 3) Perform zip‑deploy of your code into wwwroot
echo "🚀 Deploying application code..."
az webapp deployment source config-zip \
  --resource-group $RESOURCE_GROUP \
  --name $APP_NAME \
  --src $ZIP_PATH

# 4) (Re)apply your startup command to ensure Gunicorn is used
echo "⚙️ Configuring startup command..."
az webapp config set \
  --resource-group $RESOURCE_GROUP \
  --name $APP_NAME \
  --startup-file "gunicorn --bind=0.0.0.0:5000 main:app" \
  --linux-fx-version "PYTHON|$PYTHON_VERSION"

# 5) Restart to pick up changes
echo "🔄 Restarting the web application..."
az webapp restart \
  --resource-group $RESOURCE_GROUP \
  --name $APP_NAME

echo "✅ Deployment complete. Your Flask app should now be accessible."
echo "📝 You can view the logs with: az webapp log tail --resource-group $RESOURCE_GROUP --name $APP_NAME"