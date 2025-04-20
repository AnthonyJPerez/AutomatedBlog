# Blog Automation Deployment Guide

This guide explains the deployment process for the blog automation project with WordPress integration.

## Architecture Overview

The blog automation system consists of the following components:

1. **Main Function App (blogauto-{env}-function)**: 
   - Contains all functions in the content pipeline 
   - Hosts the admin portal interface
   - Endpoints for API integrations

2. **Storage Account**: 
   - Stores blog configurations and generated content
   - Maintains state for function triggers

3. **Key Vault**:
   - Securely stores WordPress credentials
   - Manages API keys and access tokens

4. **WordPress (blogauto-{env}-wordpress)**:
   - Multisite WordPress installation
   - Enhanced with necessary plugins
   - Domain mapping for multiple blogs

5. **Infrastructure Automation**:
   - Bicep templates for Azure resources
   - GitHub Actions for CI/CD

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
   - `AZURE_CREDENTIALS`: JSON credentials for Azure Service Principal with format:
     ```json
     {
       "clientId": "<client-id>",
       "clientSecret": "<client-secret>",
       "subscriptionId": "<subscription-id>",
       "tenantId": "<tenant-id>"
     }
     ```
   - `AZURE_SUBSCRIPTION_ID`: Your Azure subscription ID

2. To modify deployment parameters, update the GitHub environment variables:
   - `ENVIRONMENT`: The deployment environment (dev, test, prod)
   - `PROJECT_NAME`: The base name for all resources (default: blogauto)
   - `LOCATION`: The Azure region for deployment (default: eastus for dev/test, westus for prod)

3. **WordPress Deployment**: The GitHub Action is now configured to **always** deploy WordPress with each infrastructure deployment.

### 2. Direct Deployment Script

For local or manual deployments, use the consolidated deployment script:

- **File**: `deploy-consolidated.py`
- **Prerequisites**:
  - Azure CLI installed and logged in, or
  - Azure SDK for Python installed (`pip install azure-identity azure-mgmt-resource`)

#### Examples:

**Deploy with WordPress (recommended):**
```bash
python deploy-consolidated.py --resource-group "blogauto-dev-rg" --environment dev --deploy-wordpress
```

**Production deployment with WordPress in westus:**
```bash
python deploy-consolidated.py --resource-group "blogauto-prod-rg" --environment prod --location westus --deploy-wordpress
```

**Using Azure SDK (Note: WordPress deployment not supported with SDK method):**
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
- `deploy-wordpress`: Flag to deploy WordPress with multisite capabilities (default: false)
- `verbose`: Enable verbose logging for troubleshooting (default: false)
- `use-azure-sdk`: Use Azure SDK instead of CLI (default: false)

## Infrastructure Components

The deployment creates the following Azure resources:

1. **Storage Account** (`blogauto{env}storage`):
   - Blog-specific configuration files
   - Generated content storage
   - Run artifacts in dated folders
   
2. **Function App** (`blogauto-{env}-function`):
   - Hosts all serverless functions
   - Contains admin portal UI
   - API endpoints for content generation
   
3. **Key Vault** (`blogauto-{env}-vault`):
   - WordPress credentials
   - API keys for OpenAI, Anthropic, etc.
   - Social media tokens
   
4. **Application Insights** (`blogauto-{env}-insights`):
   - Performance monitoring
   - Error tracking
   - Usage metrics
   
5. **WordPress App Service** (`wp-{uniqueId}`):
   - Multisite-enabled WordPress
   - Custom plugins
   - MySQL database

## Accessing the Admin Portal

The admin portal is part of the Function App. To access it:

1. Navigate to your Azure portal (portal.azure.com)
2. Find the Function App (`blogauto-{env}-function`)
3. The admin portal is available at the root URL:
   ```
   https://blogauto-{env}-function.azurewebsites.net/
   ```

### Admin Portal Configuration

If the admin portal is not accessible (you see the default Azure Functions page instead), you need to configure the Function App to serve the web application:

1. **Using the update scripts (Recommended)**:
   ```bash
   # First update the app configuration
   ./update-app-config.sh blogauto-prod-rg blogauto-prod-function
   
   # Then deploy the admin portal files
   ./deploy-admin-portal.sh blogauto-prod-rg blogauto-prod-function
   ```

2. **Using Azure Portal**:
   - Navigate to your Function App in the Azure Portal
   - Go to Configuration → General settings
   - Set "Stack" to "Python"
   - Set "Startup Command" to: `gunicorn --bind=0.0.0.0:5000 --timeout 600 main:app`
   - Save the changes
   - Go to Configuration → Application settings
   - Add the following settings:
     - `FLASK_APP`: `main.py`
     - `WEBSITES_PORT`: `5000`
     - `ADMIN_PORTAL_ENABLED`: `true`
   - Save the changes
   - Restart the Function App

3. **Using Azure CLI**:
   ```bash
   # Update app settings
   az webapp config appsettings set --resource-group blogauto-prod-rg --name blogauto-prod-function --settings FLASK_APP=main.py WEBSITES_PORT=5000 ADMIN_PORTAL_ENABLED=true
   
   # Update startup command
   az webapp config set --resource-group blogauto-prod-rg --name blogauto-prod-function --startup-file "gunicorn --bind=0.0.0.0:5000 --timeout 600 main:app"
   ```

## WordPress Integration

WordPress is now **automatically deployed** with each infrastructure deployment. The WordPress installation includes:

1. **Multisite Configuration**:
   - Enabled for multiple blogs
   - Domain mapping support

2. **Pre-installed Plugins**:
   - Yoast SEO
   - Jetpack
   - Contact Form 7
   - Wordfence Security
   - Google Analytics
   - WP Super Cache
   - Autoptimize
   - Mercator (for domain mapping)

3. **WordPress Credentials**:
   - Stored securely in Key Vault
   - Available to the Function App via managed identity

## Troubleshooting

If you encounter issues during deployment:

1. Check the GitHub Actions logs for detailed error messages
2. Verify your Azure credentials are correctly configured
3. Ensure resource names are valid and not already in use
4. Check for any Bicep validation errors in the templates

### Common Issues and Solutions

#### 1. Admin Portal Not Accessible

If you see the default Azure Functions landing page instead of the admin portal:

- **Problem**: The Function App is not configured to serve the web application files
- **Solution**: Use the provided scripts to update the app configuration:
  ```bash
  ./update-app-config.sh blogauto-prod-rg blogauto-prod-function
  ./deploy-admin-portal.sh blogauto-prod-rg blogauto-prod-function
  ```

- **Alternative Solution**: Manually check the Function App configuration in Azure Portal:
  1. Ensure the `WEBSITES_PORT` is set to `5000`
  2. Verify the startup command is set to `gunicorn --bind=0.0.0.0:5000 --timeout 600 main:app`
  3. Check if all necessary files (main.py, templates folder, static folder) are deployed to the Function App

- **Verification**: Check the Function App logs in Azure Portal for any startup errors:
  1. Go to the Function App in Azure Portal
  2. Select "Logs" from the left menu
  3. Check for any Python or Gunicorn startup errors

#### 2. Azure Quota Limitations

If you encounter an error like:
```
"code":"SubscriptionIsOverQuotaForSku","message":"This region has quota of 0 instances for your subscription. Try selecting different region or SKU."
```

This indicates your Azure subscription has reached its quota limit for the specified SKU in that region. To resolve this:

- Use a different region by changing the `location` parameter
  ```bash
  python deploy-consolidated.py --resource-group "blogauto-dev-rg" --location "westus" --deploy-wordpress
  ```

- The templates now default to `B1` (Basic) SKU instead of premium tiers
- For production, consider requesting a quota increase from Azure Support

#### 3. GitHub Actions Workflow Syntax Errors

If you see errors related to duplicate commands or improper formatting:

- Check for duplicate `az deployment group create` commands in the workflow file
- Ensure parameters are properly formatted with one per line
- Verify that deployment parameters are correctly specified

#### 4. WordPress Deployment Issues

If WordPress deployment fails or doesn't appear:

- Check if the `deployWordPress` parameter is set to `true` in the deployment
- Verify that the WordPress App Service name is unique (globally)
- Ensure MySQL server name meets Azure naming requirements

#### 4. Storage Account Naming Errors

If you receive errors about invalid storage account names:

- Storage account names must be lowercase alphanumeric characters
- No hyphens or special characters are allowed
- The deployment script automatically handles this by using `toLower()` and removing hyphens

For persistent issues, run deployment with verbose logging:
```bash
python deploy-consolidated.py --resource-group "blogauto-dev-rg" --deploy-wordpress --verbose
```

## Recent Changes

**April 20, 2025 Update:**
- Modified GitHub Actions workflow to **always** deploy WordPress with each infrastructure deployment
- Updated deployment script to support the `--deploy-wordpress` flag
- Fixed issues with complex Bicep expressions by simplifying tier determination
- Added improved error handling and troubleshooting guidance
- Updated region configuration to use westus for production (better quota availability)
- Enhanced documentation with detailed descriptions of all components