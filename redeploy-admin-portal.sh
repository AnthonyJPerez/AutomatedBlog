#!/bin/bash
# Script to redeploy the admin portal with proper Poetry configuration
# This addresses the Kudu deployment errors related to missing [tool.poetry] section

# Set variables based on environment
ENVIRONMENT="${1:-prod}"  # Default to prod if not specified
RESOURCE_GROUP="blogauto-${ENVIRONMENT}-rg"
ADMIN_PORTAL_NAME="blogauto-${ENVIRONMENT}-admin"

# Echo current settings
echo "Redeploying admin portal with proper Poetry configuration"
echo "Environment: $ENVIRONMENT"
echo "Resource Group: $RESOURCE_GROUP"
echo "Admin Portal: $ADMIN_PORTAL_NAME"

# First, ensure we're logged in to Azure
echo "Checking Azure login status..."
az account show &> /dev/null
if [ $? -ne 0 ]; then
  echo "ERROR: Not logged in to Azure. Please run 'az login' first."
  exit 1
fi

# Copy Poetry-compatible pyproject.toml and requirements.txt to a temporary location
echo "Preparing deployment files..."
TEMP_DIR=$(mktemp -d)
cp deployment-templates/pyproject.toml $TEMP_DIR/
cp deployment-templates/requirements.txt $TEMP_DIR/
cp deployment-templates/main.py $TEMP_DIR/
cp deployment-templates/wsgi.py $TEMP_DIR/

# Create a minimal templates directory if it doesn't exist in the deployment templates
if [ ! -d "deployment-templates/templates" ]; then
  mkdir -p $TEMP_DIR/templates
  echo "Creating minimal index.html template..."
  cat > $TEMP_DIR/templates/index.html << 'EOF'
<!doctype html>
<html>
<head>
  <title>{{ title }}</title>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css">
</head>
<body class="bg-dark text-light">
  <div class="container py-5">
    <h1>Blog Automation Admin Portal</h1>
    <p class="lead">The admin portal is being configured.</p>
    <div class="alert alert-success">
      Server is running. Deployment was successful.
    </div>
  </div>
  <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
</body>
</html>
EOF
else
  mkdir -p $TEMP_DIR/templates
  cp -r deployment-templates/templates/* $TEMP_DIR/templates/
fi

# Create a zip file for deployment
echo "Creating deployment zip file..."
cd $TEMP_DIR
zip -r deploy.zip ./*
cd - > /dev/null

# Check if the admin portal exists
echo "Checking if admin portal exists..."
PORTAL_EXISTS=$(az webapp show --name $ADMIN_PORTAL_NAME --resource-group $RESOURCE_GROUP &> /dev/null && echo "yes" || echo "no")

if [ "$PORTAL_EXISTS" == "yes" ]; then
  # Deploy using the zip file
  echo "Deploying files to admin portal..."
  az webapp deployment source config-zip --resource-group $RESOURCE_GROUP --name $ADMIN_PORTAL_NAME --src $TEMP_DIR/deploy.zip
  
  # Restart the web app
  echo "Restarting the admin portal..."
  az webapp restart --resource-group $RESOURCE_GROUP --name $ADMIN_PORTAL_NAME
  
  echo "Deployment completed. The admin portal should be accessible at: https://$ADMIN_PORTAL_NAME.azurewebsites.net/"
else
  echo "ERROR: Admin portal '$ADMIN_PORTAL_NAME' not found in resource group '$RESOURCE_GROUP'."
  echo "Please check the name and resource group or deploy the infrastructure first."
  exit 1
fi

# Clean up
echo "Cleaning up temporary files..."
rm -rf $TEMP_DIR

echo "Done!"