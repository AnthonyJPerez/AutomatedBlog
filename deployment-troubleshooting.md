# Deployment Troubleshooting Guide

This document provides solutions to common deployment issues encountered with the Blog Automation Platform.

## Git Deployment Conflicts

### Issue: Conflict with existing ScmType

When deploying through GitHub Actions or the Azure CLI, you might encounter the following error:

```
Conflict with existing ScmType: ExternalGit
```

This happens because the Bicep template is trying to configure Git deployment on a resource that already has Git deployment configured.

### Solution

We've implemented a conditional Git deployment configuration:

1. Added a `configureSourceControl` parameter (default: false) to Bicep templates
2. Set this parameter to `false` in GitHub workflows
3. Added proper SCM type detection in the workflow to correctly handle existing configurations
4. Modified deployment scripts to check for existing SCM types before attempting to configure Git

## Poetry Configuration Errors

### Issue: Missing [tool.poetry] section

When deploying Python applications to Azure App Service, you might see errors related to Poetry configuration:

```
[tool.poetry] section not found in pyproject.toml
```

This happens because Azure App Service expects a Poetry-compatible configuration but finds a different format.

### Solution

We've updated the project configuration to be Poetry-compatible:

1. Restructured `pyproject.toml` to include the proper `[tool.poetry]` section
2. Created proper `requirements.txt` files for deployment
3. Added deployment scripts to ensure the correct files are deployed:
   - `redeploy-admin-portal.sh`: Redeploys the admin portal with Poetry configuration
   - `redeploy-function-app.sh`: Redeploys the function app with Poetry configuration

## Manual Deployment Process

If automatic deployment is failing, you can use our manual deployment scripts:

### Redeploying the Admin Portal

```bash
# For production
./redeploy-admin-portal.sh prod

# For development
./redeploy-admin-portal.sh dev
```

This script:
1. Creates a temporary directory with the proper files
2. Packages them into a ZIP file
3. Deploys directly to the Azure App Service
4. Restarts the service to apply changes

### Redeploying the Function App

```bash
# For production
./redeploy-function-app.sh prod

# For development
./redeploy-function-app.sh dev
```

This script follows a similar process for the function app.

## Deployment Templates

The `deployment-templates` directory contains minimal versions of files needed for a successful deployment:

- `main.py`: A simple Flask application for the admin portal
- `wsgi.py`: WSGI entry point for the admin portal
- `requirements.txt`: Python dependencies
- `pyproject.toml`: Poetry-compatible project configuration

These templates can be used as a starting point for debugging deployment issues.

## Other Common Issues

### Azure Resource Naming

Make sure resource names match between GitHub workflow variables and deployment parameters. Check for:

- Resource group names
- Function app names
- Admin portal web app names

### Azure Credentials

Ensure GitHub Actions has proper Azure credentials. The GitHub repository should have a secret named `AZURE_CREDENTIALS` with the proper service principal credentials.