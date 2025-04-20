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

// Add access policies using the dedicated endpoint rather than updating the vault directly
resource functionAppAccessPolicy 'Microsoft.KeyVault/vaults/accessPolicies@2022-07-01' = if (!empty(functionAppPrincipalId)) {
  name: '${keyVaultName}/add'
  properties: {
    accessPolicies: [
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
    ]
  }
}

resource adminPortalAccessPolicy 'Microsoft.KeyVault/vaults/accessPolicies@2022-07-01' = if (!empty(adminPortalPrincipalId)) {
  name: '${keyVaultName}/add'
  properties: {
    accessPolicies: [
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
    ]
  }
  dependsOn: [
    functionAppAccessPolicy
  ]
}

// Outputs
output updatedKeyVaultId string = keyVault.id