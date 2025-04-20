// Functions template for blog automation infrastructure
@description('Name of the Azure Function App')
param functionAppName string

@description('Name of the App Service Plan')
param appServicePlanName string

@description('Azure region for the function app')
param location string

@description('Tags for the function app')
param tags object

@description('Name of the storage account for function app')
param storageAccountName string

@description('Instrumentation key for Application Insights')
param appInsightsInstrumentationKey string

@description('Name of the Key Vault')
param keyVaultName string

@description('The SKU of the App Service Plan')
param appServicePlanSku string = 'B1' // Default to Basic tier

// Hardcoded tier based on the most common SKU option, matching the default param value
var tier = 'Basic'

// Get reference to storage account
resource storageAccount 'Microsoft.Storage/storageAccounts@2021-09-01' existing = {
  name: storageAccountName
}

// Create App Service Plan
resource appServicePlan 'Microsoft.Web/serverfarms@2022-03-01' = {
  name: appServicePlanName
  location: location
  tags: tags
  sku: {
    name: appServicePlanSku
    tier: tier
  }
  properties: {
    reserved: true // Required for Linux
  }
}

// Create Function App with Web App capabilities
resource functionApp 'Microsoft.Web/sites@2022-03-01' = {
  name: functionAppName
  location: location
  tags: tags
  kind: 'app,linux' // Changed from 'functionapp,linux' to support both functions and web app
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    serverFarmId: appServicePlan.id
    siteConfig: {
      linuxFxVersion: 'PYTHON|3.11'
      appSettings: [
        {
          name: 'FUNCTIONS_EXTENSION_VERSION'
          value: '~4'
        }
        {
          name: 'FUNCTIONS_WORKER_RUNTIME'
          value: 'python'
        }
        {
          name: 'AzureWebJobsStorage'
          value: 'DefaultEndpointsProtocol=https;AccountName=${storageAccount.name};EndpointSuffix=${environment().suffixes.storage};AccountKey=${storageAccount.listKeys().keys[0].value}'
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
          name: 'WEBSITE_RUN_FROM_PACKAGE'
          value: '1'
        }
        {
          name: 'STORAGE_ACCOUNT_NAME'
          value: storageAccount.name
        }
        {
          name: 'USE_KEY_VAULT_WORDPRESS_CREDENTIALS'
          value: 'true'
        }
        // Default to automatic WordPress connection when credentials are in Key Vault
        {
          name: 'WORDPRESS_USE_DEFAULT_CREDENTIALS'
          value: 'true'
        }
        // The following environment variables will be overridden by Key Vault values when available
        {
          name: 'WORDPRESS_URL'
          value: '@Microsoft.KeyVault(SecretUri=https://${keyVaultName}.vault.azure.net/secrets/WordPressUrl/)'
        }
        {
          name: 'WORDPRESS_USERNAME'
          value: '@Microsoft.KeyVault(SecretUri=https://${keyVaultName}.vault.azure.net/secrets/WordPressAdminUsername/)'
        }
        {
          name: 'WORDPRESS_APP_PASSWORD'
          value: '@Microsoft.KeyVault(SecretUri=https://${keyVaultName}.vault.azure.net/secrets/WordPressAppPassword/)'
        }
        // Web app specific settings
        {
          name: 'SCM_DO_BUILD_DURING_DEPLOYMENT'
          value: 'true'
        }
        {
          name: 'ENABLE_ORYX_BUILD'
          value: 'true'
        }
        {
          name: 'FLASK_APP'
          value: 'main.py'
        }
        {
          name: 'WEBSITES_PORT'
          value: '5000'
        }
        {
          name: 'ADMIN_PORTAL_ENABLED'
          value: 'true'
        }
      ]
      ftpsState: 'Disabled'
      minTlsVersion: '1.2'
      http20Enabled: true
      // Add handlers for Flask application
      appCommandLine: 'gunicorn --bind=0.0.0.0:5000 --timeout 600 main:app'
      // Ensure the root handler is set
      defaultDocuments: [
        'index.html',
        'index.htm',
        'default.html',
        'default.htm',
        'hostingstart.html'
      ]
    }
    httpsOnly: true
  }
}

// Outputs
output functionAppId string = functionApp.id
output functionAppName string = functionApp.name
output functionAppHostName string = functionApp.properties.defaultHostName
output functionAppPrincipalId string = functionApp.identity.principalId