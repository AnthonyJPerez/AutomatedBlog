// Key Vault template for blog automation infrastructure
@description('Name of the Key Vault')
param keyVaultName string

@description('Azure region for the Key Vault')
param location string

@description('Tags for the Key Vault')
param tags object

@description('Object ID of the Function App Managed Identity')
param functionAppPrincipalId string

// Deploy Key Vault
resource keyVault 'Microsoft.KeyVault/vaults@2022-07-01' = {
  name: keyVaultName
  location: location
  tags: tags
  properties: {
    sku: {
      family: 'A'
      name: 'standard'
    }
    tenantId: subscription().tenantId
    enableRbacAuthorization: false
    enableSoftDelete: true
    softDeleteRetentionInDays: 90
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
    networkAcls: {
      defaultAction: 'Allow'
      bypass: 'AzureServices'
    }
  }
}

// Secret placeholders
resource openAISecretPlaceholder 'Microsoft.KeyVault/vaults/secrets@2022-07-01' = {
  name: 'OpenAIApiKey'
  parent: keyVault
  properties: {
    contentType: 'text/plain'
    value: 'REPLACE_WITH_ACTUAL_API_KEY'
  }
}

resource surferSEOSecretPlaceholder 'Microsoft.KeyVault/vaults/secrets@2022-07-01' = {
  name: 'SurferSEOApiKey'
  parent: keyVault
  properties: {
    contentType: 'text/plain'
    value: 'REPLACE_WITH_ACTUAL_API_KEY'
  }
}

resource goDaddyApiKeyPlaceholder 'Microsoft.KeyVault/vaults/secrets@2022-07-01' = {
  name: 'GoDaddyApiKey'
  parent: keyVault
  properties: {
    contentType: 'text/plain'
    value: 'REPLACE_WITH_ACTUAL_API_KEY'
  }
}

resource goDaddyApiSecretPlaceholder 'Microsoft.KeyVault/vaults/secrets@2022-07-01' = {
  name: 'GoDaddyApiSecret'
  parent: keyVault
  properties: {
    contentType: 'text/plain'
    value: 'REPLACE_WITH_ACTUAL_API_SECRET'
  }
}

resource adSenseSnippetPlaceholder 'Microsoft.KeyVault/vaults/secrets@2022-07-01' = {
  name: 'AdSenseSnippet'
  parent: keyVault
  properties: {
    contentType: 'text/plain'
    value: '<!-- Placeholder for AdSense snippet -->'
  }
}

resource wordPressAppPasswordPlaceholder 'Microsoft.KeyVault/vaults/secrets@2022-07-01' = {
  name: 'WordPressAppPassword'
  parent: keyVault
  properties: {
    contentType: 'text/plain'
    value: 'REPLACE_WITH_ACTUAL_APP_PASSWORD'
  }
}

resource ga4MeasurementIdPlaceholder 'Microsoft.KeyVault/vaults/secrets@2022-07-01' = {
  name: 'GA4MeasurementId'
  parent: keyVault
  properties: {
    contentType: 'text/plain'
    value: 'G-XXXXXXXXXX'
  }
}

// Outputs
output keyVaultId string = keyVault.id
output keyVaultName string = keyVault.name
output keyVaultUri string = keyVault.properties.vaultUri