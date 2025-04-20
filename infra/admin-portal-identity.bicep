// Admin Portal Identity Configuration
@description('Name of the admin portal web app')
param adminPortalName string

@description('Location for all resources.')
param location string = resourceGroup().location

@description('App Service Plan ID')
param appServicePlanId string

@description('Site Configuration')
param siteConfig object

// Enable managed identity for admin portal by updating the existing web app
resource adminPortalWithIdentity 'Microsoft.Web/sites@2021-02-01' = {
  name: adminPortalName
  location: location
  kind: 'app,linux'
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    serverFarmId: appServicePlanId
    httpsOnly: true
    siteConfig: siteConfig
  }
}

// Outputs
output adminPortalPrincipalId string = adminPortalWithIdentity.identity.principalId