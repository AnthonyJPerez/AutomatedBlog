#!/usr/bin/env python3
"""
Consolidated deployment script for Azure resources.
This script combines the functionality of the various deployment scripts
to provide a single, clean interface for deploying resources.

Usage:
  python deploy-consolidated.py --resource-group <resource-group-name> [options]

Options:
  --resource-group, -g  (Required) Name of the Azure resource group
  --location, -l        Azure region location (default: eastus, recommend westus for prod)
  --environment, -e     Environment name for resources (default: dev)
  --project-name, -p    Project name for resource naming (default: blogauto)
  --use-azure-sdk       Use Azure SDK instead of CLI (useful for CI/CD)
  --verbose, -v         Enable verbose logging
  --deploy-wordpress    Flag to deploy WordPress with multisite capabilities
"""

import os
import sys
import argparse
import logging
import time
import subprocess
from pathlib import Path

# SDK imports - only used when --use-azure-sdk flag is set
try:
    from azure.identity import ClientSecretCredential
    from azure.mgmt.resource import ResourceManagementClient
    from azure.mgmt.resource.resources.models import DeploymentProperties
    from azure.core.exceptions import HttpResponseError
    SDK_AVAILABLE = True
except ImportError:
    SDK_AVAILABLE = False

# Set up logging
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('deployment')

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

def deploy_with_sdk(resource_group_name, location="eastus", env_name="dev", project_name="blogauto"):
    """
    Deploy Azure resources using Azure SDK.
    
    Parameters:
        resource_group_name: Name of the resource group
        location: Azure region (default: eastus)
        env_name: Environment name for naming resources (default: dev)
        project_name: Project name for resource naming (default: blogauto)
    
    Returns:
        bool: True if deployment successful, False otherwise
    """
    if not SDK_AVAILABLE:
        logger.error("Azure SDK not available. Install with: pip install azure-identity azure-mgmt-resource")
        return False
        
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

def deploy_with_cli(resource_group_name, location="eastus", env_name="dev", project_name="blogauto", verbose=False, deploy_wordpress=False):
    """
    Deploy Azure resources using az CLI and Bicep templates.
    
    Parameters:
        resource_group_name: Name of the resource group
        location: Azure region (default: eastus)
        env_name: Environment name for naming resources (default: dev)
        project_name: Project name for resource naming (default: blogauto)
        verbose: Enable verbose logging (default: False)
        deploy_wordpress: Flag to deploy WordPress (default: False)
    
    Returns:
        bool: True if deployment successful, False otherwise
    """
    if not resource_group_name:
        raise ValueError("Resource group name cannot be empty!")
    
    if not project_name:
        raise ValueError("Project name cannot be empty!")
        
    logger.info(f"Deploying to resource group: {resource_group_name}")
    logger.info(f"Project name: {project_name}")
    logger.info(f"Environment: {env_name}")
    logger.info(f"Location: {location}")
    logger.info(f"Deploy WordPress: {deploy_wordpress}")
    
    # Ensure resource group exists
    try:
        logger.info(f"Checking if resource group {resource_group_name} exists...")
        result = subprocess.run(
            ["az", "group", "exists", "--name", resource_group_name],
            capture_output=True,
            text=True,
            check=True
        )
        
        if "true" not in result.stdout.lower():
            logger.info(f"Creating resource group {resource_group_name}...")
            subprocess.run(
                ["az", "group", "create", "--name", resource_group_name, "--location", location],
                check=True
            )
    except subprocess.CalledProcessError as e:
        logger.error(f"Error checking/creating resource group: {e}")
        return False
    
    # Deploy using Bicep
    try:
        template_path = Path("infra/main.bicep").absolute()
        if not template_path.exists():
            logger.error(f"Template file not found: {template_path}")
            return False
            
        logger.info(f"Deploying Bicep template {template_path}...")
        cmd = [
            "az", "deployment", "group", "create",
            "--resource-group", resource_group_name,
            "--template-file", str(template_path),
            "--parameters", f"projectName={project_name}",
            "--parameters", f"environment={env_name}",
            "--parameters", f"location={location}"
        ]
        
        # Add WordPress deployment parameter if enabled
        if deploy_wordpress:
            cmd.extend(["--parameters", "deployWordPress=true"])
            logger.info("WordPress deployment enabled")
        
        # Add debug flag for verbose mode
        if verbose:
            cmd.append("--debug")
            logger.debug(f"Running command with debug output: {' '.join(cmd)}")
        
        subprocess.run(cmd, check=True)
        logger.info("Deployment completed successfully")
        return True
    except subprocess.CalledProcessError as e:
        logger.error(f"Deployment failed: {e}")
        return False

def main():
    """Main entry point for deployment script"""
    parser = argparse.ArgumentParser(description='Deploy Azure resources')
    parser.add_argument('--resource-group', '-g', required=True, 
                        help='Azure resource group name')
    parser.add_argument('--location', '-l', default='eastus',
                        help='Azure region (default: eastus)')
    parser.add_argument('--environment', '-e', default='dev',
                        help='Environment name (default: dev)')
    parser.add_argument('--project-name', '-p', default='blogauto',
                        help='Project name (default: blogauto)')
    parser.add_argument('--use-azure-sdk', action='store_true',
                        help='Use Azure SDK instead of CLI (useful for CI/CD)')
    parser.add_argument('--verbose', '-v', action='store_true',
                        help='Enable verbose output for debugging')
    parser.add_argument('--deploy-wordpress', action='store_true',
                        help='Deploy WordPress with multisite capabilities')
    
    args = parser.parse_args()
    
    # Set logging level based on verbose flag
    if args.verbose:
        logger.setLevel(logging.DEBUG)
        logger.debug("Verbose logging enabled")
    
    if args.use_azure_sdk:
        if not SDK_AVAILABLE:
            logger.error("Azure SDK not available but --use-azure-sdk was specified.")
            logger.error("Install required packages with: pip install azure-identity azure-mgmt-resource")
            sys.exit(1)
        # Note: SDK method doesn't yet support WordPress deployment
        if args.deploy_wordpress:
            logger.warning("WordPress deployment not supported with Azure SDK method. Please use CLI method instead.")
        success = deploy_with_sdk(
            resource_group_name=args.resource_group,
            location=args.location,
            env_name=args.environment,
            project_name=args.project_name
        )
    else:
        success = deploy_with_cli(
            resource_group_name=args.resource_group,
            location=args.location,
            env_name=args.environment,
            project_name=args.project_name,
            verbose=args.verbose,
            deploy_wordpress=args.deploy_wordpress
        )
    
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()