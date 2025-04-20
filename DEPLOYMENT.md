# Deployment Guide for Blog Automation Platform

This document provides step-by-step instructions for deploying the blog automation platform to Azure.

## Prerequisites

Before deploying, ensure you have:

1. **Azure CLI** installed and configured
2. **GitHub account** with permissions to the repository
3. **Azure subscription** with appropriate permissions
4. **Service Principal** with Contributor access to the subscription

## Setup GitHub Secrets

Set up the following secrets in your GitHub repository settings:

- `AZURE_CREDENTIALS`: JSON output from creating a service principal
- `WORDPRESS_ADMIN_PASSWORD`: Password for WordPress admin user
- `DB_ADMIN_PASSWORD`: Password for MySQL database admin

### Creating a Service Principal for GitHub Actions

```bash
# Replace with your subscription ID
SUBSCRIPTION_ID="your-subscription-id"

# Create the service principal and assign a Contributor role
az ad sp create-for-rbac --name "blogauto-github-actions" \
  --role Contributor \
  --scopes /subscriptions/$SUBSCRIPTION_ID \
  --sdk-auth

# The output JSON should be added as a secret named AZURE_CREDENTIALS in GitHub
```

## Deployment Options

### Option 1: Automatic Deployment via GitHub Actions

This is the recommended approach for production deployments:

1. Push changes to your repository
2. GitHub Actions workflow will automatically build and deploy resources
3. Monitor the workflow in the Actions tab

### Option 2: Manual Deployment using Deploy Script

For testing or when GitHub Actions isn't suitable:

```bash
# Basic deployment
python deploy-consolidated.py --resource-group blogauto-prod-rg --project-name blogauto --environment prod

# Advanced deployment with custom location
python deploy-consolidated.py --resource-group blogauto-prod-rg --project-name blogauto --environment prod --location westus

# Use Azure SDK approach (for CI/CD)
python deploy-consolidated.py --resource-group blogauto-prod-rg --project-name blogauto --environment prod --use-azure-sdk
```

## Troubleshooting the Admin Portal

If the admin portal isn't displaying properly, try these approaches:

### Step 1: Run the Fix Web App Directly Script

```bash
./fix-webapp-directly.sh "blogauto-prod-rg" "blogauto-prod-function"
```

### Step 2: Try the Minimal Test App

```bash
./deploy-minimal-test.sh "blogauto-prod-rg" "blogauto-prod-function"
```

### Step 3: Try the Static Test Deployment

```bash
./deploy-static-test.sh "blogauto-prod-rg" "blogauto-prod-function"
```

### Step 4: Use the Direct Fix Approach

```bash
./direct-fix.sh "blogauto-prod-rg" "blogauto-prod-function"
```

### Step 5: Create a Dedicated Admin App (Last Resort)

```bash
./create-dedicated-admin-app.sh "blogauto-prod-rg" "blogauto-prod-plan" "blogauto-prod-admin"
```

## Post-Deployment Configuration

After successful deployment:

1. Access the admin portal at `https://[function-app-name].azurewebsites.net/`
2. Configure analytics integrations in the admin portal
3. Set up blog configurations and themes
4. Configure WordPress for each blog

## Updating an Existing Deployment

To update an existing deployment:

```bash
# Update app configuration
./update-app-config.sh "blogauto-prod-rg" "blogauto-prod-function"

# Deploy only the admin portal
./deploy-admin-portal.sh "blogauto-prod-rg" "blogauto-prod-function"
```

## Monitoring and Logs

- Azure Function logs: Available in the Azure Portal under the Monitor tab
- Admin portal logs: Available in the Log Stream feature of the Function App
- Application Insights: If configured, provides detailed monitoring

## Additional Resources

- See `ADMIN_PORTAL_TROUBLESHOOTING.md` for detailed admin portal troubleshooting
- Check the Azure Portal for real-time metrics and logging
- Review GitHub Actions workflows for CI/CD pipeline details