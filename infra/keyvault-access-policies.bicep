// Key Vault Access Policies template
@description('Name of the Key Vault')
param keyVaultName string

@description('Object ID of the Function App Managed Identity')
param functionAppPrincipalId string

@description('Object ID of the Admin Portal Managed Identity')
param adminPortalPrincipalId string = ''

// Reference the existing Key Vault
resource keyVault 'Microsoft.KeyVault/vaults@2022-07-01' existing = {
  name: keyVaultName
}

// Update Key Vault with access policies for both apps
resource keyVaultWithPolicies 'Microsoft.KeyVault/vaults@2022-07-01' = {
  name: keyVaultName
  location: keyVault.location
  tags: keyVault.tags
  properties: {
    sku: keyVault.properties.sku
    tenantId: subscription().tenantId
    enableRbacAuthorization: false
    enableSoftDelete: true
    softDeleteRetentionInDays: 90
    accessPolicies: concat(
      !empty(functionAppPrincipalId) ? [
        {
          tenantId: subscription().tenantId
          objectId: functionAppPrincipalId
          permissions: {
            secrets: [
              'get'
              'list'
            ]
            keys: [
              'get'
              'list'
            ]
            certificates: [
              'get'
              'list'
            ]
          }
        }
      ] : [],
      !empty(adminPortalPrincipalId) ? [
        {
          tenantId: subscription().tenantId
          objectId: adminPortalPrincipalId
          permissions: {
            secrets: [
              'get'
              'list'
            ]
            keys: [
              'get'
              'list'
            ]
            certificates: [
              'get'
              'list'
            ]
          }
        }
      ] : []
    )
    networkAcls: keyVault.properties.networkAcls
  }
}

// Outputs
output updatedKeyVaultId string = keyVaultWithPolicies.id