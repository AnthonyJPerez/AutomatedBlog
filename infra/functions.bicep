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

// Get reference to storage account
resource storageAccount 'Microsoft.Storage/storageAccounts@2021-09-01' existing = {
  name: storageAccountName
}

@description('The SKU of the App Service Plan')
param appServicePlanSku string = 'B1' // Default to Basic tier

// Create App Service Plan
resource appServicePlan 'Microsoft.Web/serverfarms@2022-03-01' = {
  name: appServicePlanName
  location: location
  tags: tags
  sku: {
    name: appServicePlanSku
    tier: appServicePlanSku == 'Y1' ? 'Dynamic' : 
          startsWith(appServicePlanSku, 'B') ? 'Basic' : 
          startsWith(appServicePlanSku, 'S') ? 'Standard' : 
          startsWith(appServicePlanSku, 'P') ? 'Premium' : 'Free'
  }
  properties: {
    reserved: true // Required for Linux
  }
}

// Create Function App
resource functionApp 'Microsoft.Web/sites@2022-03-01' = {
  name: functionAppName
  location: location
  tags: tags
  kind: 'functionapp,linux'
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
      ]
      ftpsState: 'Disabled'
      minTlsVersion: '1.2'
      http20Enabled: true
    }
    httpsOnly: true
  }
}

// Outputs
output functionAppId string = functionApp.id
output functionAppName string = functionApp.name
output functionAppHostName string = functionApp.properties.defaultHostName
output functionAppPrincipalId string = functionApp.identity.principalId