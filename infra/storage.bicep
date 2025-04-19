@description('The name of the storage account')
param storageAccountName string

@description('Location for the storage account')
param location string = resourceGroup().location

// Create storage account
resource storageAccount 'Microsoft.Storage/storageAccounts@2022-09-01' = {
  name: storageAccountName
  location: location
  sku: {
    name: 'Standard_LRS'
  }
  kind: 'StorageV2'
  properties: {
    accessTier: 'Hot'
    supportsHttpsTrafficOnly: true
    minimumTlsVersion: 'TLS1_2'
  }
}

// Create blog data container
resource blogDataContainer 'Microsoft.Storage/storageAccounts/blobServices/containers@2022-09-01' = {
  name: '${storageAccount.name}/default/blog-data'
  properties: {
    publicAccess: 'None'
  }
}

// Create configuration container
resource configContainer 'Microsoft.Storage/storageAccounts/blobServices/containers@2022-09-01' = {
  name: '${storageAccount.name}/default/configuration'
  properties: {
    publicAccess: 'None'
  }
}

// Create results container
resource resultsContainer 'Microsoft.Storage/storageAccounts/blobServices/containers@2022-09-01' = {
  name: '${storageAccount.name}/default/results'
  properties: {
    publicAccess: 'None'
  }
}

// Outputs
output storageAccountName string = storageAccount.name
output storageAccountKey string = listKeys(storageAccount.id, storageAccount.apiVersion).keys[0].value
output blogDataContainerName string = blogDataContainer.name
output configContainerName string = configContainer.name
output resultsContainerName string = resultsContainer.name
