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

resource wordPressUsernameSecret 'Microsoft.KeyVault/vaults/secrets@2022-07-01' = {
  name: 'WordPressAdminUsername'
  parent: keyVault
  properties: {
    contentType: 'text/plain'
    value: 'admin'  // Default value, will be updated after WordPress deployment
  }
}

resource wordPressUrlSecret 'Microsoft.KeyVault/vaults/secrets@2022-07-01' = {
  name: 'WordPressUrl'
  parent: keyVault
  properties: {
    contentType: 'text/plain'
    value: 'https://YOUR_WORDPRESS_URL'  // Will be populated after WordPress deployment
  }
}

resource wordPressApiSecret 'Microsoft.KeyVault/vaults/secrets@2022-07-01' = {
  name: 'WordPressApiKey'
  parent: keyVault
  properties: {
    contentType: 'text/plain'
    value: 'REPLACE_WITH_WORDPRESS_API_KEY'  // Will be populated after WordPress deployment
  }
}

resource wordPressDbCredentialsSecret 'Microsoft.KeyVault/vaults/secrets@2022-07-01' = {
  name: 'WordPressDbCredentials'
  parent: keyVault
  properties: {
    contentType: 'application/json'
    value: '{"host":"mysql-server","username":"admin","password":"PASSWORD","database":"wordpress"}'  // Will be populated after WordPress deployment
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