// Storage account template for the blog automation infrastructure
@minLength(3)
@maxLength(24)
@description('Name of the storage account (3-24 chars, lowercase, no hyphens)')
param storageAccountName string

@description('Azure region for the storage account')
param location string

@description('Tags for the storage account')
param tags object = {}

@description('Storage account SKU')
@allowed([
  'Standard_LRS'
  'Standard_GRS'
  'Standard_RAGRS'
  'Standard_ZRS'
  'Premium_LRS'
  'Premium_ZRS'
])
param sku string = 'Standard_LRS'

// Deploy storage account
resource storageAccount 'Microsoft.Storage/storageAccounts@2021-09-01' = {
  name: storageAccountName
  location: location
  tags: tags
  sku: {
    name: sku
  }
  kind: 'StorageV2'
  properties: {
    accessTier: 'Cool'
    supportsHttpsTrafficOnly: true
    minimumTlsVersion: 'TLS1_2'
    allowBlobPublicAccess: false
    networkAcls: {
      bypass: 'AzureServices'
      defaultAction: 'Allow'
    }
  }
}

// Create containers
resource blobService 'Microsoft.Storage/storageAccounts/blobServices@2021-09-01' = {
  name: 'default'
  parent: storageAccount
  properties: {
    deleteRetentionPolicy: {
      enabled: true
      days: 30
    }
    containerDeleteRetentionPolicy: {
      enabled: true
      days: 30
    }
  }
}

// Container for blog data
resource blogDataContainer 'Microsoft.Storage/storageAccounts/blobServices/containers@2021-09-01' = {
  name: 'blog-data'
  parent: blobService
  properties: {
    publicAccess: 'None'
  }
}

// Container for generated content
resource generatedContainer 'Microsoft.Storage/storageAccounts/blobServices/containers@2021-09-01' = {
  name: 'generated'
  parent: blobService
  properties: {
    publicAccess: 'None'
  }
}

// Container for deployment packages
resource deploymentPackagesContainer 'Microsoft.Storage/storageAccounts/blobServices/containers@2021-09-01' = {
  name: 'deployment-packages'
  parent: blobService
  properties: {
    publicAccess: 'None'
  }
}

// Create lifecycle management policy for old content
resource lifecycleManagementPolicy 'Microsoft.Storage/storageAccounts/managementPolicies@2021-09-01' = {
  name: 'default'
  parent: storageAccount
  properties: {
    policy: {
      rules: [
        {
          name: 'DeleteOldGenerated'
          type: 'Lifecycle'
          definition: {
            filters: {
              prefixMatch: ['generated/']
              blobTypes: ['blockBlob']
            }
            actions: {
              baseBlob: {
                delete: {
                  daysAfterModificationGreaterThan: 30
                }
              }
            }
          }
        }
      ]
    }
  }
}

// Role assignment parameters
@description('Principal ID to assign Storage Blob Data Contributor role')
param deploymentPrincipalId string = '' // Will be assigned from GitHub workflow

// Add role assignment for GitHub Actions service principal
resource blobDataContributorRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = if(!empty(deploymentPrincipalId)) {
  name: guid(storageAccount.id, deploymentPrincipalId, 'ba92f5b4-2d11-453d-a403-e96b0029c9fe') // Storage Blob Data Contributor role ID
  scope: storageAccount
  properties: {
    roleDefinitionId: resourceId('Microsoft.Authorization/roleDefinitions', 'ba92f5b4-2d11-453d-a403-e96b0029c9fe') // Storage Blob Data Contributor
    principalId: deploymentPrincipalId
    principalType: 'ServicePrincipal'
  }
}

// Outputs
output storageAccountName string = storageAccount.name
output storageAccountId string = storageAccount.id
output blobEndpoint string = storageAccount.properties.primaryEndpoints.blob

// Note: We're no longer outputting storage keys directly
// Connection strings are constructed in the function app using references