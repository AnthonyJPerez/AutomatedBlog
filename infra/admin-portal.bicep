// Admin Portal Web App Bicep template
@description('Name of the admin portal web app')
param adminPortalName string

@description('Name of the app service plan to use (should be the same as Function App)')
param appServicePlanName string

@description('Location for all resources.')
param location string = resourceGroup().location

@description('Resource tags')
param tags object = {}

@description('Application Insights instrumentation key')
param appInsightsInstrumentationKey string

@description('Key Vault name for storing secrets')
param keyVaultName string

// Use existing App Service Plan
resource appServicePlan 'Microsoft.Web/serverfarms@2021-02-01' existing = {
  name: appServicePlanName
}

// Deploy the Admin Portal Web App with system-assigned identity
resource adminPortal 'Microsoft.Web/sites@2021-02-01' = {
  name: adminPortalName
  location: location
  tags: tags
  kind: 'app,linux'
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    serverFarmId: appServicePlan.id
    httpsOnly: true
    siteConfig: {
      linuxFxVersion: 'PYTHON|3.11'
      appSettings: [
        {
          name: 'WEBSITES_PORT'
          value: '5000'
        }
        {
          name: 'PORT'
          value: '5000'
        }
        {
          name: 'FLASK_APP'
          value: 'main.py'
        }
        {
          name: 'SCM_DO_BUILD_DURING_DEPLOYMENT'
          value: 'true'
        }
        {
          name: 'WEBSITES_ENABLE_APP_SERVICE_STORAGE'
          value: 'true'
        }
        {
          name: 'APPINSIGHTS_INSTRUMENTATIONKEY'
          value: appInsightsInstrumentationKey
        }
        {
          name: 'KEY_VAULT_NAME'
          value: keyVaultName
        }
      ]
      alwaysOn: true
      appCommandLine: 'gunicorn --bind=0.0.0.0:5000 --timeout 600 wsgi:application'
    }
  }
}

// Outputs
output adminPortalName string = adminPortal.name
output adminPortalHostName string = adminPortal.properties.defaultHostName
output adminPortalPrincipalId string = adminPortal.identity.principalId