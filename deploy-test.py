#!/usr/bin/env python3
"""
Simple script to test deployment parameters.
Run with: python deploy-test.py --resource-group <resource-group-name>
"""

import argparse
import json

def main():
    parser = argparse.ArgumentParser(description="Test deployment parameters")
    parser.add_argument("--resource-group", "-g", type=str, required=True, help="Resource group name")
    parser.add_argument("--project-name", "-p", type=str, default="blogauto", help="Project name")
    parser.add_argument("--environment", "-e", type=str, default="dev", help="Environment (dev, staging, prod)")
    
    args = parser.parse_args()
    
    # Create ARM deployment parameters
    params = {
        "projectName": {"value": args.project_name},
        "environment": {"value": args.environment},
        "location": {"value": "eastus"}
    }
    
    print("Resource Group:", args.resource_group)
    print("Deployment Parameters:", json.dumps(params, indent=2))
    
    # Show the command that would be used in GitHub Actions
    print("\nGitHub Actions Command:")
    print(f"azure/arm-deploy@v1 with:")
    print(f"  resourceGroupName: {args.resource_group}")
    print(f"  template: ./infra/main.bicep")
    print(f"  parameters: projectName={args.project_name} environment={args.environment} location=eastus")

if __name__ == "__main__":
    main()