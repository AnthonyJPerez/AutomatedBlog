import logging
import os
import json
import time
import requests
import azure.functions as func
from azure.keyvault.secrets import SecretClient
from azure.identity import DefaultAzureCredential
from azure.storage.blob import BlobServiceClient, BlobClient, ContainerClient

def main(bootstrapBlob: func.InputStream, outputBlob: func.Out[str]) -> None:
    """
    Blob trigger that suggests domain names based on blog theme.
    This function is triggered when bootstrap.json is created.
    It uses the GoDaddy API to generate domain suggestions.
    
    Parameters:
        bootstrapBlob: The bootstrap.json blob that triggered this function
        outputBlob: Output binding for the DomainNames.json file
    """
    # Set up logging
    logger = logging.getLogger('DomainNameSelector')
    logger.info(f'DomainNameSelector function triggered by blob: {bootstrapBlob.name}')
    
    # Check if topics.json and theme.json exist
    storage_connection_string = get_storage_connection_string()
    
    if not storage_connection_string:
        logger.error('Storage connection string not available')
        return
    
    try:
        # Check if DomainNames.json already exists (idempotency)
        blob_service_client = BlobServiceClient.from_connection_string(storage_connection_string)
        domain_names_blob_client = blob_service_client.get_blob_client(
            container="generated",
            blob="DomainNames.json"
        )
        
        if domain_names_blob_client.exists():
            logger.info('DomainNames.json already exists, skipping')
            return
        
        # Get topics.json
        topics_blob_client = blob_service_client.get_blob_client(
            container="",
            blob="topics.json"
        )
        
        # Get theme.json
        theme_blob_client = blob_service_client.get_blob_client(
            container="",
            blob="theme.json"
        )
        
        # Check if both files exist
        if not (topics_blob_client.exists() and theme_blob_client.exists()):
            logger.error('Required files topics.json or theme.json not found')
            return
        
        # Read topics.json
        topics_data = topics_blob_client.download_blob().readall().decode('utf-8')
        topics = json.loads(topics_data)
        
        # Read theme.json
        theme_data = theme_blob_client.download_blob().readall().decode('utf-8')
        theme = json.loads(theme_data)
        
        # Extract theme name and description
        theme_name = theme.get('name', '')
        theme_description = theme.get('description', '')
        
        # Generate domain suggestions
        domain_suggestions = generate_domain_suggestions(theme_name, theme_description, topics)
        
        # Write domain suggestions to output blob
        outputBlob.set(json.dumps(domain_suggestions, indent=2))
        logger.info('Domain suggestions successfully written to DomainNames.json')
        
    except Exception as e:
        logger.error(f'Error in DomainNameSelector: {str(e)}')

def generate_domain_suggestions(theme_name, theme_description, topics, max_price=50, tlds=None):
    """
    Generate domain suggestions using GoDaddy API.
    
    Parameters:
        theme_name: The name of the blog theme
        theme_description: The description of the blog theme
        topics: Array of focus topics
        max_price: Maximum price for domain suggestions in USD
        tlds: List of TLDs to check, defaults to ['.com', '.net', '.org', '.io', '.blog']
    
    Returns:
        list: List of domain suggestions with availability and pricing
    """
    logger = logging.getLogger('DomainNameSelector')
    
    if tlds is None:
        tlds = ['.com', '.net', '.org', '.io', '.blog']
    
    # Get GoDaddy API credentials
    godaddy_api_key = get_godaddy_api_key()
    godaddy_api_secret = get_godaddy_api_secret()
    
    if not (godaddy_api_key and godaddy_api_secret):
        logger.error('GoDaddy API credentials not available')
        # Fallback to generating suggestions without checking availability
        return generate_fallback_suggestions(theme_name, theme_description, topics, tlds)
    
    suggestions = []
    
    # Generate base keywords from theme and topics
    keywords = []
    
    if theme_name:
        keywords.append(theme_name.lower().replace(' ', ''))
        keywords.append(theme_name.lower().replace(' ', '-'))
    
    for topic in topics[:3]:  # Use up to 3 topics
        topic_keyword = topic.lower().replace(' ', '')
        keywords.append(topic_keyword)
        
        # Combine with theme
        if theme_name:
            combined = f"{theme_name.lower()}{topic_keyword}"
            keywords.append(combined)
            keywords.append(combined.replace(' ', '-'))
    
    # Add some common prefixes and suffixes
    prefixes = ['the', 'my', 'best', 'top']
    suffixes = ['hub', 'spot', 'central', 'blog', 'guru', 'pro']
    
    expanded_keywords = []
    for keyword in keywords:
        expanded_keywords.append(keyword)
        for prefix in prefixes:
            expanded_keywords.append(f"{prefix}{keyword}")
        for suffix in suffixes:
            expanded_keywords.append(f"{keyword}{suffix}")
    
    # Deduplicate
    keywords = list(set(expanded_keywords))
    
    # Check availability with GoDaddy API
    headers = {
        'Authorization': f'sso-key {godaddy_api_key}:{godaddy_api_secret}',
        'Content-Type': 'application/json'
    }
    
    for keyword in keywords[:20]:  # Limit to 20 keywords to avoid API rate limits
        for tld in tlds:
            domain = f"{keyword}{tld}"
            
            try:
                # Check domain availability
                url = f"https://api.godaddy.com/v1/domains/available?domain={domain}"
                response = requests.get(url, headers=headers)
                
                if response.status_code == 200:
                    data = response.json()
                    
                    if data.get('available', False):
                        price = data.get('price', 0) / 1000000  # Convert from microseconds to USD
                        
                        if price <= max_price:
                            suggestions.append({
                                'domain': domain,
                                'available': True,
                                'price': price
                            })
                
                # Respect API rate limits
                time.sleep(0.5)
                
            except Exception as e:
                logger.error(f'Error checking domain availability for {domain}: {str(e)}')
    
    # Sort by price
    suggestions.sort(key=lambda x: x.get('price', float('inf')))
    
    # If we don't have enough suggestions, add some fallbacks
    if len(suggestions) < 10:
        fallback_suggestions = generate_fallback_suggestions(theme_name, theme_description, topics, tlds)
        
        # Add fallbacks until we have 10 suggestions
        for suggestion in fallback_suggestions:
            if suggestion['domain'] not in [s['domain'] for s in suggestions]:
                suggestions.append(suggestion)
                if len(suggestions) >= 10:
                    break
    
    # Return top 10 or all if less than 10
    return suggestions[:10]

def generate_fallback_suggestions(theme_name, theme_description, topics, tlds):
    """
    Generate fallback domain suggestions without checking availability.
    
    Parameters:
        theme_name: The name of the blog theme
        theme_description: The description of the blog theme
        topics: Array of focus topics
        tlds: List of TLDs to check
    
    Returns:
        list: List of domain suggestions (without availability or pricing)
    """
    import random
    
    suggestions = []
    
    # Generate combinations of themes and topics
    keywords = []
    
    if theme_name:
        keywords.append(theme_name.lower().replace(' ', ''))
    
    for topic in topics[:5]:  # Use up to 5 topics
        topic_keyword = topic.lower().replace(' ', '')
        keywords.append(topic_keyword)
        
        # Combine with theme
        if theme_name:
            combined = f"{theme_name.lower()}{topic_keyword}"
            keywords.append(combined)
    
    # Add some common prefixes and suffixes
    prefixes = ['the', 'my', 'best', 'top', 'daily', 'smart', 'pro']
    suffixes = ['hub', 'spot', 'central', 'blog', 'guru', 'pro', 'zone', 'hq', 'insider']
    
    for keyword in keywords:
        # Add the keyword with different TLDs
        for tld in tlds[:3]:  # Limit to first 3 TLDs
            domain = f"{keyword}{tld}"
            suggestions.append({
                'domain': domain,
                'available': None,  # Unknown
                'price': random.uniform(10, 30),  # Random price between $10-30
                'is_fallback': True
            })
        
        # Add with prefixes
        for prefix in random.sample(prefixes, min(2, len(prefixes))):
            domain = f"{prefix}{keyword}{random.choice(tlds)}"
            suggestions.append({
                'domain': domain,
                'available': None,
                'price': random.uniform(10, 30),
                'is_fallback': True
            })
        
        # Add with suffixes
        for suffix in random.sample(suffixes, min(2, len(suffixes))):
            domain = f"{keyword}{suffix}{random.choice(tlds)}"
            suggestions.append({
                'domain': domain,
                'available': None,
                'price': random.uniform(10, 30),
                'is_fallback': True
            })
    
    # Shuffle and limit to 15 suggestions
    random.shuffle(suggestions)
    return suggestions[:15]

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

def get_godaddy_api_key():
    """Get GoDaddy API key from Key Vault or environment variable"""
    # Check if we have access to Key Vault
    key_vault_name = os.environ.get("KEY_VAULT_NAME")
    
    if key_vault_name:
        try:
            # Use managed identity to access Key Vault
            credential = DefaultAzureCredential()
            key_vault_uri = f"https://{key_vault_name}.vault.azure.net/"
            secret_client = SecretClient(vault_url=key_vault_uri, credential=credential)
            
            # Get GoDaddy API key from Key Vault
            api_key = secret_client.get_secret("GoDaddyApiKey").value
            return api_key
        except Exception as e:
            logging.error(f"Error retrieving GoDaddy API key from Key Vault: {str(e)}")
    
    # Fallback to environment variable
    return os.environ.get("GODADDY_API_KEY", "")

def get_godaddy_api_secret():
    """Get GoDaddy API secret from Key Vault or environment variable"""
    # Check if we have access to Key Vault
    key_vault_name = os.environ.get("KEY_VAULT_NAME")
    
    if key_vault_name:
        try:
            # Use managed identity to access Key Vault
            credential = DefaultAzureCredential()
            key_vault_uri = f"https://{key_vault_name}.vault.azure.net/"
            secret_client = SecretClient(vault_url=key_vault_uri, credential=credential)
            
            # Get GoDaddy API secret from Key Vault
            api_secret = secret_client.get_secret("GoDaddyApiSecret").value
            return api_secret
        except Exception as e:
            logging.error(f"Error retrieving GoDaddy API secret from Key Vault: {str(e)}")
    
    # Fallback to environment variable
    return os.environ.get("GODADDY_API_SECRET", "")