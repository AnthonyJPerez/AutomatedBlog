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

// Using a simpler approach by adding all policies at once
resource keyVaultPolicies 'Microsoft.KeyVault/vaults/accessPolicies@2022-07-01' = {
  parent: keyVault
  name: 'add'
  properties: {
    accessPolicies: concat(
      !empty(functionAppPrincipalId) ? [
        {
          tenantId: subscription().tenantId
          objectId: functionAppPrincipalId
          permissions: {
            secrets: ['get', 'list']
            keys: ['get', 'list']
            certificates: ['get', 'list']
          }
        }
      ] : [],
      !empty(adminPortalPrincipalId) ? [
        {
          tenantId: subscription().tenantId
          objectId: adminPortalPrincipalId
          permissions: {
            secrets: ['get', 'list']
            keys: ['get', 'list']
            certificates: ['get', 'list']
          }
        }
      ] : []
    )
  }
}

// Outputs
output updatedKeyVaultId string = keyVault.id