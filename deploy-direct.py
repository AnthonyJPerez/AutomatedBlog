#!/usr/bin/env python3
"""
Direct deployment script for Azure resources.
Similar to deploy.py but with explicit resource group handling.
"""

import os
import argparse
import logging
import subprocess
from pathlib import Path

# Set up logging
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('deployment')

def run_deployment(resource_group_name, location="eastus", env_name="dev", project_name="blogauto"):
    """
    Deploy Azure resources using az CLI and Bicep templates.
    
    Parameters:
        resource_group_name: Name of the resource group (REQUIRED)
        location: Azure region (default: eastus)
        env_name: Environment name for naming resources (default: dev)
        project_name: Project name for resource naming (default: blogauto)
    
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
    
    args = parser.parse_args()
    
    success = run_deployment(
        resource_group_name=args.resource_group,
        location=args.location,
        env_name=args.environment,
        project_name=args.project_name
    )
    
    exit(0 if success else 1)

if __name__ == "__main__":
    main()