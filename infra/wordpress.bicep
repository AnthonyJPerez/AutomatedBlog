@description('The name of the WordPress site')
param siteName string

@description('The name of the App Service Plan')
param appServicePlanName string = '${siteName}-plan'

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

var mysqlServerName = '${toLower(siteName)}-mysql'
var databaseName = 'wordpress'

// Create App Service Plan
resource appServicePlan 'Microsoft.Web/serverfarms@2022-03-01' = {
  name: appServicePlanName
  location: location
  sku: {
    name: sku
  }
  properties: {
    reserved: true // For Linux
  }
}

// Create MySQL Server
resource mysqlServer 'Microsoft.DBforMySQL/flexibleServers@2022-01-01' = {
  name: mysqlServerName
  location: location
  sku: {
    name: contains(sku, 'P') ? 'Standard_D2ds_v4' : 'Standard_B1ms'
    tier: contains(sku, 'P') ? 'GeneralPurpose' : 'Burstable'
  }
  properties: {
    version: '8.0.21'
    administratorLogin: administratorLogin
    administratorLoginPassword: administratorLoginPassword
    storage: {
      storageSizeGB: 20
      autoGrow: 'Enabled'
    }
    backup: {
      backupRetentionDays: 7
      geoRedundantBackup: 'Disabled'
    }
    highAvailability: {
      mode: 'Disabled'
    }
  }
}

// Create MySQL Database
resource mysqlDatabase 'Microsoft.DBforMySQL/flexibleServers/databases@2022-01-01' = {
  parent: mysqlServer
  name: databaseName
  properties: {
    charset: 'utf8'
    collation: 'utf8_general_ci'
  }
}

// Create MySQL Firewall Rule to allow Azure services
resource mysqlFirewallRule 'Microsoft.DBforMySQL/flexibleServers/firewallRules@2022-01-01' = {
  parent: mysqlServer
  name: 'AllowAzureServices'
  properties: {
    startIpAddress: '0.0.0.0'
    endIpAddress: '0.0.0.0'
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
    siteConfig: {
      linuxFxVersion: 'DOCKER|wordpress:latest'
      appSettings: [
        {
          name: 'WEBSITES_ENABLE_APP_SERVICE_STORAGE'
          value: 'true'
        }
        {
          name: 'WORDPRESS_DB_HOST'
          value: '${mysqlServer.name}.mysql.database.azure.com'
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
          value: 'define(\'WP_HOME\', \'https://${siteName}.azurewebsites.net\');define(\'WP_SITEURL\', \'https://${siteName}.azurewebsites.net\');'
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
        // Add additional WordPress config for performance and security
        {
          name: 'WORDPRESS_CONFIG_EXTRA_PERFORMANCE'
          value: 'define(\'WP_MEMORY_LIMIT\', \'256M\');define(\'WP_MAX_MEMORY_LIMIT\', \'512M\');'
        }
        {
          name: 'WEBSITES_CONTAINER_START_TIME_LIMIT'
          value: '600'
        }
      ]
      alwaysOn: contains(sku, 'P') || contains(sku, 'S') ? true : false
    }
    httpsOnly: true
  }
}

// No need for additional identity setup since we're using SystemAssigned identity
// which is already configured on the wordpressApp resource

// Setup WordPress plugins deployment script (runs once after WordPress is deployed)
resource deploymentScript 'Microsoft.Resources/deploymentScripts@2020-10-01' = {
  name: '${siteName}-wp-plugins-setup'
  location: location
  kind: 'AzureCLI'
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    azCliVersion: '2.30.0'
    retentionInterval: 'P1D'
    timeout: 'PT30M'
    scriptContent: '''
      #!/bin/bash
      # Wait for WordPress to be fully deployed
      sleep 180
      
      # Install recommended plugins via WP-CLI
      # Connect to the WordPress container and install plugins
      az webapp ssh --resource-group $RESOURCE_GROUP --name $SITE_NAME --command "wp plugin install wordpress-seo jetpack contact-form-7 wordfence google-analytics-for-wordpress --activate"
      
      # Set up permalink structure for SEO
      az webapp ssh --resource-group $RESOURCE_GROUP --name $SITE_NAME --command "wp rewrite structure '/%postname%/'"
      
      # Optimize WordPress settings
      az webapp ssh --resource-group $RESOURCE_GROUP --name $SITE_NAME --command "wp option update blog_public 0" # Discourage search engines until site is ready
      
      # Install additional performance plugins
      az webapp ssh --resource-group $RESOURCE_GROUP --name $SITE_NAME --command "wp plugin install wp-super-cache autoptimize --activate"
      
      # Configure WP Super Cache settings
      az webapp ssh --resource-group $RESOURCE_GROUP --name $SITE_NAME --command "wp super-cache enable"
      
      # Enable WordPress Multisite
      echo "Enabling WordPress Multisite..."
      # Add WP_ALLOW_MULTISITE to wp-config.php
      az webapp ssh --resource-group $RESOURCE_GROUP --name $SITE_NAME --command "wp config set WP_ALLOW_MULTISITE true --raw=true"
      
      # Configure multisite
      az webapp ssh --resource-group $RESOURCE_GROUP --name $SITE_NAME --command "wp core multisite-convert --subdomains=false --title='Blog Network' --base='/'"
      
      # Enable subdirectory URLs by default
      az webapp ssh --resource-group $RESOURCE_GROUP --name $SITE_NAME --command "wp config set SUBDOMAIN_INSTALL false --raw=true"
      
      # Add required multisite constants to wp-config.php
      az webapp ssh --resource-group $RESOURCE_GROUP --name $SITE_NAME --command "wp config set DOMAIN_CURRENT_SITE '\$_SERVER[\"HTTP_HOST\"]' --raw=true"
      az webapp ssh --resource-group $RESOURCE_GROUP --name $SITE_NAME --command "wp config set PATH_CURRENT_SITE '/' --raw=true"
      az webapp ssh --resource-group $RESOURCE_GROUP --name $SITE_NAME --command "wp config set SITE_ID_CURRENT_SITE 1 --raw=true"
      az webapp ssh --resource-group $RESOURCE_GROUP --name $SITE_NAME --command "wp config set BLOG_ID_CURRENT_SITE 1 --raw=true"
      
      # Install domain mapping plugin for custom domains
      az webapp ssh --resource-group $RESOURCE_GROUP --name $SITE_NAME --command "wp plugin install mercator --activate --network"
      
      echo "WordPress Multisite installation and plugins setup completed"
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
    ]
  }
  dependsOn: [
    wordpressApp
  ]
}

// Update Key Vault with WordPress credentials
@description('Name of the Key Vault to store WordPress credentials')
param keyVaultName string

// Add a deployment script to update Key Vault with WordPress credentials
resource updateKeyVaultWithWordPressCredentials 'Microsoft.Resources/deploymentScripts@2020-10-01' = {
  name: '${siteName}-update-keyvault'
  location: location
  kind: 'AzureCLI'
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    azCliVersion: '2.30.0'
    retentionInterval: 'P1D'
    timeout: 'PT30M'
    scriptContent: '''
      #!/bin/bash
      
      # Wait for WordPress to be fully deployed
      sleep 180
      
      # Generate WordPress application password for API access
      WP_APP_PASSWORD=$(openssl rand -base64 20 | tr -dc 'a-zA-Z0-9' | fold -w 20 | head -n 1)
      
      # Create WordPress application password
      az webapp ssh --resource-group $RESOURCE_GROUP --name $SITE_NAME --command "wp user application-password create $WP_ADMIN_USERNAME 'Content-API' --porcelain" > app_password.txt
      
      if [ -s app_password.txt ]; then
        WP_APP_PASSWORD=$(cat app_password.txt)
        echo "Successfully created WordPress application password"
      else
        echo "Failed to create WordPress application password, using generated one"
      fi
      
      # Update Key Vault secrets with WordPress information
      az keyvault secret set --vault-name $KEY_VAULT_NAME --name 'WordPressUrl' --value "https://$SITE_NAME.azurewebsites.net"
      az keyvault secret set --vault-name $KEY_VAULT_NAME --name 'WordPressAdminUsername' --value "$WP_ADMIN_USERNAME"
      az keyvault secret set --vault-name $KEY_VAULT_NAME --name 'WordPressAppPassword' --value "$WP_APP_PASSWORD"
      
      # Store MySQL credentials
      DB_CREDENTIALS="{\"host\":\"$MYSQL_SERVER.mysql.database.azure.com\",\"username\":\"$DB_ADMIN_USERNAME\",\"password\":\"$DB_ADMIN_PASSWORD\",\"database\":\"wordpress\"}"
      az keyvault secret set --vault-name $KEY_VAULT_NAME --name 'WordPressDbCredentials' --value "$DB_CREDENTIALS"
      
      # Store WordPress Multisite information
      az keyvault secret set --vault-name $KEY_VAULT_NAME --name 'WordPressIsMultisite' --value "true"
      
      # Get the site ID of the main network
      NETWORK_ID=$(az webapp ssh --resource-group $RESOURCE_GROUP --name $SITE_NAME --command "wp site list --field=blog_id --skip-plugins --skip-themes" | head -n 1)
      if [ -n "$NETWORK_ID" ]; then
        az keyvault secret set --vault-name $KEY_VAULT_NAME --name 'WordPressNetworkId' --value "$NETWORK_ID"
      fi
      
      # Store basic information about the Multisite configuration 
      MULTISITE_CONFIG="{\"is_multisite\":true,\"subdirectory_install\":true,\"network_id\":$NETWORK_ID,\"domain_mapping_plugin\":\"mercator\"}"
      az keyvault secret set --vault-name $KEY_VAULT_NAME --name 'WordPressMultisiteConfig' --value "$MULTISITE_CONFIG"
      
      echo "WordPress credentials and Multisite information stored in Key Vault"
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
        value: mysqlServer.name
      }
      {
        name: 'DB_ADMIN_USERNAME'
        value: administratorLogin
      }
      {
        name: 'DB_ADMIN_PASSWORD'
        secureValue: administratorLoginPassword
      }
    ]
  }
  dependsOn: [
    deploymentScript
    wordpressApp
  ]
}

// Outputs that can be used by other resources
output wordpressUrl string = 'https://${wordpressApp.properties.defaultHostName}'
output mysqlHostname string = '${mysqlServer.name}.mysql.database.azure.com'
output serverPrincipalId string = wordpressApp.identity.principalId