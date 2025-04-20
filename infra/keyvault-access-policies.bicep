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

// Add access policy for Function App if principal ID is provided
resource functionAppAccessPolicy 'Microsoft.KeyVault/vaults/accessPolicies@2022-07-01' = if (!empty(functionAppPrincipalId)) {
  name: 'add'
  parent: keyVault
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

// Add access policy for Admin Portal if principal ID is provided
resource adminPortalAccessPolicy 'Microsoft.KeyVault/vaults/accessPolicies@2022-07-01' = if (!empty(adminPortalPrincipalId)) {
  name: 'add'
  parent: keyVault
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
    functionAppAccessPolicy // Wait for Function App access policy to be applied first
  ]
}

// Outputs
output updatedKeyVaultId string = keyVault.id