# Admin Portal Deployment Troubleshooting Guide

This document provides information about how the admin portal for the blog automation system is deployed and how to troubleshoot common issues.

## Deployment Process Overview

The admin portal is deployed as a Python Flask application to an Azure App Service (Linux) using the following steps:

1. A dedicated App Service is created via Bicep infrastructure templates
2. The application is deployed via GitHub Actions using the official Azure WebApps deploy action
3. Oryx builder automatically installs dependencies from requirements.txt
4. Gunicorn is used as the WSGI server to run the Flask application

## Key Configuration Principles

### Use Linux App Service Configuration

App Service for Python applications should always use Linux, as Windows is no longer a supported platform for Python applications on App Service.

### Enable Oryx Builder

Oryx is the build system that automatically detects your app type and installs dependencies. It's enabled by setting:
- `SCM_DO_BUILD_DURING_DEPLOYMENT=true`

### Correct File Structure

The deployment package should include:
- `main.py` - Contains the Flask application (app = Flask(__name__))
- `wsgi.py` - Entry point for Gunicorn
- `requirements.txt` - Lists all Python dependencies
- `/templates` and `/static` - Directories for Flask templates and static files

### Proper Startup Command 

For a Flask application, the recommended startup command is:
```
gunicorn --bind=0.0.0.0:8000 --timeout 600 wsgi:application
```

## Common Deployment Issues

### 1. Web App Shows Default "hostingstart.html" Page

**Problem**: After deployment, the web app still shows the default Azure "Your App Service app is up and running" page.

**Causes**:
- Deployment didn't properly extract files
- Gunicorn isn't starting correctly

**Solution**:
- Ensure the deployment is using the official webapps-deploy action
- Check the startup command is correctly set
- Verify SCM_DO_BUILD_DURING_DEPLOYMENT is set to true

### 2. ModuleNotFoundError or Import Errors

**Problem**: The application crashes with module import errors.

**Causes**:
- Dependencies weren't installed by Oryx
- PYTHONPATH is incorrect
- requirements.txt is missing or improperly formatted

**Solution**:
- Place requirements.txt at the root of your deployment package
- Ensure SCM_DO_BUILD_DURING_DEPLOYMENT=true
- Check the logs for any installation errors

### 3. Application Shows Error 500

**Problem**: The web app returns HTTP 500 errors.

**Causes**:
- Flask application failed to start
- Errors in application code
- Missing environment variables

**Solution**:
- Check application logs
```bash
az webapp log tail --resource-group "blogauto-prod-rg" --name "blogauto-prod-admin"
```
- Verify environment variables are set correctly
- Debug any code errors

## Troubleshooting Steps

### 1. View Live Logs

```bash
az webapp log tail --resource-group "blogauto-prod-rg" --name "blogauto-prod-admin"
```

### 2. Check Application Settings

```bash
az webapp config appsettings list --resource-group "blogauto-prod-rg" --name "blogauto-prod-admin" --output table
```

### 3. Verify Deployment Status

```bash
az webapp deployment list --resource-group "blogauto-prod-rg" --name "blogauto-prod-admin" --output table
```

### 4. Check Current Configuration

```bash
az webapp config show --resource-group "blogauto-prod-rg" --name "blogauto-prod-admin" --output table
```

### 5. Verify Files with Kudu Console

1. Navigate to https://blogauto-prod-admin.scm.azurewebsites.net/
2. Go to Debug Console > PowerShell
3. Check the contents of site/wwwroot

### 6. Restart the Web App

```bash
az webapp restart --resource-group "blogauto-prod-rg" --name "blogauto-prod-admin"
```

## Essential Settings for Python Apps on Linux

### Required Application Settings

```bash
az webapp config appsettings set \
  --resource-group "blogauto-prod-rg" \
  --name "blogauto-prod-admin" \
  --settings \
  SCM_DO_BUILD_DURING_DEPLOYMENT=true \
  WEBSITES_ENABLE_APP_SERVICE_STORAGE=true \
  FLASK_APP=main.py
```

### Setting the Linux Python Runtime

```bash
az webapp config set \
  --resource-group "blogauto-prod-rg" \
  --name "blogauto-prod-admin" \
  --linux-fx-version "PYTHON|3.11"
```

### Setting the Startup Command

```bash
az webapp config set \
  --resource-group "blogauto-prod-rg" \
  --name "blogauto-prod-admin" \
  --startup-command "gunicorn --bind=0.0.0.0:8000 --timeout 600 wsgi:application"
```

## Manual Deployment Steps

If GitHub Actions deployment is failing, you can use the Azure CLI to deploy manually:

1. Create a deployment package
```bash
zip -r app.zip main.py wsgi.py requirements.txt templates/ static/ src/
```

2. Deploy using the ZIP deploy API
```bash
az webapp deployment source config-zip \
  --resource-group "blogauto-prod-rg" \
  --name "blogauto-prod-admin" \
  --src app.zip
```

3. Configure the startup command
```bash
az webapp config set \
  --resource-group "blogauto-prod-rg" \
  --name "blogauto-prod-admin" \
  --startup-command "gunicorn --bind=0.0.0.0:8000 --timeout 600 wsgi:application"
```

4. Restart the application
```bash
az webapp restart \
  --resource-group "blogauto-prod-rg" \
  --name "blogauto-prod-admin"
```