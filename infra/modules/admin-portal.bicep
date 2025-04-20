// Admin Portal Web App Bicep template
@description('Name of the admin portal web app')
@minLength(2)
@maxLength(60)
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

@description('Python version to use')
@allowed(['3.10', '3.11', '3.12'])
param pythonVersion string = '3.11'

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
      linuxFxVersion: 'PYTHON|${pythonVersion}'
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
          name: 'ENABLE_ORYX_BUILD'
          value: 'true'
        }
        {
          name: 'PYTHONPATH'
          value: '/home/site/wwwroot'
        }
        {
          name: 'APPINSIGHTS_INSTRUMENTATIONKEY'
          value: appInsightsInstrumentationKey
        }
        {
          name: 'KEY_VAULT_NAME'
          value: keyVaultName
        }
        {
          name: 'WEBSITE_HTTPLOGGING_RETENTION_DAYS'
          value: '3'
        }
      ]
      alwaysOn: true
      appCommandLine: 'gunicorn --bind=0.0.0.0:5000 --timeout 600 wsgi:application'
      ftpsState: 'Disabled'
      minTlsVersion: '1.2'
      http20Enabled: true
    }
  }
}

// Add logs configuration
resource adminPortalLogsConfig 'Microsoft.Web/sites/config@2021-02-01' = {
  parent: adminPortal
  name: 'logs'
  properties: {
    applicationLogs: {
      fileSystem: {
        level: 'Information'
      }
    }
    httpLogs: {
      fileSystem: {
        enabled: true
        retentionInDays: 3
        retentionInMb: 35
      }
    }
    detailedErrorMessages: {
      enabled: true
    }
    failedRequestsTracing: {
      enabled: true
    }
  }
}

// Outputs
output adminPortalName string = adminPortal.name
output adminPortalHostName string = adminPortal.properties.defaultHostName
output adminPortalPrincipalId string = adminPortal.identity.principalId