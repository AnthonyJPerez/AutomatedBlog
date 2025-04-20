#!/bin/bash
# direct-fix.sh
# Last resort approach to get at least a static page displayed
# Usage: ./direct-fix.sh <resource-group-name> <function-app-name>

if [ $# -lt 2 ]; then
    echo "Usage: $0 <resource-group-name> <function-app-name>"
    exit 1
fi

RESOURCE_GROUP=$1
FUNCTION_APP_NAME=$2

echo "====================================================="
echo "EXECUTING DIRECT FIX FOR AZURE APP SERVICE"
echo "Resource Group: $RESOURCE_GROUP"
echo "App Name: $FUNCTION_APP_NAME"
echo "====================================================="

# Create a temp file for basic HTML
cat > hostingstart.html << EOF
<!DOCTYPE html>
<html>
<head>
    <title>Admin Portal - Direct Fix</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 40px; line-height: 1.6; }
        h1 { color: #0066cc; }
        .container { border: 1px solid #ddd; padding: 20px; border-radius: 5px; }
        .success { color: green; background-color: #e7f9e7; padding: 15px; border-radius: 5px; margin-bottom: 20px; }
    </style>
</head>
<body>
    <h1>Admin Portal - Direct Fix</h1>
    
    <div class="success">
        <strong>Success!</strong> If you're seeing this page, the direct fix worked. This confirms that Azure App Service can serve static content.
    </div>
    
    <div class="container">
        <h2>Next Steps</h2>
        <p>Now that we know static content works, we can address the Flask application configuration:</p>
        <ol>
            <li>Check <code>https://${FUNCTION_APP_NAME}.scm.azurewebsites.net/DebugConsole</code> to explore files</li>
            <li>Look at the app settings in the Azure Portal</li>
            <li>Review the startup command configuration</li>
        </ol>
        
        <h3>Project Links</h3>
        <ul>
            <li><a href="/admin">Try accessing /admin directly</a></li>
            <li><a href="/api">Try accessing /api directly</a></li>
            <li><a href="/index">Try accessing /index directly</a></li>
        </ul>
    </div>
</body>
</html>
EOF

# Upload the file via FTP
echo "Uploading hostingstart.html directly..."
PUBLISH_PROFILE=$(az webapp deployment list-publishing-profiles \
  --resource-group $RESOURCE_GROUP \
  --name $FUNCTION_APP_NAME \
  --query "[?publishMethod=='FTP'].{publishUrl:publishUrl,userName:userName,userPWD:userPWD}[0]" -o json)

FTP_URL=$(echo $PUBLISH_PROFILE | jq -r '.publishUrl')
FTP_USER=$(echo $PUBLISH_PROFILE | jq -r '.userName')
FTP_PASS=$(echo $PUBLISH_PROFILE | jq -r '.userPWD')

# Remove ftp:// prefix if present
FTP_URL=${FTP_URL#ftp://}

echo "Uploading to FTP: $FTP_URL with user: $FTP_USER"

# Create a basic .netrc file for FTP credentials
cat > .netrc << EOF
machine $FTP_URL
login $FTP_USER
password $FTP_PASS
EOF

chmod 600 .netrc

# Ensure curl is installed
command -v curl >/dev/null 2>&1 || { echo "Error: curl is required but not installed. Trying to install..."; apt-get update && apt-get install -y curl; }

# Upload the file
echo "Uploading file via FTP..."
curl -T hostingstart.html -u "$FTP_USER:$FTP_PASS" "ftp://$FTP_URL/site/wwwroot/hostingstart.html" --ssl

# Configure app settings
echo "Setting critical app settings..."
az webapp config appsettings set --resource-group $RESOURCE_GROUP --name $FUNCTION_APP_NAME \
  --settings WEBSITE_WEBDEPLOY_USE_SCM=false

# Configure Azure to use hostingstart.html
echo "Configuring to use hostingstart.html as the default document..."
az webapp config set --resource-group $RESOURCE_GROUP --name $FUNCTION_APP_NAME \
  --generic-configurations "{'defaultDocuments': ['hostingstart.html','index.html','default.htm']}"

# Configure the direct approach - make this file the default hostingstart file
echo "Setting special Azure system variable..."
az webapp config appsettings set --resource-group $RESOURCE_GROUP --name $FUNCTION_APP_NAME \
  --settings WEBSITE_HOSTNAME_REWRITE_ENABLED=0

# Stop the app
echo "Stopping the app..."
az webapp stop --resource-group $RESOURCE_GROUP --name $FUNCTION_APP_NAME

# Start the app
echo "Starting the app..."
az webapp start --resource-group $RESOURCE_GROUP --name $FUNCTION_APP_NAME

# Clean up temp files
rm -f hostingstart.html .netrc

echo "====================================================="
echo "DIRECT FIX COMPLETED"
echo "Now visit: https://$FUNCTION_APP_NAME.azurewebsites.net/"
echo "You should see the direct fix confirmation page."
echo "====================================================="