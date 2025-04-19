@description('The name of the project')
param projectName string = 'blog-automation'

@description('The environment (dev, test, prod)')
param environment string = 'dev'

@description('Location for all resources')
param location string = resourceGroup().location

// Generate unique names for resources
var uniqueSuffix = uniqueString(resourceGroup().id)
var storageAccountName = '${replace(projectName, '-', '')}${environment}${uniqueSuffix}'
var functionAppName = '${projectName}-function-${environment}-${uniqueSuffix}'
var appInsightsName = '${projectName}-insights-${environment}'
var keyVaultName = '${projectName}-kv-${environment}-${uniqueSuffix}'
var logAnalyticsName = '${projectName}-logs-${environment}'

// Deploy storage account
module storageModule 'storage.bicep' = {
  name: 'storageDeployment'
  params: {
    storageAccountName: storageAccountName
    location: location
  }
}

// Deploy Application Insights and Log Analytics
module monitoringModule 'monitoring.bicep' = {
  name: 'monitoringDeployment'
  params: {
    appInsightsName: appInsightsName
    logAnalyticsName: logAnalyticsName
    location: location
  }
}

// Deploy Key Vault
module keyVaultModule 'keyvault.bicep' = {
  name: 'keyVaultDeployment'
  params: {
    keyVaultName: keyVaultName
    location: location
  }
}

// Deploy Function App
module functionModule 'functions.bicep' = {
  name: 'functionDeployment'
  params: {
    functionAppName: functionAppName
    storageAccountName: storageModule.outputs.storageAccountName
    appInsightsInstrumentationKey: monitoringModule.outputs.instrumentationKey
    keyVaultName: keyVaultModule.outputs.keyVaultName
    location: location
  }
}

// Outputs
output functionAppName string = functionModule.outputs.functionAppName
output storageAccountName string = storageModule.outputs.storageAccountName
output keyVaultName string = keyVaultModule.outputs.keyVaultName
output appInsightsName string = monitoringModule.outputs.appInsightsName
