#!/bin/bash
# deploy-admin-portal.sh
# Script to deploy the admin portal to an existing Azure Function App
# Usage: ./deploy-admin-portal.sh <resource-group-name> <function-app-name>

if [ $# -lt 2 ]; then
    echo "Usage: $0 <resource-group-name> <function-app-name>"
    exit 1
fi

RESOURCE_GROUP=$1
FUNCTION_APP_NAME=$2

echo "====================================================="
echo "DEPLOYING ADMIN PORTAL TO AZURE FUNCTION APP"
echo "Resource Group: $RESOURCE_GROUP"
echo "App Name: $FUNCTION_APP_NAME"
echo "====================================================="

# Create a temporary deployment package directory
TEMP_DIR=$(mktemp -d)
echo "Creating deployment package in: $TEMP_DIR"

# Prepare web.config for the admin portal
cat > $TEMP_DIR/web.config << EOF
<?xml version="1.0" encoding="utf-8"?>
<configuration>
  <system.webServer>
    <handlers>
      <add name="PythonHandler" path="*" verb="*" modules="FastCgiModule" scriptProcessor="D:\Program Files\Python\3.11\python.exe|D:\Program Files\Python\3.11\Lib\site-packages\wfastcgi.py" resourceType="Unspecified" requireAccess="Script" />
    </handlers>
    <fastCgi>
      <application fullPath="D:\Program Files\Python\3.11\python.exe" arguments="D:\Program Files\Python\3.11\Lib\site-packages\wfastcgi.py">
        <environmentVariables>
          <environmentVariable name="PYTHONPATH" value="D:\home\site\wwwroot" />
          <environmentVariable name="WSGI_HANDLER" value="wsgi.application" />
        </environmentVariables>
      </application>
    </fastCgi>
    <rewrite>
      <rules>
        <rule name="LowerCaseUrls" stopProcessing="true">
          <match url="[A-Z]" ignoreCase="false" />
          <action type="Redirect" url="{ToLower:{URL}}" />
        </rule>
      </rules>
    </rewrite>
    <httpErrors errorMode="DetailedLocalOnly" existingResponse="Auto">
      <clear />
      <error statusCode="404" path="404.html" responseMode="File" />
      <error statusCode="500" path="500.html" responseMode="File" />
    </httpErrors>
  </system.webServer>
  <appSettings>
    <add key="PYTHONPATH" value="D:\home\site\wwwroot" />
    <add key="WSGI_HANDLER" value="wsgi.application" />
    <add key="WSGI_LOG" value="D:\home\LogFiles\application.log" />
  </appSettings>
</configuration>
EOF

# Create wsgi.py file with fallback mechanism
cat > $TEMP_DIR/wsgi.py << EOF
#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import sys
import logging
import traceback

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(os.path.join(os.environ.get('HOME', '.'), 'LogFiles', 'application.log'))
    ]
)

logger = logging.getLogger('wsgi')
logger.info("WSGI script starting up")

# Add the current directory to the path
script_dir = os.path.dirname(os.path.abspath(__file__))
if script_dir not in sys.path:
    sys.path.insert(0, script_dir)

# Try multiple different app imports to handle various configurations
application = None

try:
    logger.info("Trying to import from main as app")
    from main import app as application
    logger.info("Successfully imported app from main")
except Exception as e:
    error_message = str(e)
    traceback_message = traceback.format_exc()
    logger.error(f"Failed to import from main as app: {error_message}")
    logger.error(f"Traceback: {traceback_message}")

    try:
        logger.info("Trying to import from app as app")
        from app import app as application
        logger.info("Successfully imported app from app")
    except Exception as e:
        error_message = str(e)
        traceback_message = traceback.format_exc()
        logger.error(f"Failed to import from app as app: {error_message}")
        logger.error(f"Traceback: {traceback_message}")

        try:
            logger.info("Trying to import from minimal_app as app")
            from minimal_app import app as application
            logger.info("Successfully imported app from minimal_app")
        except Exception as e:
            error_message = str(e)
            traceback_message = traceback.format_exc()
            logger.error(f"Failed to import from minimal_app as app: {error_message}")
            logger.error(f"Traceback: {traceback_message}")

            # Create a fallback application if all else fails
            logger.warning("All imports failed, creating fallback application")
            from flask import Flask, render_template_string

            fallback_app = Flask(__name__)

            @fallback_app.route('/')
            def home():
                return render_template_string("""
                <!DOCTYPE html>
                <html>
                <head>
                    <title>Admin Portal - Fallback Mode</title>
                    <style>
                        body { font-family: Arial, sans-serif; margin: 40px; line-height: 1.6; }
                        h1 { color: #cc0000; }
                        .container { border: 1px solid #ddd; padding: 20px; border-radius: 5px; }
                        .error { color: #cc0000; background-color: #ffeeee; padding: 15px; border-radius: 5px; margin-bottom: 20px; }
                        pre { background-color: #f5f5f5; padding: 10px; border-radius: 5px; overflow-x: auto; }
                    </style>
                </head>
                <body>
                    <h1>Admin Portal - Fallback Mode</h1>
                    
                    <div class="error">
                        <strong>Error:</strong> The admin portal application could not be loaded.
                    </div>
                    
                    <div class="container">
                        <h2>Troubleshooting Information</h2>
                        <p>The WSGI script was unable to import the Flask application. Check the following:</p>
                        <ul>
                            <li>Is main.py present in the root directory?</li>
                            <li>Does main.py define an 'app' variable?</li>
                            <li>Are all required dependencies installed?</li>
                        </ul>
                        
                        <h3>Log Files</h3>
                        <p>Check the logs at D:\\home\\LogFiles\\application.log for more details.</p>
                    </div>
                </body>
                </html>
                """)

            application = fallback_app

if not application:
    logger.critical("Failed to create any application, WSGI will fail")
    raise ImportError("Could not import or create a Flask application")

# Final success log
logger.info("WSGI script successfully configured application")
EOF

# Create a startup.sh file to ensure wfastcgi is installed
cat > $TEMP_DIR/startup.sh << EOF
#!/bin/bash
# startup.sh - Runs on Azure App Service during container startup

echo "Installing wfastcgi and gunicorn for Flask hosting..."
python -m pip install wfastcgi gunicorn flask

echo "Running application with gunicorn..."
gunicorn --bind=0.0.0.0:8000 --timeout 600 wsgi:application
EOF

# Create a simple fallback main.py (if no other exists)
cat > $TEMP_DIR/minimal_app.py << EOF
from flask import Flask, render_template_string

app = Flask(__name__)

@app.route('/')
def home():
    return render_template_string("""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Minimal Admin Portal</title>
        <style>
            body { font-family: Arial, sans-serif; margin: 40px; line-height: 1.6; }
            h1 { color: #0066cc; }
            .container { border: 1px solid #ddd; padding: 20px; border-radius: 5px; }
            .success { color: green; background-color: #e7f9e7; padding: 15px; border-radius: 5px; margin-bottom: 20px; }
        </style>
    </head>
    <body>
        <h1>Minimal Admin Portal</h1>
        
        <div class="success">
            <strong>Success!</strong> The minimal admin portal is working.
        </div>
        
        <div class="container">
            <h2>Next Steps</h2>
            <p>Now that the minimal app is working, you should:</p>
            <ol>
                <li>Make sure your main.py file is properly structured</li>
                <li>Check all required dependencies are in requirements.txt</li>
                <li>Deploy your full admin portal code</li>
            </ol>
        </div>
    </body>
    </html>
    """)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000, debug=True)
EOF

# Create or update requirements.txt
cat > $TEMP_DIR/requirements.txt << EOF
flask>=2.0.0
gunicorn>=20.1.0
wfastcgi>=3.0.0
python-dotenv>=0.19.0
EOF

# Create 404.html
cat > $TEMP_DIR/404.html << EOF
<!DOCTYPE html>
<html>
<head>
    <title>404 - Page Not Found</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 40px; line-height: 1.6; text-align: center; }
        h1 { color: #0066cc; }
        .container { border: 1px solid #ddd; padding: 20px; border-radius: 5px; max-width: 600px; margin: 0 auto; }
    </style>
</head>
<body>
    <h1>404 - Page Not Found</h1>
    
    <div class="container">
        <p>The page you requested could not be found.</p>
        <p><a href="/">Return to Dashboard</a></p>
    </div>
</body>
</html>
EOF

# Create 500.html
cat > $TEMP_DIR/500.html << EOF
<!DOCTYPE html>
<html>
<head>
    <title>500 - Server Error</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 40px; line-height: 1.6; text-align: center; }
        h1 { color: #cc0000; }
        .container { border: 1px solid #ddd; padding: 20px; border-radius: 5px; max-width: 600px; margin: 0 auto; }
    </style>
</head>
<body>
    <h1>500 - Server Error</h1>
    
    <div class="container">
        <p>The server encountered an internal error and was unable to complete your request.</p>
        <p>Please try again later or contact the administrator.</p>
        <p><a href="/">Return to Dashboard</a></p>
    </div>
</body>
</html>
EOF

# Configure the app as a web app (not a function app)
echo "Configuring app as web app..."
az resource update --resource-group $RESOURCE_GROUP --name $FUNCTION_APP_NAME \
    --resource-type "Microsoft.Web/sites" --set kind="app,linux" --api-version "2021-02-01"

# Configure required app settings
echo "Configuring app settings..."
az webapp config appsettings set --resource-group $RESOURCE_GROUP --name $FUNCTION_APP_NAME \
    --settings \
    FLASK_APP=main.py \
    WEBSITES_PORT=8000 \
    PORT=8000 \
    SCM_DO_BUILD_DURING_DEPLOYMENT=true \
    WSGI_LOG=D:\\home\\LogFiles\\application.log

# Configure the startup command
echo "Setting startup command..."
az webapp config set --resource-group $RESOURCE_GROUP --name $FUNCTION_APP_NAME \
    --startup-file "gunicorn --bind=0.0.0.0:8000 --timeout 600 wsgi:application"

# Deploy the app using ZIP deployment
echo "Deploying admin portal files via ZIP..."
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

echo "====================================================="
echo "ADMIN PORTAL DEPLOYMENT COMPLETE"
echo "Now visit: https://$FUNCTION_APP_NAME.azurewebsites.net/"
echo "You should see your admin portal or the fallback minimal app."
echo "====================================================="