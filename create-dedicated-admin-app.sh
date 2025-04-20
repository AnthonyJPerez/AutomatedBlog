#!/bin/bash
# create-dedicated-admin-app.sh
# Creates a totally separate, dedicated web app just for the admin portal
# Usage: ./create-dedicated-admin-app.sh <resource-group-name> <app-service-plan> <admin-app-name>

if [ $# -lt 3 ]; then
    echo "Usage: $0 <resource-group-name> <app-service-plan> <admin-app-name>"
    echo "Example: $0 blogauto-prod-rg blogauto-prod-plan blogauto-prod-admin"
    exit 1
fi

RESOURCE_GROUP=$1
APP_SERVICE_PLAN=$2
ADMIN_APP_NAME=$3

echo "====================================================="
echo "CREATING DEDICATED ADMIN PORTAL WEB APP"
echo "Resource Group: $RESOURCE_GROUP"
echo "App Service Plan: $APP_SERVICE_PLAN"
echo "Admin App Name: $ADMIN_APP_NAME"
echo "====================================================="

# Create a web app (not a function app)
echo "Creating dedicated web app for admin portal..."
az webapp create \
  --resource-group $RESOURCE_GROUP \
  --plan $APP_SERVICE_PLAN \
  --name $ADMIN_APP_NAME \
  --runtime "PYTHON:3.11"

# Configure the web app
echo "Configuring web app settings..."
az webapp config appsettings set \
  --resource-group $RESOURCE_GROUP \
  --name $ADMIN_APP_NAME \
  --settings \
  FLASK_APP=main.py \
  WEBSITES_PORT=8000 \
  SCM_DO_BUILD_DURING_DEPLOYMENT=true \
  FLASK_ENV=production

# Set the startup command
echo "Setting startup command..."
az webapp config set \
  --resource-group $RESOURCE_GROUP \
  --name $ADMIN_APP_NAME \
  --startup-file "python -m flask run --host=0.0.0.0 --port=8000"

# Create a temporary deployment package directory
TEMP_DIR=$(mktemp -d)
echo "Creating deployment package in: $TEMP_DIR"

# Copy necessary files to the temp directory - this is where you'd copy your admin portal files
# For now, we'll create a minimal Flask app for testing
cat > $TEMP_DIR/main.py << EOF
from flask import Flask, render_template_string

app = Flask(__name__)

@app.route('/')
def home():
    return render_template_string("""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Dedicated Admin Portal</title>
        <style>
            body { font-family: Arial, sans-serif; margin: 40px; line-height: 1.6; }
            h1 { color: #0066cc; }
            .container { border: 1px solid #ddd; padding: 20px; border-radius: 5px; }
            .success { color: green; background-color: #e7f9e7; padding: 15px; border-radius: 5px; margin-bottom: 20px; }
        </style>
    </head>
    <body>
        <h1>Dedicated Admin Portal</h1>
        
        <div class="success">
            <strong>Success!</strong> The dedicated admin portal web app is working.
        </div>
        
        <div class="container">
            <h2>Next Steps</h2>
            <p>Now that we have a dedicated admin portal web app, you should:</p>
            <ol>
                <li>Deploy your full admin portal code to this app</li>
                <li>Update any references from the function app to point to this new admin portal URL</li>
                <li>Consider setting up a custom domain for this admin portal</li>
            </ol>
        </div>
    </body>
    </html>
    """)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000, debug=True)
EOF

# Create simple requirements.txt
cat > $TEMP_DIR/requirements.txt << EOF
flask==2.0.1
gunicorn==20.1.0
EOF

# Deploy the app using ZIP deployment
echo "Deploying application via ZIP..."
cd $TEMP_DIR
zip -r app.zip ./*
az webapp deployment source config-zip \
  --resource-group $RESOURCE_GROUP \
  --name $ADMIN_APP_NAME \
  --src app.zip

# Clean up
cd -
rm -rf $TEMP_DIR

# Restart the app
echo "Restarting app..."
az webapp restart --resource-group $RESOURCE_GROUP --name $ADMIN_APP_NAME

# Wait a moment
echo "Waiting 15 seconds for app to initialize..."
sleep 15

# Get the URL
ADMIN_URL="https://$ADMIN_APP_NAME.azurewebsites.net/"

echo "====================================================="
echo "DEDICATED ADMIN PORTAL CREATED SUCCESSFULLY"
echo "Your admin portal is now available at: $ADMIN_URL"
echo ""
echo "The next step is to deploy your full admin portal code to this app."
echo "This approach completely separates your admin portal from your Function App,"
echo "avoiding the complexity of serving a web app from a Function App."
echo "====================================================="