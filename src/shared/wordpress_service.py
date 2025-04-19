import os
import json
import logging
import time
import requests
from azure.identity import DefaultAzureCredential
from azure.keyvault.secrets import SecretClient

class WordPressService:
    """
    Service for publishing content to WordPress sites.
    Handles authentication, content formatting, and AdSense integration.
    """
    
    def __init__(self):
        self.logger = logging.getLogger('wordpress_service')
        self.default_wordpress_url = None
        self.default_wordpress_username = None
        self.default_wordpress_password = None
        
        # Multisite configuration
        self.is_multisite = False
        self.multisite_config = None
        self.network_id = None
        
        # Get Key Vault name from environment variable
        key_vault_name = os.environ.get("KEY_VAULT_NAME")
        
        if key_vault_name:
            # Use managed identity to access Key Vault
            try:
                credential = DefaultAzureCredential()
                key_vault_uri = f"https://{key_vault_name}.vault.azure.net/"
                self.secret_client = SecretClient(vault_url=key_vault_uri, credential=credential)
                
                # Get WordPress secrets from Key Vault
                try:
                    # Try to get default WordPress credentials
                    self.default_wordpress_url = self._get_secret('WordPressUrl')
                    self.default_wordpress_username = self._get_secret('WordPressAdminUsername')
                    self.default_wordpress_password = self._get_secret('WordPressAppPassword')
                    
                    # Check for Multisite information
                    is_multisite_str = self._get_secret('WordPressIsMultisite')
                    if is_multisite_str and is_multisite_str.lower() == 'true':
                        self.is_multisite = True
                        
                        # Get network ID
                        self.network_id = self._get_secret('WordPressNetworkId')
                        
                        # Get detailed multisite configuration
                        multisite_config_json = self._get_secret('WordPressMultisiteConfig')
                        if multisite_config_json:
                            try:
                                self.multisite_config = json.loads(multisite_config_json)
                                self.logger.info("Successfully loaded WordPress Multisite configuration")
                            except Exception as e:
                                self.logger.warning(f"Error parsing Multisite configuration: {str(e)}")
                    
                    if self.default_wordpress_url and self.default_wordpress_username and self.default_wordpress_password:
                        self.logger.info(f"Successfully loaded WordPress credentials from Key Vault for {self.default_wordpress_url}")
                        if self.is_multisite:
                            self.logger.info("WordPress Multisite is enabled")
                    else:
                        self.logger.warning("Some WordPress credentials were not found in Key Vault")
                        
                except Exception as e:
                    self.logger.warning(f"WordPress credentials not found in Key Vault: {str(e)}")
            except Exception as e:
                self.logger.error(f"Error initializing Key Vault client: {str(e)}")
                self.secret_client = None
        else:
            self.logger.warning("No KEY_VAULT_NAME environment variable, WordPress credentials must be provided manually")
            self.secret_client = None
    
    def _get_secret(self, secret_name):
        """Retrieve a secret from Key Vault"""
        if not self.secret_client:
            return None
            
        try:
            secret = self.secret_client.get_secret(secret_name)
            return secret.value
        except Exception as e:
            self.logger.debug(f"Secret {secret_name} not found in Key Vault: {str(e)}")
            return None
    
    def publish_post(self, wordpress_url, username, application_password, title, content, seo_metadata):
        """
        Publish a post to a WordPress site using the REST API.
        
        Args:
            wordpress_url (str): The URL of the WordPress site
            username (str): WordPress username
            application_password (str): WordPress application password
            title (str): The title of the post
            content (str): The HTML content of the post
            seo_metadata (dict): SEO metadata for the post
            
        Returns:
            dict: Details of the published post including post ID and URL
        """
        self.logger.info(f"Publishing post '{title}' to WordPress site: {wordpress_url}")
        
        # Ensure WordPress URL has the correct format
        if not wordpress_url.endswith('/'):
            wordpress_url += '/'
        
        if not wordpress_url.endswith('wp-json/'):
            wordpress_url += 'wp-json/'
        
        # Create the endpoint URL
        endpoint = f"{wordpress_url}wp/v2/posts"
        
        # Prepare post data
        post_data = {
            'title': title,
            'content': content,
            'status': 'publish',
            'slug': seo_metadata.get('slug', ''),
            'excerpt': seo_metadata.get('meta_description', ''),
            'categories': [1],  # Default category (usually "Uncategorized")
            'meta': {
                '_yoast_wpseo_metadesc': seo_metadata.get('meta_description', ''),
                '_yoast_wpseo_focuskw': seo_metadata.get('keywords', [''])[0] if seo_metadata.get('keywords') else '',
                '_yoast_wpseo_opengraph-title': seo_metadata.get('social_title', title),
                '_yoast_wpseo_opengraph-description': seo_metadata.get('social_description', seo_metadata.get('meta_description', ''))
            }
        }
        
        # Create tags from keywords if available
        if seo_metadata.get('keywords'):
            # Get existing tags first
            tags_endpoint = f"{wordpress_url}wp/v2/tags"
            existing_tags = self._make_request('GET', tags_endpoint, auth=(username, application_password))
            
            # Map existing tag names to IDs
            tag_map = {tag['name'].lower(): tag['id'] for tag in existing_tags} if existing_tags else {}
            
            # Process keywords into tags
            tag_ids = []
            for keyword in seo_metadata['keywords'][:5]:  # Limit to 5 tags
                keyword_lower = keyword.lower()
                if keyword_lower in tag_map:
                    # Use existing tag
                    tag_ids.append(tag_map[keyword_lower])
                else:
                    # Create new tag
                    tag_data = {'name': keyword}
                    new_tag = self._make_request('POST', tags_endpoint, auth=(username, application_password), json=tag_data)
                    if new_tag and 'id' in new_tag:
                        tag_ids.append(new_tag['id'])
            
            # Add tags to post data
            if tag_ids:
                post_data['tags'] = tag_ids
        
        # Make the request to create the post
        max_retries = 3
        for attempt in range(max_retries):
            try:
                response = self._make_request('POST', endpoint, auth=(username, application_password), json=post_data)
                
                if response and 'id' in response:
                    post_id = response['id']
                    post_url = response['link']
                    
                    self.logger.info(f"Successfully published post with ID {post_id} at {post_url}")
                    
                    return {
                        'post_id': post_id,
                        'post_url': post_url,
                        'status': 'published'
                    }
                else:
                    raise Exception(f"Failed to publish post: {response}")
                    
            except Exception as e:
                self.logger.error(f"Error publishing post (attempt {attempt+1}/{max_retries}): {str(e)}")
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)  # Exponential backoff
                else:
                    raise Exception(f"Failed to publish post after {max_retries} attempts: {str(e)}")
    
    def insert_adsense_ads(self, content, publisher_id, ad_slots):
        """
        Insert AdSense ad code into the content at appropriate positions.
        
        Args:
            content (str): The HTML content of the post
            publisher_id (str): The AdSense publisher ID
            ad_slots (list): List of ad slot IDs and their positions
            
        Returns:
            str: The content with AdSense ads inserted
        """
        self.logger.info(f"Inserting {len(ad_slots)} AdSense ads into content")
        
        if not ad_slots:
            return content
        
        # Split content by paragraphs
        paragraphs = content.split("</p>")
        
        # Calculate positions for ad insertion
        positions = []
        
        if len(paragraphs) <= 3:
            # If content is very short, only place ad at the end
            positions = [len(paragraphs) - 1]
        else:
            # Place ads after introduction (position 1) and then evenly throughout the content
            positions = [1]  # After first paragraph
            
            # Calculate spacing for remaining ads
            remaining_paragraphs = len(paragraphs) - 2  # Exclude first and last paragraph
            remaining_ads = min(len(ad_slots) - 1, 3)  # Limit to 3 additional ads
            
            if remaining_ads > 0 and remaining_paragraphs > 0:
                spacing = remaining_paragraphs // (remaining_ads + 1)
                for i in range(1, remaining_ads + 1):
                    position = 1 + (i * spacing)
                    if position < len(paragraphs) - 1:  # Avoid last paragraph
                        positions.append(position)
            
            # Always add one ad at the end if we have slots available
            if len(positions) < len(ad_slots):
                positions.append(len(paragraphs) - 1)
        
        # Limit positions to available ad slots
        positions = positions[:len(ad_slots)]
        
        # Insert ads at the calculated positions
        modified_paragraphs = list(paragraphs)  # Create a copy to modify
        
        for i, position in enumerate(positions):
            if i < len(ad_slots):
                ad_slot = ad_slots[i]
                ad_code = self._generate_adsense_code(publisher_id, ad_slot)
                modified_paragraphs[position] = f"{modified_paragraphs[position]}</p>{ad_code}"
        
        # Reassemble content
        modified_content = "</p>".join(modified_paragraphs)
        
        return modified_content
    
    def _generate_adsense_code(self, publisher_id, ad_slot):
        """Generate AdSense ad code for a specific slot"""
        ad_code = f"""
        <div class="adsense-container">
            <ins class="adsbygoogle"
                 style="display:block"
                 data-ad-client="ca-pub-{publisher_id}"
                 data-ad-slot="{ad_slot}"
                 data-ad-format="auto"
                 data-full-width-responsive="true"></ins>
            <script>
                (adsbygoogle = window.adsbygoogle || []).push({{}});
            </script>
        </div>
        """
        return ad_code
    
    def publish_to_default_wordpress(self, title, content, seo_metadata=None, site_id=None):
        """
        Publish a post to the default WordPress site using credentials from Key Vault.
        In multisite mode, optionally specify a site_id to publish to a specific site.
        
        Args:
            title (str): The title of the post
            content (str): The HTML content of the post
            seo_metadata (dict, optional): SEO metadata for the post
            site_id (int, optional): The site ID to publish to in a multisite network
            
        Returns:
            dict: Details of the published post including post ID and URL
        
        Raises:
            Exception: If default WordPress credentials are not available or publishing fails
        """
        # Check if default WordPress credentials are available
        if not self.default_wordpress_url or not self.default_wordpress_username or not self.default_wordpress_password:
            error_msg = "Default WordPress credentials not available. Make sure KEY_VAULT_NAME is set and contains WordPress secrets."
            self.logger.error(error_msg)
            raise Exception(error_msg)
        
        # Set default SEO metadata if not provided
        if not seo_metadata:
            seo_metadata = {
                'slug': '',
                'meta_description': '',
                'keywords': []
            }
        
        # Handle multisite publication
        if self.is_multisite and site_id:
            self.logger.info(f"Publishing to WordPress Multisite, site ID: {site_id}")
            return self.publish_to_multisite(
                wordpress_url=self.default_wordpress_url,
                username=self.default_wordpress_username,
                application_password=self.default_wordpress_password,
                title=title,
                content=content,
                site_id=site_id,
                seo_metadata=seo_metadata
            )
        
        # Default single site publication
        self.logger.info("Publishing to default WordPress site")
        return self.publish_post(
            wordpress_url=self.default_wordpress_url,
            username=self.default_wordpress_username,
            application_password=self.default_wordpress_password,
            title=title,
            content=content,
            seo_metadata=seo_metadata
        )
    
    def _make_request(self, method, url, **kwargs):
        """Make HTTP request with error handling and logging"""
        try:
            response = requests.request(method, url, **kwargs)
            response.raise_for_status()
            
            if response.status_code == 204:  # No content
                return {}
                
            return response.json()
            
        except requests.exceptions.HTTPError as e:
            error_msg = f"HTTP error: {e}"
            if hasattr(e, 'response') and e.response is not None:
                try:
                    error_detail = e.response.json()
                    error_msg += f" - {json.dumps(error_detail)}"
                except:
                    error_msg += f" - Status code: {e.response.status_code}"
            
            self.logger.error(error_msg)
            raise Exception(error_msg)
            
        except requests.exceptions.ConnectionError:
            error_msg = f"Connection error when calling {url}"
            self.logger.error(error_msg)
            raise Exception(error_msg)
            
        except requests.exceptions.Timeout:
            error_msg = f"Timeout when calling {url}"
            self.logger.error(error_msg)
            raise Exception(error_msg)
            
        except requests.exceptions.RequestException as e:
            error_msg = f"Request error: {e}"
            self.logger.error(error_msg)
            raise Exception(error_msg)
            
        except ValueError as e:
            error_msg = f"JSON decode error: {e}"
            self.logger.error(error_msg)
            raise Exception(error_msg)
