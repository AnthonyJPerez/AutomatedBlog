import logging
import os
import json
import time
import azure.functions as func
from azure.storage.blob import BlobServiceClient, BlobClient, ContainerClient

def main(bootstrapBlob: func.InputStream, outputBlob: func.Out[str]) -> None:
    """
    Blob trigger that generates integration stub files.
    This function is triggered when bootstrap.json is created.
    It generates stub files for various integrations and writes them to the integrations folder.
    
    Parameters:
        bootstrapBlob: The bootstrap.json blob that triggered this function
        outputBlob: Output binding for the bootstrap.done.json file
    """
    # Set up logging
    logger = logging.getLogger('IntegrationStubGenerator')
    logger.info(f'IntegrationStubGenerator function triggered by blob: {bootstrapBlob.name}')
    
    # Check if topics.json and theme.json exist
    storage_connection_string = get_storage_connection_string()
    
    if not storage_connection_string:
        logger.error('Storage connection string not available')
        return
    
    try:
        # Check if bootstrap.done.json already exists (idempotency)
        blob_service_client = BlobServiceClient.from_connection_string(storage_connection_string)
        bootstrap_done_blob_client = blob_service_client.get_blob_client(
            container="generated",
            blob="bootstrap.done.json"
        )
        
        # Create metrics for bootstrap processing
        metrics = {
            "timestamp": time.strftime('%Y-%m-%dT%H:%M:%SZ'),
            "errors": [],
            "stubs_created": []
        }
        
        # Create the integrations/ folder if it doesn't exist
        integrations_container_client = blob_service_client.get_container_client("")
        
        # List of integration stubs to create
        integrations = ['openai', 'surferseo', 'godaddy', 'adsense', 'analytics']
        
        # Generate stubs for each integration
        for integration in integrations:
            try:
                # Create or update the stub file
                stub_content = generate_stub_content(integration)
                
                # Check if stub already exists
                stub_blob_client = blob_service_client.get_blob_client(
                    container="",
                    blob=f"integrations/{integration}.json"
                )
                
                # Write the stub
                stub_blob_client.upload_blob(stub_content, overwrite=True)
                
                logger.info(f'Created integration stub for {integration}')
                metrics["stubs_created"].append(integration)
                
            except Exception as e:
                error_message = f'Error creating integration stub for {integration}: {str(e)}'
                logger.error(error_message)
                metrics["errors"].append(error_message)
        
        # Write bootstrap.done.json with metrics
        outputBlob.set(json.dumps(metrics, indent=2))
        logger.info('Integration stubs generated successfully')
        
    except Exception as e:
        logger.error(f'Error in IntegrationStubGenerator: {str(e)}')

def generate_stub_content(integration):
    """
    Generate stub content for a specific integration.
    
    Parameters:
        integration: The name of the integration
    
    Returns:
        str: JSON string with stub content
    """
    current_time = time.strftime('%Y-%m-%dT%H:%M:%SZ')
    
    if integration == 'openai':
        stub = {
            "description": "OpenAI API configuration for content generation",
            "setup_instructions": [
                "Create an OpenAI account at https://openai.com",
                "Go to https://platform.openai.com/api-keys to generate an API key",
                "Add the API key to your Azure Key Vault with the name 'OpenAIApiKey'",
                "Alternatively, set the OPENAI_API_KEY environment variable"
            ],
            "settings": {
                "model": "gpt-4o",
                "temperature": 0.7,
                "max_tokens": 4000,
                "frequency_penalty": 0.5,
                "presence_penalty": 0.0
            },
            "created_at": current_time,
            "is_configured": False
        }
        
    elif integration == 'surferseo':
        stub = {
            "description": "SurferSEO API configuration for content optimization",
            "setup_instructions": [
                "Create a SurferSEO account at https://surferseo.com",
                "Go to your account settings and generate an API key",
                "Add the API key to your Azure Key Vault with the name 'SurferSEOApiKey'",
                "Alternatively, set the SURFERSEO_API_KEY environment variable"
            ],
            "settings": {
                "project_id": "",
                "optimize_for_keyword": True,
                "competitor_analysis": True,
                "content_score_threshold": 80
            },
            "created_at": current_time,
            "is_configured": False
        }
        
    elif integration == 'godaddy':
        stub = {
            "description": "GoDaddy API configuration for domain name suggestions",
            "setup_instructions": [
                "Create or log into your GoDaddy account",
                "Go to https://developer.godaddy.com and create a production API key",
                "Add the API key to your Azure Key Vault with the name 'GoDaddyApiKey'",
                "Add the API secret to your Azure Key Vault with the name 'GoDaddyApiSecret'",
                "Alternatively, set the GODADDY_API_KEY and GODADDY_API_SECRET environment variables"
            ],
            "settings": {
                "max_domain_price": 50,
                "preferred_tlds": [".com", ".net", ".org", ".io", ".blog"]
            },
            "created_at": current_time,
            "is_configured": False
        }
        
    elif integration == 'adsense':
        stub = {
            "description": "Google AdSense configuration for blog monetization",
            "setup_instructions": [
                "Create an AdSense account at https://www.google.com/adsense",
                "Get your publisher ID (format: pub-XXXXXXXXXXXXXXXX)",
                "Create ad units for your blog",
                "Add the following ad snippets to your Azure Key Vault with the name 'AdSenseSnippet'"
            ],
            "settings": {
                "publisher_id": "pub-XXXXXXXXXXXXXXXX",
                "ad_types": ["in-article", "in-feed", "sidebar"],
                "auto_ads_enabled": True
            },
            "created_at": current_time,
            "is_configured": False
        }
        
    elif integration == 'analytics':
        stub = {
            "description": "Google Analytics configuration for blog traffic tracking",
            "setup_instructions": [
                "Create a Google Analytics 4 property at https://analytics.google.com",
                "Get your Measurement ID (format: G-XXXXXXXXXX)",
                "Add the Measurement ID to your Azure Key Vault with the name 'GA4MeasurementId'",
                "Alternatively, set the GA4_MEASUREMENT_ID environment variable"
            ],
            "settings": {
                "measurement_id": "G-XXXXXXXXXX",
                "user_property_tracking": True,
                "enhanced_event_tracking": True
            },
            "created_at": current_time,
            "is_configured": False
        }
        
    else:
        stub = {
            "description": f"Configuration for {integration}",
            "setup_instructions": [
                "This is a stub file for the integration",
                "Replace this with actual configuration"
            ],
            "settings": {},
            "created_at": current_time,
            "is_configured": False
        }
    
    return json.dumps(stub, indent=2)

def get_storage_connection_string():
    """Get Azure Storage connection string"""
    # First try to get from environment variable
    connection_string = os.environ.get("AzureWebJobsStorage")
    
    if connection_string:
        return connection_string
    
    # If not in environment, try to construct from account name and key
    account_name = os.environ.get("STORAGE_ACCOUNT_NAME")
    account_key = os.environ.get("STORAGE_ACCOUNT_KEY")
    
    if account_name and account_key:
        return f"DefaultEndpointsProtocol=https;AccountName={account_name};AccountKey={account_key};EndpointSuffix=core.windows.net"
    
    return None