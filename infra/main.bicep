// Main deployment template for the blog automation infrastructure
@description('Project name used as prefix for resource naming')
param projectName string = 'blogauto'

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
var namePrefix = '${projectName}-${environment}'

// Tags for resources
var deploymentTags = {
  Environment: environment
  Application: 'BlogAutomation'
  DeployDate: '${environment}-deployment'
}

// Storage account settings
// Convert to lowercase to ensure valid storage account name (Azure storage requires lowercase)
var storageName = toLower(replace('${namePrefix}storage', '-', ''))
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
    tags: deploymentTags
    sku: storageSku
  }
}

// Deploy Key Vault
module keyVaultModule 'keyvault.bicep' = {
  name: 'keyVaultDeployment'
  params: {
    keyVaultName: keyVaultName
    location: location
    tags: deploymentTags
    functionAppPrincipalId: functionApp.outputs.functionAppPrincipalId
  }
}

// Deploy monitoring resources
module monitoringModule 'monitoring.bicep' = {
  name: 'monitoringDeployment'
  params: {
    appInsightsName: appInsightsName
    location: location
    tags: deploymentTags
  }
}

// Deploy Function App
module functionApp 'functions.bicep' = {
  name: 'functionAppDeployment'
  params: {
    functionAppName: functionAppName
    appServicePlanName: appServicePlanName
    location: location
    tags: deploymentTags
    storageAccountName: storageModule.outputs.storageAccountName
    appInsightsInstrumentationKey: monitoringModule.outputs.instrumentationKey
    keyVaultName: keyVaultName
  }
  // No explicit dependsOn needed, implicit through parameter references
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
    keyVaultName: keyVaultName
  }
  // No explicit dependsOn needed, implicit through parameter references
}

// Outputs
output functionAppName string = functionApp.outputs.functionAppName
output storageAccountName string = storageModule.outputs.storageAccountName
output keyVaultName string = keyVaultName
output functionAppHostName string = functionApp.outputs.functionAppHostName
output wordpressUrl string = deployWordPress ? wordpressModule.outputs.wordpressUrl : ''