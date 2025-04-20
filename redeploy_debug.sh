#!/bin/bash
#
# Helper script to redeploy the admin portal in debug mode to Azure
#

# Configuration
RESOURCE_GROUP=${1:-"blogauto-prod-rg"}
WEBAPP_NAME=${2:-"blogauto-prod-admin"}

echo "Preparing debug deployment for $WEBAPP_NAME in $RESOURCE_GROUP"

# Create a temporary directory for the deployment package
TEMP_DIR=$(mktemp -d)
echo "Using temporary directory: $TEMP_DIR"

# Copy necessary files to the temp dir
echo "Copying debug files..."
cp admin_portal_debug.py $TEMP_DIR/
cp web.config $TEMP_DIR/
cp wsgi.py $TEMP_DIR/
cp minimal_app.py $TEMP_DIR/
cp main.py $TEMP_DIR/
cp -r static $TEMP_DIR/ 2>/dev/null || mkdir -p $TEMP_DIR/static
cp -r templates $TEMP_DIR/ 2>/dev/null || mkdir -p $TEMP_DIR/templates
mkdir -p $TEMP_DIR/data

# Create a simple requirements.txt
cat > $TEMP_DIR/requirements.txt << EOF
flask==2.0.3
gunicorn==20.1.0
python-dotenv==0.21.1
werkzeug==2.0.3
requests==2.29.0
EOF

# Create a simple test template
mkdir -p $TEMP_DIR/templates
cat > $TEMP_DIR/templates/index.html << EOF
<!DOCTYPE html>
<html>
<head>
    <title>Admin Portal Test Page</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; }
        h1 { color: #333; }
        .info { background-color: #f8f9fa; padding: 15px; border: 1px solid #ddd; }
    </style>
</head>
<body>
    <h1>Admin Portal Test Page</h1>
    <div class="info">
        <p>This is a test page for the admin portal.</p>
        <p>If you can see this page, Flask is working correctly.</p>
        <p>Diagnostic URLs:</p>
        <ul>
            <li><a href="/debug">Debug Information</a></li>
            <li><a href="/minimal">Minimal Test Page</a></li>
            <li><a href="/run-diagnostics">Run Diagnostics</a></li>
        </ul>
    </div>
</body>
</html>
EOF

# Create a debug WSGI file
cat > $TEMP_DIR/debug_wsgi.py << EOF
#!/usr/bin/env python
import os
import sys
from datetime import datetime

# Add the current directory to the path
sys.path.insert(0, os.path.dirname(__file__))

def application(environ, start_response):
    """WSGI application function for debugging"""
    path_info = environ.get('PATH_INFO', '/')
    
    if path_info == '/debug':
        # Return debug information as plain text
        status = '200 OK'
        headers = [('Content-Type', 'text/plain; charset=utf-8')]
        start_response(status, headers)
        
        debug_info = [
            "Admin Portal Debug Information",
            f"Timestamp: {datetime.now().isoformat()}",
            f"Python Version: {sys.version}",
            f"WSGI environ variables:",
        ]
        
        # Add environ variables
        for key, value in sorted(environ.items()):
            if not any(secret in key.lower() for secret in ['key', 'password', 'secret']):
                debug_info.append(f"  {key}: {value}")
        
        # Add system path information
        debug_info.append("Python sys.path:")
        for path in sys.path:
            debug_info.append(f"  {path}")
        
        return [line.encode('utf-8') + b'\\n' for line in debug_info]
    
    elif path_info == '/minimal':
        # Return a simple HTML page for minimal testing
        status = '200 OK'
        headers = [('Content-Type', 'text/html; charset=utf-8')]
        start_response(status, headers)
        
        html = f"""<!DOCTYPE html>
<html>
<head>
    <title>Minimal Debug Page</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; }}
        h1 {{ color: #333; }}
        .info {{ background-color: #f8f9fa; padding: 15px; border: 1px solid #ddd; }}
    </style>
</head>
<body>
    <h1>Minimal Debug Page</h1>
    <div class="info">
        <p>This is a minimal debug page to check if the WSGI application is working.</p>
        <p>Current time: {datetime.now().isoformat()}</p>
        <p>Python version: {sys.version}</p>
        <p>Testing URLs:</p>
        <ul>
            <li><a href="/debug">Debug Information</a></li>
            <li><a href="/minimal">This Minimal Page</a></li>
        </ul>
    </div>
</body>
</html>"""
        
        return [html.encode('utf-8')]
    
    else:
        # Try to import and use the minimal app
        try:
            # Try to import the Flask application
            from minimal_app import app as flask_app
            
            # Create a WSGI callable from the Flask app
            return flask_app.wsgi_app(environ, start_response)
        except Exception as e:
            # If that fails, return an error page
            status = '500 Internal Server Error'
            headers = [('Content-Type', 'text/html; charset=utf-8')]
            start_response(status, headers)
            
            error_html = f"""<!DOCTYPE html>
<html>
<head>
    <title>Admin Portal Error</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; color: #333; }}
        h1 {{ color: #d9534f; }}
        .error {{ background-color: #f8d7da; padding: 15px; border: 1px solid #f5c6cb; }}
        .info {{ background-color: #f8f9fa; padding: 15px; border: 1px solid #ddd; }}
    </style>
</head>
<body>
    <h1>Admin Portal Error</h1>
    <div class="error">
        <p>The application could not be loaded due to an error:</p>
        <pre>{str(e)}</pre>
    </div>
    <div class="info">
        <p>Diagnostic URLs:</p>
        <ul>
            <li><a href="/debug">Debug Information</a></li>
            <li><a href="/minimal">Minimal Test Page</a></li>
        </ul>
    </div>
</body>
</html>"""
            
            return [error_html.encode('utf-8')]

if __name__ == '__main__':
    # Start a simple HTTP server
    from wsgiref.simple_server import make_server
    httpd = make_server('0.0.0.0', int(os.environ.get('PORT', 5000)), application)
    print(f"Serving on port {os.environ.get('PORT', 5000)}...")
    httpd.serve_forever()
EOF

# Create a simple minimal Flask app
cat > $TEMP_DIR/minimal_app.py << EOF
#!/usr/bin/env python
import os
from datetime import datetime
from flask import Flask, render_template_string, jsonify

app = Flask(__name__)

@app.route('/')
def index():
    html = """<!DOCTYPE html>
<html>
<head>
    <title>Admin Portal - Minimal Test</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; }
        h1 { color: #333; }
        .info { background-color: #f8f9fa; padding: 15px; border: 1px solid #ddd; }
    </style>
</head>
<body>
    <h1>Admin Portal - Minimal Test</h1>
    <div class="info">
        <p>If you can see this page, the minimal Flask app is working.</p>
        <p>Next steps:</p>
        <ul>
            <li>Check the <a href="/api/status">API Status</a> endpoint</li>
            <li>Review the full application logs</li>
            <li>Deploy the complete application once this test succeeds</li>
        </ul>
    </div>
</body>
</html>"""
    return render_template_string(html)

@app.route('/api/status')
def status():
    return jsonify({
        'status': 'ok',
        'python_version': os.environ.get('PYTHON_VERSION', 'Unknown'),
        'app_name': os.environ.get('WEBSITE_SITE_NAME', 'Unknown'),
        'timestamp': str(datetime.now())
    })

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
EOF

# Create a zip package for deployment
echo "Creating deployment package..."
cd $TEMP_DIR
zip -r admin-portal-debug.zip ./*

# Deploy the package to Azure
echo "Deploying to Azure App Service..."
az webapp deployment source config-zip \
  --resource-group "$RESOURCE_GROUP" \
  --name "$WEBAPP_NAME" \
  --src ./admin-portal-debug.zip

# Configure the web app to use the debug WSGI application
echo "Configuring web app settings..."
az webapp config set \
  --resource-group "$RESOURCE_GROUP" \
  --name "$WEBAPP_NAME" \
  --startup-file "gunicorn --bind=0.0.0.0:5000 debug_wsgi:application"

# Set app settings for debugging
echo "Setting app settings for debugging..."
az webapp config appsettings set \
  --resource-group "$RESOURCE_GROUP" \
  --name "$WEBAPP_NAME" \
  --settings \
  FLASK_APP="minimal_app.py" \
  FLASK_ENV="development" \
  SCM_DO_BUILD_DURING_DEPLOYMENT="true" \
  DEBUG_MODE="true"

# Restart the web app
echo "Restarting the web app..."
az webapp restart \
  --resource-group "$RESOURCE_GROUP" \
  --name "$WEBAPP_NAME"

# Clean up
echo "Cleaning up temporary files..."
rm -rf $TEMP_DIR

echo "Deployment complete!"
echo "Wait a moment for the app to start, then visit:"
echo "https://$WEBAPP_NAME.azurewebsites.net/"
echo "Debug information: https://$WEBAPP_NAME.azurewebsites.net/debug"
echo "Minimal page: https://$WEBAPP_NAME.azurewebsites.net/minimal"