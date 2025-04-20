// Main deployment template for the blog automation infrastructure
@minLength(3)
@maxLength(11)
@description('Project name used as prefix for resource naming (3-11 characters)')
param projectName string = 'blogauto'

@allowed(['dev', 'test', 'prod'])
@description('Environment name (dev, test, prod)')
param environment string = 'dev'

@description('Azure region for all resources')
param location string = resourceGroup().location

@description('Enable WordPress deployment')
param deployWordPress bool = false

@maxLength(20)
@description('WordPress site name suffix (optional, max 20 chars)')
param wordPressSiteNameSuffix string = ''

@minLength(4)
@maxLength(20)
@description('Database administrator login name (4-20 chars)')
param dbAdminLogin string = 'wpdbadmin'

@minLength(8)
@description('Database administrator password (min 8 chars)')
@secure()
param dbAdminPassword string = ''

@description('WordPress admin email address')
param wpAdminEmail string = ''

@minLength(4)
@description('WordPress admin username (min 4 chars)')
param wpAdminUsername string = 'admin'

@minLength(8)
@description('WordPress admin password (min 8 chars)')
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
// Use B1 SKU for all environments to avoid quota issues
var appServicePlanSku = 'B1'

// Admin Portal settings
var adminPortalName = '${namePrefix}-admin'

// Use a region with available quota
// westus often has better availability than eastus
var deploymentRegion = location == 'eastus' && environment == 'prod' ? 'westus' : location

// Key Vault settings
var keyVaultName = '${namePrefix}-vault'

// WordPress settings
var wordPressSiteName = !empty(wordPressSiteNameSuffix) ? 'wp-${wordPressSiteNameSuffix}' : 'wp-${uniqueString(resourceGroup().id)}'
var wpAppServicePlanName = '${wordPressSiteName}-plan'

// Deploy storage account
module storageModule 'modules/storage.bicep' = {
  name: 'storageDeployment'
  params: {
    storageAccountName: storageName
    location: location
    tags: deploymentTags
    sku: storageSku
  }
}

// Deploy monitoring resources
module monitoringModule 'modules/monitoring.bicep' = {
  name: 'monitoringDeployment'
  params: {
    appInsightsName: appInsightsName
    location: location
    tags: deploymentTags
  }
}

// Deploy Key Vault first (without access policies)
module keyVaultModule 'modules/keyvault.bicep' = {
  name: 'keyVaultDeployment'
  params: {
    keyVaultName: keyVaultName
    location: location
    tags: deploymentTags
    // Principal IDs will be added in a separate step via keyvault-access-policies.bicep
  }
}

// Deploy Function App
module functionApp 'modules/functions.bicep' = {
  name: 'functionAppDeployment'
  params: {
    functionAppName: functionAppName
    appServicePlanName: appServicePlanName
    location: deploymentRegion
    tags: deploymentTags
    storageAccountName: storageModule.outputs.storageAccountName
    appInsightsInstrumentationKey: monitoringModule.outputs.instrumentationKey
    keyVaultName: keyVaultName
    appServicePlanSku: appServicePlanSku
  }
}

// Deploy Admin Portal Web App
module adminPortalModule 'modules/admin-portal.bicep' = {
  name: 'adminPortalDeployment'
  params: {
    adminPortalName: adminPortalName
    appServicePlanName: appServicePlanName // Reuse the Function App's app service plan
    location: deploymentRegion
    tags: deploymentTags
    appInsightsInstrumentationKey: monitoringModule.outputs.instrumentationKey
    keyVaultName: keyVaultName
  }
  dependsOn: [
    functionApp // Make sure Function App is deployed first since we're reusing its app service plan
  ]
}

// Update Key Vault access policies after apps are created
module keyVaultAccessPoliciesModule 'modules/keyvault-access-policies.bicep' = {
  name: 'keyVaultAccessPoliciesDeployment'
  params: {
    keyVaultName: keyVaultName
    functionAppPrincipalId: functionApp.outputs.functionAppPrincipalId
    adminPortalPrincipalId: adminPortalModule.outputs.adminPortalPrincipalId
  }
  dependsOn: [
    keyVaultModule
    functionApp
    adminPortalModule
  ]
}

// Deploy WordPress if enabled
module wordpressModule 'modules/wordpress.bicep' = if (deployWordPress) {
  name: 'wordpressDeployment'
  params: {
    siteName: wordPressSiteName
    appServicePlanName: wpAppServicePlanName
    location: deploymentRegion
    sku: environment == 'prod' ? 'B2' : 'B1'  // Scale down to avoid quota issues
    administratorLogin: dbAdminLogin
    administratorLoginPassword: dbAdminPassword
    wpAdminEmail: wpAdminEmail
    wpAdminUsername: wpAdminUsername
    wpAdminPassword: wpAdminPassword
    keyVaultName: keyVaultName
  }
  dependsOn: [
    keyVaultModule // Ensure Key Vault exists for WordPress to store its secrets
  ]
}

// Outputs
output functionAppName string = functionApp.outputs.functionAppName
output storageAccountName string = storageModule.outputs.storageAccountName
output keyVaultName string = keyVaultName
output functionAppHostName string = functionApp.outputs.functionAppHostName
output adminPortalName string = adminPortalModule.outputs.adminPortalName
output adminPortalHostName string = adminPortalModule.outputs.adminPortalHostName
output wordpressUrl string = deployWordPress ? wordpressModule.outputs.wordpressUrl : ''