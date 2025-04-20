// Post-deployment configuration for admin portal
@description('Name of the Azure Function App')
param functionAppName string

@description('Resource group name')
param resourceGroupName string = resourceGroup().name

@description('Location for deployment')
param location string = resourceGroup().location

// Deployment script to configure Function App for admin portal
resource configureAdminPortal 'Microsoft.Resources/deploymentScripts@2020-10-01' = {
  name: '${functionAppName}-admin-portal-config'
  location: location
  kind: 'AzureCLI'
  // Remove identity block to avoid deployment issues
  properties: {
    azCliVersion: '2.30.0'
    retentionInterval: 'P1D'
    timeout: 'PT30M'
    scriptContent: '''
      #!/bin/bash
      
      echo "Configuring admin portal for $FUNCTION_APP_NAME in $RESOURCE_GROUP..."
      
      # Update the site configuration
      echo "Updating site configuration..."
      az webapp config set \
        --resource-group $RESOURCE_GROUP \
        --name $FUNCTION_APP_NAME \
        --linux-fx-version "PYTHON|3.11" \
        --startup-file "gunicorn --bind=0.0.0.0:5000 --timeout 600 main:app"
      
      # Update routing configuration to make sure default document is served
      echo "Updating default document routing configuration..."
      az webapp config set \
        --resource-group $RESOURCE_GROUP \
        --name $FUNCTION_APP_NAME \
        --default-documents "index.html" "index.htm" "default.html" "default.htm" "hostingstart.html"
      
      # Set HTTP handlers properly
      echo "Configuring HTTP handlers..."
      az webapp config set \
        --resource-group $RESOURCE_GROUP \
        --name $FUNCTION_APP_NAME \
        --generic-configurations '{"httpLoggingEnabled": true, "detailedErrorLoggingEnabled": true}'
      
      # Restart the web app to apply changes
      echo "Restarting web app to apply changes..."
      az webapp restart --resource-group $RESOURCE_GROUP --name $FUNCTION_APP_NAME
      
      echo "Admin portal configuration completed. The portal should be available shortly at: https://$FUNCTION_APP_NAME.azurewebsites.net/"
    '''
    environmentVariables: [
      {
        name: 'FUNCTION_APP_NAME'
        value: functionAppName
      }
      {
        name: 'RESOURCE_GROUP'
        value: resourceGroupName
      }
    ]
  }
}

// Output
output message string = 'Post-deployment configuration for admin portal completed'