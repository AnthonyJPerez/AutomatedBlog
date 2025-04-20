# Blog Automation Deployment Guide

This guide explains the simplified deployment process for the blog automation project.

## Deployment Methods

There are two primary ways to deploy this application:

### 1. GitHub Actions (Recommended)

The project includes a streamlined GitHub Actions workflow for automated deployments:

- **File**: `.github/workflows/deploy-consolidated.yml`
- **Triggers**: 
  - Automatically on push to the `main` branch
  - Manually via GitHub Actions interface

To use GitHub Actions deployment:
1. Ensure you have the following secrets configured in your GitHub repository:
   - `AZURE_CREDENTIALS`: JSON credentials for Azure Service Principal
   - `AZURE_SUBSCRIPTION_ID`: Your Azure subscription ID

2. To modify deployment parameters, update the GitHub environment variables:
   - `ENVIRONMENT`: The deployment environment (dev, test, prod)
   - `PROJECT_NAME`: The base name for all resources (default: blogauto)
   - `LOCATION`: The Azure region for deployment (default: eastus)

### 2. Direct Deployment Script

For local or manual deployments, use the consolidated deployment script:

- **File**: `deploy-consolidated.py`
- **Prerequisites**:
  - Azure CLI installed and logged in, or
  - Azure SDK for Python installed (`pip install azure-identity azure-mgmt-resource`)

#### Examples:

**Using Azure CLI (default):**
```bash
python deploy-consolidated.py --resource-group "blogauto-dev-rg" --environment dev
```

**Using Azure SDK:**
```bash
# Set environment variables first
export AZURE_TENANT_ID="your-tenant-id"
export AZURE_CLIENT_ID="your-client-id"
export AZURE_CLIENT_SECRET="your-client-secret"
export AZURE_SUBSCRIPTION_ID="your-subscription-id"

python deploy-consolidated.py --resource-group "blogauto-dev-rg" --use-azure-sdk
```

## Parameters

All deployment methods support the following parameters:

- `resource-group`: Azure resource group name (REQUIRED)
- `location`: Azure region (default: eastus)
- `environment`: Environment name (default: dev)
- `project-name`: Project name for resource naming (default: blogauto)

## Infrastructure Components

The deployment creates the following Azure resources:

1. Storage Account for content and configurations
2. Function App for serverless processing
3. Key Vault for secret management
4. Application Insights for monitoring
5. WordPress App Service (if configured)

## Troubleshooting

If you encounter issues during deployment:

1. Check the GitHub Actions logs for detailed error messages
2. Verify your Azure credentials are correctly configured
3. Ensure resource names are valid and not already in use
4. Check for any Bicep validation errors in the templates

For persistent issues, run deployment with verbose logging:
```bash
python deploy-consolidated.py --resource-group "blogauto-dev-rg" --verbose
```