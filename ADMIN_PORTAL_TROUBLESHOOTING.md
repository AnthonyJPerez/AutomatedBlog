# Admin Portal Troubleshooting Guide

This document provides a step-by-step approach to resolve issues with the admin portal not displaying at the root URL of your Azure Function App.

## Diagnosis Tools

First, let's check what's happening with your Function App:

1. **Check the application logs**:
   ```bash
   az webapp log tail --resource-group "blogauto-prod-rg" --name "blogauto-prod-function"
   ```

2. **Examine the configuration**:
   ```bash
   az webapp config show --resource-group "blogauto-prod-rg" --name "blogauto-prod-function"
   ```

3. **Check app settings**:
   ```bash
   az webapp config appsettings list --resource-group "blogauto-prod-rg" --name "blogauto-prod-function"
   ```

4. **Check deployment status**:
   ```bash
   az webapp deployment list --resource-group "blogauto-prod-rg" --name "blogauto-prod-function"
   ```

## Resolution Options

### Option 1: Try the Fix Script (Recommended First)

Run the direct fix script which attempts to resolve common issues:

```bash
./fix-webapp-directly.sh "blogauto-prod-rg" "blogauto-prod-function"
```

This script will:
- Reset the app to a known good state
- Set a simple, direct startup command
- Configure critical app settings
- Restart the app

### Option 2: Deploy a Minimal Test App

If Option 1 doesn't work, try deploying a minimal test app to verify the basic configuration:

```bash
./deploy-minimal-test.sh "blogauto-prod-rg" "blogauto-prod-function"
```

This will deploy a very simple Flask application that should work with minimal configuration.

### Option 3: Deploy a Static Test Page

If the minimal Flask app doesn't work, try deploying a static HTML test page:

```bash
./deploy-static-test.sh "blogauto-prod-rg" "blogauto-prod-function"
```

This will deploy a simple static HTML page that should render even without Python/Flask working correctly.

## Manual Configuration Steps

If none of the scripts work, you can try these manual steps:

### Step 1: Convert to a Web App (not a Function App)

```bash
az resource update --resource-group "blogauto-prod-rg" --name "blogauto-prod-function" \
    --resource-type "Microsoft.Web/sites" --set kind="app,linux" --api-version "2021-02-01"
```

### Step 2: Set a Direct Startup Command

```bash
az webapp config set --resource-group "blogauto-prod-rg" --name "blogauto-prod-function" \
    --startup-file "python -m flask run --host=0.0.0.0 --port=8000"
```

### Step 3: Configure Essential App Settings

```bash
az webapp config appsettings set --resource-group "blogauto-prod-rg" --name "blogauto-prod-function" \
    --settings \
    FLASK_APP=main.py \
    WEBSITES_PORT=8000 \
    PORT=8000 \
    SCM_DO_BUILD_DURING_DEPLOYMENT=true
```

### Step 4: Stop and Start the App

```bash
az webapp stop --resource-group "blogauto-prod-rg" --name "blogauto-prod-function"
sleep 5
az webapp start --resource-group "blogauto-prod-rg" --name "blogauto-prod-function"
```

## Create a Simple main.py for Testing

If you suspect the issue might be with your Flask application code, replace your main.py with this simplified version to test:

```python
from flask import Flask

app = Flask(__name__)

@app.route('/')
def home():
    return """
    <html>
    <head><title>Admin Portal Test</title></head>
    <body>
        <h1>Admin Portal Test</h1>
        <p>If you can see this, the admin portal is working correctly!</p>
    </body>
    </html>
    """

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000, debug=True)
```

## Direct Access to Kudu Console

For advanced troubleshooting, access the Kudu console:

```
https://blogauto-prod-function.scm.azurewebsites.net/DebugConsole
```

From here you can:
- Browse the file system to verify deployed files
- Check log files in LogFiles directory
- Run commands to diagnose issues

## Last Resort: Create a New Web App

If all else fails, consider creating a dedicated Web App (not a Function App) for the admin portal:

```bash
az webapp create --resource-group "blogauto-prod-rg" --name "blogauto-prod-admin" \
    --runtime "PYTHON:3.11" --plan "blogauto-prod-plan"
```

Then deploy your admin portal to this dedicated web app instead of trying to host it in the Function App.