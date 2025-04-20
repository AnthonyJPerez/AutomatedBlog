# Deployment Guide for Blog Automation Platform

This document provides step-by-step instructions for deploying the blog automation platform to Azure.

## Architecture Overview

The deployment consists of two main components:
1. **Azure Functions App**: Handles all serverless processing, event triggers, and content generation
2. **Admin Portal Web App**: Dedicated web application for managing blogs, configurations, and monitoring

This clean separation ensures each component can operate independently and be scaled/maintained separately.

## Prerequisites

Before deploying, ensure you have:

1. **GitHub account** with permissions to the repository
2. **Azure subscription** with appropriate permissions
3. **Service Principal** with Contributor access to the subscription

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

## Automatic Deployment via GitHub Actions

This is the touchless deployment approach for production:

1. Push changes to your repository
2. GitHub Actions workflow will automatically:
   - Build and validate the Bicep templates
   - Deploy Azure infrastructure
   - Deploy the Functions App
   - Deploy the dedicated Admin Portal web app
3. Monitor the workflow in the GitHub Actions tab

## Deployment Components

The GitHub workflow deploys several components:

1. **Infrastructure** (Bicep templates):
   - Resource Group
   - Storage Account
   - Function App
   - Key Vault
   - WordPress (if enabled)
   - Application Insights

2. **Functions App**:
   - All serverless functions for processing
   - Event-triggered functions
   - Background processing tasks

3. **Admin Portal Web App**:
   - Dedicated web app for the admin interface
   - Configuration and management UI
   - Monitoring and analytics dashboards

## Admin Portal Access

The admin portal is deployed as a dedicated web app and will be available at:

```
https://[project-name]-[environment]-admin.azurewebsites.net/
```

For example:
- Development: `https://blogauto-dev-admin.azurewebsites.net/`
- Production: `https://blogauto-prod-admin.azurewebsites.net/`

## Post-Deployment Configuration

After successful deployment:

1. Access the admin portal at the dedicated web app URL
2. Configure analytics integrations in the admin portal
3. Set up blog configurations and themes
4. Configure WordPress for each blog

## Manual Deployment (Alternative)

For testing or when GitHub Actions isn't suitable:

```bash
# Basic deployment
python deploy-consolidated.py --resource-group blogauto-prod-rg --project-name blogauto --environment prod

# Advanced deployment with custom location
python deploy-consolidated.py --resource-group blogauto-prod-rg --project-name blogauto --environment prod --location westus

# Use Azure SDK approach (for CI/CD)
python deploy-consolidated.py --resource-group blogauto-prod-rg --project-name blogauto --environment prod --use-azure-sdk
```

## Monitoring and Logs

- Function App logs: Available in the Azure Portal under the Monitor tab
- Admin portal logs: Available in the Log Stream feature of the Admin Portal Web App
- Application Insights: Provides detailed monitoring for both the Function App and Admin Portal

## Additional Resources

- Check the Azure Portal for real-time metrics and logging
- Review GitHub Actions workflows for CI/CD pipeline details
- Monitor Application Insights for performance metrics and errors