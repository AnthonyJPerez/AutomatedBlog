// Post-deployment configuration for admin portal using declarative approach
@description('Name of the web app to configure')
@minLength(2)
@maxLength(60)
param webAppName string

@description('Location for deployment')
param location string = resourceGroup().location

@description('Python version to use')
@allowed(['3.10', '3.11', '3.12'])
param pythonVersion string = '3.11'

// Instead of using a DeploymentScript, configure the web app directly
// Update the site configuration with proper Python version and startup command
resource siteConfig 'Microsoft.Web/sites/config@2021-02-01' = {
  name: '${webAppName}/web'
  properties: {
    linuxFxVersion: 'PYTHON|${pythonVersion}'
    appCommandLine: 'gunicorn --bind=0.0.0.0:5000 --timeout 600 main:app'
    defaultDocuments: [
      'index.html'
      'index.htm'
      'default.html'
      'default.htm'
      'hostingstart.html'
    ]
    ftpsState: 'Disabled'
    minTlsVersion: '1.2'
    http20Enabled: true
    alwaysOn: true
  }
}

// Add logs configuration
resource logsConfig 'Microsoft.Web/sites/config@2021-02-01' = {
  name: '${webAppName}/logs'
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
  dependsOn: [
    siteConfig
  ]
}

// Add application settings
resource appSettings 'Microsoft.Web/sites/config@2021-02-01' = {
  name: '${webAppName}/appsettings'
  properties: {
    // Environment-specific settings
    SCM_DO_BUILD_DURING_DEPLOYMENT: 'true'
    WEBSITES_ENABLE_APP_SERVICE_STORAGE: 'true'
    ENABLE_ORYX_BUILD: 'true'
    PYTHONPATH: '/home/site/wwwroot'
    FLASK_APP: 'main.py'
    WEBSITE_HTTPLOGGING_RETENTION_DAYS: '7'
  }
  dependsOn: [
    siteConfig
    logsConfig
  ]
}

// Output
output message string = 'Post-deployment configuration for web app completed'