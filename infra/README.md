# Blog Automation Infrastructure

This directory contains the infrastructure-as-code templates (using Bicep) for deploying the Blog Automation platform to Azure.

## Directory Structure

```
infra/
  ├── bicepconfig.json        # compiler/linter settings & module aliases
  ├── main.bicep              # root orchestrator
  ├── modules/                # reusable modules
  │     ├── storage.bicep     # storage account, blob containers, lifecycle policy
  │     ├── monitoring.bicep  # app insights, log analytics
  │     ├── keyvault.bicep    # key vault configuration
  │     ├── functions.bicep   # function app, app service plan
  │     ├── admin-portal.bicep # admin portal web app
  │     ├── wordpress.bicep   # optional WordPress deployment (multisite capable)
  │     └── keyvault-access-policies.bicep # key vault access policies
  └── env/                    # environment-specific parameter files
        ├── dev.parameters.json
        └── prod.parameters.json
```

## Deployment Instructions

### Prerequisites

- Azure CLI installed
- Bicep CLI installed
- Authenticated with Azure (`az login`)
- A resource group created

### Deploying to Development Environment

```bash
# Set environment variables
RG_NAME="blogauto-dev-rg"
LOCATION="eastus"

# Create resource group if it doesn't exist
az group create --name $RG_NAME --location $LOCATION

# Deploy using dev parameters
az deployment group create \
  --resource-group $RG_NAME \
  --template-file infra/main.bicep \
  --parameters @infra/env/dev.parameters.json \
  --parameters dbAdminPassword="$(openssl rand -base64 16)" \
  --parameters wpAdminPassword="$(openssl rand -base64 16)" \
  --parameters wpAdminEmail="admin@example.com"
```

### Deploying to Production Environment

```bash
# Set environment variables
RG_NAME="blogauto-prod-rg"
LOCATION="westus" # Note westus for better quota availability

# Create resource group if it doesn't exist
az group create --name $RG_NAME --location $LOCATION

# Deploy using prod parameters
az deployment group create \
  --resource-group $RG_NAME \
  --template-file infra/main.bicep \
  --parameters @infra/env/prod.parameters.json \
  --parameters dbAdminPassword="$(openssl rand -base64 16)" \
  --parameters wpAdminPassword="$(openssl rand -base64 16)" \
  --parameters wpAdminEmail="admin@example.com"
```

### Updating Only Specific Resources

You can use the `--what-if` flag to see what changes will be made before deployment:

```bash
az deployment group what-if \
  --resource-group $RG_NAME \
  --template-file infra/main.bicep \
  --parameters @infra/env/dev.parameters.json
```

### Working with GitHub Actions

The GitHub Actions workflow in `.github/workflows/deploy-consolidated.yml` handles the automated deployment of this infrastructure. It includes environment-specific configurations and settings.

## Parameter Validation

The template includes parameter validation with:
- `@minLength` and `@maxLength` for string lengths
- `@allowed` for enum values
- `@secure()` for sensitive values

## Best Practices Implemented

- Parameter validation with decorators
- Secure parameter handling without exposing sensitive data
- Resource naming conventions with prefixes and uniqueness
- Explicit dependencies between resources
- Modular design with reusable components
- Environment-specific parameter files
- Proper identity management with system-assigned managed identities