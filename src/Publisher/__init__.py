import logging
import json
import os
import time
import base64
import hmac
import hashlib
import requests
import azure.functions as func
from azure.keyvault.secrets import SecretClient
from azure.identity import DefaultAzureCredential

def main(inputBlob: func.InputStream, outputBlob: func.Out[str]) -> None:
    """
    Blob trigger that publishes generated blog content to WordPress.
    This function is triggered when new blog content is created.
    It publishes the content to the associated WordPress site and tracks results.
    
    Parameters:
        inputBlob: The input blob that triggered this function (blog content)
        outputBlob: Output binding for the publish result
    """
    # Set up logging
    logger = logging.getLogger('Publisher')
    logger.info(f'Publisher function triggered by blob: {inputBlob.name}')
    
    # Extract runId from the blob name
    try:
        # Path format: generated/{runId}/content.md
        path_parts = inputBlob.name.split('/')
        run_id = path_parts[1]
        logger.info(f'Processing run ID: {run_id}')
    except Exception as e:
        logger.error(f'Error extracting run ID from blob name: {str(e)}')
        return
    
    # Check if publish.json already exists (idempotency)
    publish_path = f'generated/{run_id}/publish.json'
    
    # Read content.md
    try:
        content_md = inputBlob.read().decode('utf-8')
    except Exception as e:
        logger.error(f'Error reading content.md: {str(e)}')
        outputBlob.set(json.dumps({
            "runId": run_id,
            "status": "error",
            "error": f"Failed to read content: {str(e)}"
        }))
        return
    
    # Extract metadata from the markdown frontmatter
    metadata = {}
    content = content_md
    
    if content_md.startswith('---'):
        try:
            # Split the frontmatter from the content
            parts = content_md.split('---', 2)
            if len(parts) >= 3:
                frontmatter = parts[1].strip()
                content = parts[2].strip()
                
                # Parse frontmatter
                for line in frontmatter.split('\n'):
                    if ':' in line:
                        key, value = line.split(':', 1)
                        key = key.strip()
                        value = value.strip().strip('"\'')
                        metadata[key] = value
        except Exception as e:
            logger.warning(f'Error parsing frontmatter: {str(e)}')
    
    # Get AdSense snippet from Key Vault
    adsense_snippet = get_adsense_snippet()
    
    # Append AdSense snippet to the content if available
    if adsense_snippet:
        content = f"{content}\n\n{adsense_snippet}"
    
    # Get WordPress credentials
    wordpress_url = os.environ.get("WORDPRESS_URL", "https://example.com")
    wordpress_username = os.environ.get("WORDPRESS_USERNAME", "admin")
    wordpress_password = get_wordpress_app_password()
    
    if not wordpress_password:
        logger.error("WordPress application password not found")
        outputBlob.set(json.dumps({
            "runId": run_id,
            "status": "error",
            "error": "WordPress application password not found"
        }))
        return
    
    # Prepare the post data
    post_data = {
        "title": metadata.get("title", f"Blog Post {run_id}"),
        "content": content,
        "status": "publish",
        "slug": metadata.get("slug", ""),
        "excerpt": metadata.get("description", ""),
        "categories": [1],  # Default category ID, should be configurable
        "tags": []  # Tags from keywords
    }
    
    # Add tags from keywords if available
    if "keywords" in metadata:
        keywords = [kw.strip() for kw in metadata["keywords"].split(',')]
        for keyword in keywords:
            if keyword:
                post_data["tags"].append({"name": keyword})
    
    # Publish to WordPress with retries
    max_retries = 3
    post_id = None
    post_url = None
    success = False
    error_message = None
    
    for attempt in range(max_retries):
        try:
            # Prepare the request
            headers = {
                "Content-Type": "application/json"
            }
            
            # WordPress REST API endpoint
            api_url = f"{wordpress_url}/wp-json/wp/v2/posts"
            
            # Make the request with basic auth
            response = requests.post(
                api_url,
                json=post_data,
                headers=headers,
                auth=(wordpress_username, wordpress_password),
                timeout=30
            )
            
            # Check response
            if response.status_code in [201, 200]:
                # Success
                post_data = response.json()
                post_id = post_data.get("id")
                post_url = post_data.get("link")
                success = True
                logger.info(f"Successfully published post ID: {post_id}")
                break
            elif response.status_code == 409:
                # Conflict - post already exists
                logger.warning("Post already exists, skipping")
                success = True
                error_message = "Post already exists"
                break
            elif response.status_code >= 500:
                # Server error, retry
                logger.warning(f"Server error: {response.status_code}, retrying... (attempt {attempt+1}/{max_retries})")
                time.sleep(2 ** attempt)  # Exponential backoff
            else:
                # Client error, don't retry
                logger.error(f"Client error: {response.status_code}, {response.text}")
                error_message = f"Client error: {response.status_code}, {response.text}"
                break
                
        except Exception as e:
            logger.error(f"Error publishing post (attempt {attempt+1}/{max_retries}): {str(e)}")
            error_message = str(e)
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)  # Exponential backoff
    
    # Prepare publish result
    publish_result = {
        "runId": run_id,
        "title": metadata.get("title", f"Blog Post {run_id}"),
        "status": "success" if success else "error",
        "post_id": post_id,
        "post_url": post_url,
        "published_at": time.strftime('%Y-%m-%dT%H:%M:%SZ'),
        "error_message": error_message
    }
    
    # Write publish result
    outputBlob.set(json.dumps(publish_result, indent=2))
    logger.info(f"Publish result for run ID: {run_id} written")

def get_adsense_snippet():
    """Get AdSense snippet from Key Vault or environment variable"""
    # Check if we have access to Key Vault
    key_vault_name = os.environ.get("KEY_VAULT_NAME")
    
    if key_vault_name:
        try:
            # Use managed identity to access Key Vault
            credential = DefaultAzureCredential()
            key_vault_uri = f"https://{key_vault_name}.vault.azure.net/"
            secret_client = SecretClient(vault_url=key_vault_uri, credential=credential)
            
            # Get AdSense snippet from Key Vault
            adsense_snippet = secret_client.get_secret("AdSenseSnippet").value
            return adsense_snippet
        except Exception as e:
            logging.error(f"Error retrieving AdSense snippet from Key Vault: {str(e)}")
    
    # Fallback to environment variable
    return os.environ.get("ADSENSE_SNIPPET", "")

def get_wordpress_app_password():
    """Get WordPress application password from Key Vault or environment variable"""
    # Check if we have access to Key Vault
    key_vault_name = os.environ.get("KEY_VAULT_NAME")
    
    if key_vault_name:
        try:
            # Use managed identity to access Key Vault
            credential = DefaultAzureCredential()
            key_vault_uri = f"https://{key_vault_name}.vault.azure.net/"
            secret_client = SecretClient(vault_url=key_vault_uri, credential=credential)
            
            # Get WordPress app password from Key Vault
            wordpress_password = secret_client.get_secret("WordPressAppPassword").value
            return wordpress_password
        except Exception as e:
            logging.error(f"Error retrieving WordPress app password from Key Vault: {str(e)}")
    
    # Fallback to environment variable
    return os.environ.get("WORDPRESS_APP_PASSWORD", "")