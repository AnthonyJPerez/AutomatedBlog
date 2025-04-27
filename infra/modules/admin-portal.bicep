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

@description('Git repository URL for the admin portal')
@minLength(5)
param repoUrl string = 'https://github.com/yourusername/blog-automation-platform.git'

@description('Git branch to deploy')
@minLength(1)
param repoBranch string = 'main'

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
        // Basic configuration for Python/Flask app
        {
          name: 'WEBSITES_PORT'
          value: '8000'
        }
        {
          name: 'PORT'
          value: '8000'
        }
        {
          name: 'FLASK_APP'
          value: 'main.py'
        }
        // Git and deployment settings
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
        // Python configuration
        {
          name: 'PYTHONPATH'
          value: '/home/site/wwwroot'
        }
        // Monitoring and logging settings
        {
          name: 'APPINSIGHTS_INSTRUMENTATIONKEY'
          value: appInsightsInstrumentationKey
        }
        {
          name: 'WEBSITE_HTTPLOGGING_RETENTION_DAYS'
          value: '3'
        }
        {
          name: 'WEBSITE_SCM_ALWAYS_ON_ENABLED'
          value: 'true'
        }
        {
          name: 'WEBSITE_LOG_LEVEL'
          value: 'verbose'
        }
        // Key Vault integration
        {
          name: 'KEY_VAULT_NAME'
          value: keyVaultName
        }
      ]
      alwaysOn: true
      appCommandLine: 'gunicorn --bind=0.0.0.0:$PORT main:app'
      ftpsState: 'Disabled'
      minTlsVersion: '1.2'
      http20Enabled: true
    }
  }
}

// Configure Git source control for the admin portal
resource portalGit 'Microsoft.Web/sites/sourcecontrols@2021-02-01' = {
  parent: adminPortal
  name: 'web'
  properties: {
    repoUrl: repoUrl
    branch: repoBranch
    isManualIntegration: true
  }
  // No need for explicit dependsOn since we're using parent property
}

// Configure the Web App settings
resource adminPortalConfig 'Microsoft.Web/sites/config@2021-02-01' = {
  parent: adminPortal
  name: 'web'
  properties: {
    linuxFxVersion: 'PYTHON|${pythonVersion}'
    appCommandLine: 'gunicorn --bind=0.0.0.0:$PORT main:app'
    alwaysOn: true
    ftpsState: 'Disabled'
    minTlsVersion: '1.2'
    http20Enabled: true
  }
  dependsOn: [
    portalGit
  ]
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