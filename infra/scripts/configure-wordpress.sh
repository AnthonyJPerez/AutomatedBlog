#!/bin/bash
# WordPress configuration script for Azure Bicep deployment
# This script is meant to be used with the scriptUri parameter in the deploymentScript resource

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