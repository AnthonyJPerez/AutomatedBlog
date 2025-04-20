# Infrastructure Deployment Troubleshooting Guide

This document provides guidance on troubleshooting common issues with Azure infrastructure deployment for the multi-blog pipeline project.

## Common Deployment Errors

### 1. Key Vault Access Policies Error

**Error**: `'The resource 'Microsoft.KeyVault/vaults/{vault-name}/accessPolicies/add' is defined multiple times in a template.`

**Solution**: 
- We now use a single consolidated access policy resource to avoid duplication
- All principal IDs are added in a single operation
- This eliminates the circular dependency between resources

### 2. Resource Circular Dependencies

**Problem**: Previously, there were circular dependencies between Key Vault, Function App, and Admin Portal resources.

**Solution**:
- We've separated the identity configuration from the initial deployment
- Resources are deployed in the following order:
  1. Key Vault (without access policies)
  2. Function App and Admin Portal (acquiring managed identities)
  3. Key Vault access policies (referencing the identities)

### 3. Managed Identity Issues

**Problem**: Adding system-assigned managed identity would sometimes fail with schema validation errors.

**Solution**:
- Created a separate bicep module `admin-portal-identity.bicep` to manage identity
- This creates a cleaner separation of concerns
- The identity is added in a separate deployment step after the initial resource creation

### 4. Bicep Linter Warnings

**Warning**: `Resource has its name formatted as a child of resource. The syntax can be simplified by using the parent property.`

**Solution**:
- Updated to use the recommended `parent` property syntax
- Simplified references between parent-child resources
- This provides cleaner, more maintainable code and reduces deployment errors

## GitHub Actions Deployment Improvements

We've made the following improvements to the GitHub Actions workflow:

1. Enhanced logging and error reporting
2. Better handling of app service configuration settings
3. Proper dependency management between deployment steps
4. Comprehensive validation of all Bicep templates
5. Improved Python configuration for the admin portal web app

## Key Vault Configuration

When updating Key Vault access policies, be aware that:

1. The keyvault-access-policies.bicep file now uses a consolidated approach
2. Principal IDs (object IDs) for managed identities are obtained from the outputs of their respective modules
3. Access policies are added only after the resources with managed identities are created

## Troubleshooting CI/CD Issues

If deployments fail in the CI/CD pipeline:

1. Check the detailed error messages in the GitHub Actions logs
2. Verify that all required parameters are correctly passed to the Bicep templates
3. Ensure the service principal defined in AZURE_CREDENTIALS has sufficient permissions
4. For persistent errors, consider running the az deployment group what-if command locally

## Azure Subscription Quota Limits

If you encounter quota limit errors:

1. Consider using smaller SKUs for App Service Plans
2. Deploy to different regions to distribute resource usage
3. Request quota increases from Azure support if needed

## Bicep Template Validation

Always run validation before deployment:

```bash
# Validate all templates
bicep build infra/main.bicep
bicep build infra/storage.bicep
bicep build infra/functions.bicep
bicep build infra/keyvault.bicep
bicep build infra/keyvault-access-policies.bicep
bicep build infra/monitoring.bicep
bicep build infra/admin-portal.bicep
bicep build infra/admin-portal-identity.bicep
```

For more detailed validation:

```bash
az deployment group validate \
  --resource-group "your-resource-group" \
  --template-file ./infra/main.bicep \
  --parameters projectName="your-project-name" \
  --parameters environment="dev"
```