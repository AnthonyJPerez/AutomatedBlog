// WordPress with MySQL Template - Updated with Declarative Approach
@description('The name of the WordPress site')
@minLength(3)
@maxLength(63)
param siteName string

@description('The name of the App Service Plan')
param appServicePlanName string = ''

@description('The location for all resources')
param location string = resourceGroup().location

@description('The SKU of App Service Plan')
@allowed([
  'B1'
  'B2'
  'B3'
  'S1'
  'S2'
  'S3'
  'P1v2'
  'P2v2'
  'P3v2'
])
param sku string = 'P1v2'

@description('Database administrator login name')
@minLength(1)
param administratorLogin string

@description('Database administrator password')
@minLength(8)
@secure()
param administratorLoginPassword string

@description('WordPress admin email address')
param wpAdminEmail string

@description('WordPress admin username')
param wpAdminUsername string = 'admin'

@description('WordPress admin password')
@secure()
param wpAdminPassword string

@description('Enable WordPress Multisite')
param enableMultisite bool = true

@description('Name of the Key Vault to store WordPress credentials')
param keyVaultName string

// Variables
var mysqlServerName = '${toLower(siteName)}-mysql'
var databaseName = 'wordpress'
var wpPlanName = !empty(appServicePlanName) ? appServicePlanName : '${siteName}-plan'
var multisiteConfig = enableMultisite ? 'define(\'WP_ALLOW_MULTISITE\', true);define(\'SUBDOMAIN_INSTALL\', false);define(\'DOMAIN_CURRENT_SITE\', $_SERVER["HTTP_HOST"]);define(\'PATH_CURRENT_SITE\', \'/\');define(\'SITE_ID_CURRENT_SITE\', 1);define(\'BLOG_ID_CURRENT_SITE\', 1);' : ''

// Create App Service Plan
resource appServicePlan 'Microsoft.Web/serverfarms@2022-03-01' = {
  name: wpPlanName
  location: location
  sku: {
    name: sku
  }
  properties: {
    reserved: true // For Linux
  }
}

// Create MySQL using the modular template
module mysqlModule 'mysql.bicep' = {
  name: 'mysqlDeployment-${siteName}'
  params: {
    serverName: mysqlServerName
    location: location
    skuTier: contains(sku, 'P') ? 'GeneralPurpose' : 'Burstable'
    skuName: contains(sku, 'P') ? 'Standard_D2ds_v4' : 'Standard_B1ms'
    administratorLogin: administratorLogin
    administratorLoginPassword: administratorLoginPassword
    databaseName: databaseName
    storageSizeGB: 20
    backupRetentionDays: 7
    geoRedundantBackup: false
    highAvailability: false
  }
}

// Create WordPress Web App
resource wordpressApp 'Microsoft.Web/sites@2022-03-01' = {
  name: siteName
  location: location
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    serverFarmId: appServicePlan.id
    httpsOnly: true
    siteConfig: {
      linuxFxVersion: 'DOCKER|wordpress:latest'
      alwaysOn: contains(sku, 'P') || contains(sku, 'S') ? true : false
      ftpsState: 'Disabled'
      minTlsVersion: '1.2'
      http20Enabled: true
      webSocketsEnabled: true
      appSettings: [
        {
          name: 'WEBSITES_ENABLE_APP_SERVICE_STORAGE'
          value: 'true'
        }
        {
          name: 'WEBSITES_CONTAINER_START_TIME_LIMIT'
          value: '600'
        }
        {
          name: 'WORDPRESS_DB_HOST'
          value: mysqlModule.outputs.serverFqdn
        }
        {
          name: 'WORDPRESS_DB_USER'
          value: administratorLogin
        }
        {
          name: 'WORDPRESS_DB_PASSWORD'
          value: administratorLoginPassword
        }
        {
          name: 'WORDPRESS_DB_NAME'
          value: databaseName
        }
        {
          name: 'WORDPRESS_CONFIG_EXTRA'
          value: 'define(\'WP_HOME\', \'https://${siteName}.azurewebsites.net\');define(\'WP_SITEURL\', \'https://${siteName}.azurewebsites.net\');${multisiteConfig}define(\'WP_MEMORY_LIMIT\', \'256M\');define(\'WP_MAX_MEMORY_LIMIT\', \'512M\');'
        }
        {
          name: 'WORDPRESS_ADMIN_EMAIL'
          value: wpAdminEmail
        }
        {
          name: 'WORDPRESS_ADMIN_USER'
          value: wpAdminUsername
        }
        {
          name: 'WORDPRESS_ADMIN_PASSWORD'
          value: wpAdminPassword
        }
      ]
    }
  }
}

// Add logs configuration
resource wordpressLogsConfig 'Microsoft.Web/sites/config@2022-03-01' = {
  parent: wordpressApp
  name: 'logs'
  properties: {
    applicationLogs: {
      fileSystem: {
        level: 'Information'
      }
    }
    httpLogs: {
      fileSystem: {
        enabled: true
        retentionInDays: 7
        retentionInMb: 35
      }
    }
    detailedErrorMessages: {
      enabled: true
    }
    failedRequestsTracing: {
      enabled: true
    }
  }
}

// Add Key Vault access policy for WordPress app identity
resource keyVaultAccessPolicy 'Microsoft.KeyVault/vaults/accessPolicies@2022-07-01' = {
  name: '${keyVaultName}/add'
  properties: {
    accessPolicies: [
      {
        tenantId: subscription().tenantId
        objectId: wordpressApp.identity.principalId
        permissions: {
          secrets: [
            'get'
            'set'
            'list'
          ]
        }
      }
    ]
  }
}

// Store WordPress configuration in Key Vault
resource wordpressUrlSecret 'Microsoft.KeyVault/vaults/secrets@2022-07-01' = {
  name: '${keyVaultName}/WordPressUrl'
  properties: {
    value: 'https://${wordpressApp.properties.defaultHostName}'
  }
  dependsOn: [
    keyVaultAccessPolicy
  ]
}

resource wordpressAdminUsernameSecret 'Microsoft.KeyVault/vaults/secrets@2022-07-01' = {
  name: '${keyVaultName}/WordPressAdminUsername'
  properties: {
    value: wpAdminUsername
  }
  dependsOn: [
    keyVaultAccessPolicy
  ]
}

resource wordpressMultisiteConfigSecret 'Microsoft.KeyVault/vaults/secrets@2022-07-01' = if (enableMultisite) {
  name: '${keyVaultName}/WordPressIsMultisite'
  properties: {
    value: 'true'
  }
  dependsOn: [
    keyVaultAccessPolicy
  ]
}

// As you recommended, only use DeploymentScript for one-time plugin setup
resource wordpressPluginSetup 'Microsoft.Resources/deploymentScripts@2020-10-01' = {
  name: '${siteName}-plugin-setup'
  location: location
  kind: 'AzureCLI'
  properties: {
    azCliVersion: '2.40.0'
    retentionInterval: 'P1D'
    timeout: 'PT30M'
    // Better practice: Store this script externally, but we'll inline for simplicity
    scriptContent: '''
      #!/bin/bash
      # Wait for WordPress container to be fully initialized
      echo "Waiting for WordPress to be fully deployed..."
      sleep 180
      
      # Install essential plugins only - move most configuration to container creation time
      echo "Installing WordPress plugins..."
      az webapp ssh --resource-group $RESOURCE_GROUP --name $SITE_NAME --command "wp plugin install wordpress-seo jetpack contact-form-7 wordfence google-analytics-for-wordpress --activate"
      
      # Configure permalink structure for SEO
      echo "Configuring permalink structure..."
      az webapp ssh --resource-group $RESOURCE_GROUP --name $SITE_NAME --command "wp rewrite structure '/%postname%/'"
      
      if [ "$ENABLE_MULTISITE" = "true" ]; then
        # Configure multisite if not already done through environment variables
        echo "Configuring WordPress Multisite..."
        az webapp ssh --resource-group $RESOURCE_GROUP --name $SITE_NAME --command "wp core multisite-convert --subdomains=false --title='Blog Network' --base='/'"
        
        # Install domain mapping plugin for custom domains
        echo "Installing domain mapping plugin..."
        az webapp ssh --resource-group $RESOURCE_GROUP --name $SITE_NAME --command "wp plugin install mercator --activate --network"
      fi
      
      # Create WordPress application password for API access
      echo "Creating WordPress application password..."
      WP_APP_PASSWORD=$(az webapp ssh --resource-group $RESOURCE_GROUP --name $SITE_NAME --command "wp user application-password create $WP_ADMIN_USERNAME 'Content-API' --porcelain" | tr -d '\r\n')
      
      # Store the app password in Key Vault if we got a valid one
      if [ -n "$WP_APP_PASSWORD" ]; then
        echo "Storing WordPress application password in Key Vault..."
        az keyvault secret set --vault-name $KEY_VAULT_NAME --name 'WordPressAppPassword' --value "$WP_APP_PASSWORD"
      else
        echo "Failed to create WordPress application password"
      fi
      
      # Store database connection info in Key Vault
      echo "Storing database connection information in Key Vault..."
      DB_CREDENTIALS=$(cat << EOF
      {
        "host": "$MYSQL_SERVER",
        "username": "$DB_ADMIN_USERNAME",
        "password": "$DB_ADMIN_PASSWORD", 
        "database": "$DB_NAME"
      }
      EOF
      )
      
      az keyvault secret set --vault-name $KEY_VAULT_NAME --name 'WordPressDbCredentials' --value "$DB_CREDENTIALS"
      
      echo "WordPress configuration completed successfully."
    '''
    environmentVariables: [
      {
        name: 'SITE_NAME'
        value: siteName
      }
      {
        name: 'RESOURCE_GROUP'
        value: resourceGroup().name
      }
      {
        name: 'KEY_VAULT_NAME'
        value: keyVaultName
      }
      {
        name: 'WP_ADMIN_USERNAME'
        value: wpAdminUsername
      }
      {
        name: 'MYSQL_SERVER'
        value: mysqlModule.outputs.serverFqdn
      }
      {
        name: 'DB_ADMIN_USERNAME'
        value: administratorLogin
      }
      {
        name: 'DB_ADMIN_PASSWORD'
        secureValue: administratorLoginPassword
      }
      {
        name: 'DB_NAME'
        value: databaseName
      }
      {
        name: 'ENABLE_MULTISITE'
        value: string(enableMultisite)
      }
    ]
  }
  dependsOn: [
    wordpressApp
    keyVaultAccessPolicy
  ]
}

// Outputs that can be used by other resources
output wordpressUrl string = 'https://${wordpressApp.properties.defaultHostName}'
output mysqlHostname string = mysqlModule.outputs.serverFqdn
output serverPrincipalId string = wordpressApp.identity.principalId