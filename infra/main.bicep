// Main deployment template for the blog automation infrastructure
@description('Environment name (dev, test, prod)')
param environment string = 'dev'

@description('Azure region for all resources')
param location string = resourceGroup().location

@description('Enable WordPress deployment')
param deployWordPress bool = false

@description('WordPress site name (must be globally unique)')
param wordPressSiteName string = 'wp-${uniqueString(resourceGroup().id)}'

@description('Database administrator login name')
param dbAdminLogin string = 'wpdbadmin'

@description('Database administrator password')
@secure()
param dbAdminPassword string = ''

@description('WordPress admin email address')
param wpAdminEmail string = ''

@description('WordPress admin username')
param wpAdminUsername string = 'admin'

@description('WordPress admin password')
@secure()
param wpAdminPassword string = ''

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

// WordPress settings
var wpAppServicePlanName = '${wordPressSiteName}-plan'

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

// Deploy WordPress if enabled
module wordpressModule 'wordpress.bicep' = if (deployWordPress) {
  name: 'wordpressDeployment'
  params: {
    siteName: wordPressSiteName
    appServicePlanName: wpAppServicePlanName
    location: location
    sku: environment == 'prod' ? 'P1v2' : 'B1'
    administratorLogin: dbAdminLogin
    administratorLoginPassword: dbAdminPassword
    wpAdminEmail: wpAdminEmail
    wpAdminUsername: wpAdminUsername
    wpAdminPassword: wpAdminPassword
  }
}

// Outputs
output functionAppName string = functionApp.outputs.functionAppName
output storageAccountName string = storageModule.outputs.storageAccountName
output keyVaultName string = keyVaultName
output functionAppHostName string = functionApp.outputs.functionAppHostName
output wordpressUrl string = deployWordPress ? wordpressModule.outputs.wordpressUrl : ''