// MySQL Flexible Server module for WordPress
@description('The name of the MySQL server')
@minLength(3)
@maxLength(63)
param serverName string

@description('The location for the MySQL server')
param location string = resourceGroup().location

@description('The SKU tier for the MySQL server')
@allowed(['Burstable', 'GeneralPurpose', 'MemoryOptimized'])
param skuTier string = 'Burstable'

@description('The name of the SKU for the MySQL server')
param skuName string = 'Standard_B1ms'

@description('Database administrator login name')
@minLength(1)
param administratorLogin string

@description('Database administrator password')
@minLength(8)
@secure()
param administratorLoginPassword string

@description('Database name')
@minLength(1)
param databaseName string = 'wordpress'

@description('Storage size in GB')
@minValue(20)
@maxValue(16384)
param storageSizeGB int = 20

@description('Backup retention days')
@minValue(1)
@maxValue(35)
param backupRetentionDays int = 7

@description('Enable geo-redundant backup')
param geoRedundantBackup bool = false

@description('Enable high availability')
param highAvailability bool = false

// Create MySQL Server
resource mysqlServer 'Microsoft.DBforMySQL/flexibleServers@2022-01-01' = {
  name: serverName
  location: location
  sku: {
    name: skuName
    tier: skuTier
  }
  properties: {
    version: '8.0.21'
    administratorLogin: administratorLogin
    administratorLoginPassword: administratorLoginPassword
    storage: {
      storageSizeGB: storageSizeGB
      autoGrow: 'Enabled'
    }
    backup: {
      backupRetentionDays: backupRetentionDays
      geoRedundantBackup: geoRedundantBackup ? 'Enabled' : 'Disabled'
    }
    highAvailability: {
      mode: highAvailability ? 'ZoneRedundant' : 'Disabled'
    }
  }
}

// Create MySQL Database
resource mysqlDatabase 'Microsoft.DBforMySQL/flexibleServers/databases@2022-01-01' = {
  parent: mysqlServer
  name: databaseName
  properties: {
    charset: 'utf8mb4'
    collation: 'utf8mb4_unicode_ci'
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

// Outputs
output serverName string = mysqlServer.name
output serverFqdn string = '${mysqlServer.name}.mysql.database.azure.com'
output databaseName string = databaseName