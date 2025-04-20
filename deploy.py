import os
import json
import argparse
import time
import logging
from azure.identity import ClientSecretCredential
from azure.mgmt.resource import ResourceManagementClient
from azure.mgmt.resource.resources.models import DeploymentProperties
from azure.core.exceptions import HttpResponseError

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger('deploy')

def get_credentials():
    """Get Azure credentials from environment variables"""
    tenant_id = os.environ.get("AZURE_TENANT_ID")
    client_id = os.environ.get("AZURE_CLIENT_ID")
    client_secret = os.environ.get("AZURE_CLIENT_SECRET")
    
    if not all([tenant_id, client_id, client_secret]):
        logger.error("Missing Azure credentials. Please set AZURE_TENANT_ID, AZURE_CLIENT_ID, and AZURE_CLIENT_SECRET environment variables.")
        return None
    
    return ClientSecretCredential(
        tenant_id=tenant_id,
        client_id=client_id,
        client_secret=client_secret
    )

def deploy_resources(resource_group_name, location="eastus", env_name="dev", project_name="blogauto"):
    """
    Deploy Azure resources using Bicep templates.
    
    Parameters:
        resource_group_name: Name of the resource group
        location: Azure region (default: eastus)
        env_name: Environment name for naming resources (default: dev)
        project_name: Project name for resource naming (default: blogauto)
    
    Returns:
        bool: True if deployment successful, False otherwise
    """
    # Get Azure credentials
    credential = get_credentials()
    if not credential:
        return False
    
    # Get subscription ID
    subscription_id = os.environ.get("AZURE_SUBSCRIPTION_ID")
    if not subscription_id:
        logger.error("Missing AZURE_SUBSCRIPTION_ID environment variable.")
        return False
    
    # Initialize Resource Management Client
    resource_client = ResourceManagementClient(credential, subscription_id)
    
    try:
        # Create resource group if it doesn't exist
        logger.info(f"Creating resource group {resource_group_name} in {location}...")
        resource_client.resource_groups.create_or_update(
            resource_group_name,
            {"location": location}
        )
        
        # Deploy resources using Bicep templates
        # First, deploy the main.bicep template
        logger.info("Deploying resources from main.bicep...")
        
        # Prepare the deployment properties
        params = {
            "projectName": {"value": project_name},
            "environment": {"value": env_name},
            "location": {"value": location}
        }
        
        deployment_properties = DeploymentProperties(
            mode="Incremental",
            template_file="infra/main.bicep",
            parameters=params
        )
        
        # Start the deployment
        deployment_async_operation = resource_client.deployments.begin_create_or_update(
            resource_group_name,
            f"deployment-{int(time.time())}",
            {"properties": deployment_properties}
        )
        
        # Wait for deployment to complete
        deployment_result = deployment_async_operation.result()
        
        # Check deployment status
        if deployment_result.properties.provisioning_state == "Succeeded":
            logger.info("Deployment completed successfully!")
            
            # Print outputs
            if deployment_result.properties.outputs:
                logger.info("Deployment outputs:")
                for key, value in deployment_result.properties.outputs.items():
                    logger.info(f"  {key}: {value['value']}")
            
            return True
        else:
            logger.error(f"Deployment failed: {deployment_result.properties.provisioning_state}")
            return False
        
    except HttpResponseError as e:
        logger.error(f"Azure API error: {e}")
        return False
    except Exception as e:
        logger.error(f"Deployment error: {e}")
        return False

def main():
    """Main entry point for deployment script"""
    parser = argparse.ArgumentParser(description="Deploy Azure resources for blog automation pipeline")
    parser.add_argument("--resource-group", "-g", type=str, required=True, help="Resource group name")
    parser.add_argument("--location", "-l", type=str, default="eastus", help="Azure region (default: eastus)")
    parser.add_argument("--environment", "-e", type=str, default="dev", help="Environment name (default: dev)")
    
    args = parser.parse_args()
    
    # Deploy resources
    success = deploy_resources(args.resource_group, args.location, args.environment)
    
    # Exit with appropriate status code
    if success:
        logger.info("Deployment completed successfully!")
    else:
        logger.error("Deployment failed!")
        exit(1)

if __name__ == "__main__":
    main()