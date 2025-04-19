// Main deployment template for the blog automation infrastructure
@description('Environment name (dev, test, prod)')
param environment string = 'dev'

@description('Azure region for all resources')
param location string = resourceGroup().location

// Name prefix for resources
var namePrefix = 'blogauto-${environment}'

// Tags for resources
var tags = {
  Environment: environment
  Application: 'BlogAutomation'
  DeploymentDate: utcNow('yyyy-MM-dd')
}

// Storage account settings
var storageName = replace('${namePrefix}storage', '-', '')
var storageSku = environment == 'prod' ? 'Standard_GRS' : 'Standard_LRS'

// Function app settings
var functionAppName = '${namePrefix}-function'
var appServicePlanName = '${namePrefix}-plan'
var appInsightsName = '${namePrefix}-insights'

// Key Vault settings
var keyVaultName = '${namePrefix}-vault'

// Deploy storage account
module storageModule 'storage.bicep' = {
  name: 'storageDeployment'
  params: {
    storageAccountName: storageName
    location: location
    tags: tags
    sku: storageSku
  }
}

// Deploy Key Vault
module keyVaultModule 'keyvault.bicep' = {
  name: 'keyVaultDeployment'
  params: {
    keyVaultName: keyVaultName
    location: location
    tags: tags
    functionAppPrincipalId: functionApp.outputs.functionAppPrincipalId
  }
}

// Deploy monitoring resources
module monitoringModule 'monitoring.bicep' = {
  name: 'monitoringDeployment'
  params: {
    appInsightsName: appInsightsName
    location: location
    tags: tags
  }
}

// Deploy Function App
module functionApp 'functions.bicep' = {
  name: 'functionAppDeployment'
  params: {
    functionAppName: functionAppName
    appServicePlanName: appServicePlanName
    location: location
    tags: tags
    storageAccountName: storageModule.outputs.storageAccountName
    appInsightsInstrumentationKey: monitoringModule.outputs.instrumentationKey
    keyVaultName: keyVaultName
  }
  dependsOn: [
    storageModule
    monitoringModule
  ]
}

// Outputs
output functionAppName string = functionApp.outputs.functionAppName
output storageAccountName string = storageModule.outputs.storageAccountName
output keyVaultName string = keyVaultName
output functionAppHostName string = functionApp.outputs.functionAppHostName