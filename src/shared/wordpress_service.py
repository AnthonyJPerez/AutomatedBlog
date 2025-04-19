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
        
        # Cache for API responses to reduce external calls and improve performance
        self._cache = {
            'sites': {'data': None, 'expires': 0},
            'domains': {},  # Will hold domain data by site_id
            'tags': {}      # Will hold tag data by site_id
        }
        self._cache_ttl = 300  # 5 minutes cache TTL
        self._cache_last_purge = time.time()
        self._cache_purge_interval = 3600  # Purge expired cache entries every hour
        
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
            
    def _get_cached_data(self, cache_key, subkey=None):
        """Get data from cache if it exists and hasn't expired"""
        now = time.time()
        
        # Periodically purge expired cache entries to prevent memory growth
        if now - self._cache_last_purge > self._cache_purge_interval:
            self._purge_expired_cache()
            self._cache_last_purge = now
        
        if subkey is not None:
            if cache_key in self._cache and subkey in self._cache[cache_key]:
                cache_entry = self._cache[cache_key][subkey]
                if cache_entry.get('expires', 0) > now:
                    self.logger.debug(f"Cache hit for {cache_key}/{subkey}")
                    return cache_entry['data']
        else:
            if cache_key in self._cache and self._cache[cache_key].get('expires', 0) > now:
                self.logger.debug(f"Cache hit for {cache_key}")
                return self._cache[cache_key]['data']
                
        self.logger.debug(f"Cache miss for {cache_key}{f'/{subkey}' if subkey else ''}")
        return None
        
    def _purge_expired_cache(self):
        """Purge expired entries from the cache to prevent memory leaks"""
        now = time.time()
        purged_count = 0
        
        self.logger.debug("Starting cache purge")
        
        # Clean top-level entries
        for key in list(self._cache.keys()):
            if isinstance(self._cache[key], dict) and 'expires' in self._cache[key] and self._cache[key]['expires'] < now:
                del self._cache[key]
                purged_count += 1
                
        # Clean nested entries
        for key, value in self._cache.items():
            if isinstance(value, dict) and 'expires' not in value:  # This is a container of cached items
                for subkey in list(value.keys()):
                    if 'expires' in value[subkey] and value[subkey]['expires'] < now:
                        del value[subkey]
                        purged_count += 1
        
        if purged_count > 0:
            self.logger.info(f"Purged {purged_count} expired cache entries")
        else:
            self.logger.debug("No expired cache entries to purge")
            
    def clear_cache(self, cache_key=None, subkey=None):
        """
        Manually clear the cache, either entirely or specific sections.
        
        Args:
            cache_key (str, optional): Specific cache section to clear (e.g., 'sites', 'domains', 'tags')
            subkey (str, optional): Specific subkey within a cache section to clear
            
        Returns:
            int: Number of cache entries cleared
        """
        cleared_count = 0
        
        if cache_key is None:
            # Clear entire cache
            for key in list(self._cache.keys()):
                if isinstance(self._cache[key], dict) and 'expires' not in self._cache[key]:
                    # This is a container of cached items, count its entries
                    cleared_count += len(self._cache[key])
                else:
                    cleared_count += 1
            
            self._cache = {
                'sites': {'data': None, 'expires': 0},
                'domains': {},
                'tags': {}
            }
            self.logger.info(f"Cleared entire cache ({cleared_count} entries)")
            
        elif subkey is None and cache_key in self._cache:
            # Clear specific cache section
            if isinstance(self._cache[cache_key], dict) and 'expires' not in self._cache[cache_key]:
                # This is a container of cached items, count its entries
                cleared_count = len(self._cache[cache_key])
                self._cache[cache_key] = {}
            else:
                # This is a single cache entry
                cleared_count = 1
                self._cache[cache_key] = {'data': None, 'expires': 0}
                
            self.logger.info(f"Cleared cache section '{cache_key}' ({cleared_count} entries)")
            
        elif cache_key in self._cache and isinstance(self._cache[cache_key], dict) and 'expires' not in self._cache[cache_key] and subkey in self._cache[cache_key]:
            # Clear specific subkey within a cache section
            del self._cache[cache_key][subkey]
            cleared_count = 1
            self.logger.info(f"Cleared cache entry '{cache_key}/{subkey}'")
            
        return cleared_count
        
    def _set_cached_data(self, cache_key, data, subkey=None, ttl=None):
        """Store data in cache with expiration time"""
        if ttl is None:
            ttl = self._cache_ttl
            
        expires = time.time() + ttl
        
        if subkey is not None:
            if cache_key not in self._cache:
                self._cache[cache_key] = {}
            self._cache[cache_key][subkey] = {'data': data, 'expires': expires}
        else:
            self._cache[cache_key] = {'data': data, 'expires': expires}
            
        self.logger.debug(f"Cached data for {cache_key}{f'/{subkey}' if subkey else ''} expires in {ttl}s")
        return data
    
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
        
        # Security: Sanitize inputs to prevent WordPress injection attacks
        if post_data['title']:
            post_data['title'] = self._sanitize_content(post_data['title'])
        if post_data['excerpt']:
            post_data['excerpt'] = self._sanitize_content(post_data['excerpt'])
        if post_data['meta']['_yoast_wpseo_metadesc']:
            post_data['meta']['_yoast_wpseo_metadesc'] = self._sanitize_content(post_data['meta']['_yoast_wpseo_metadesc'])
        if post_data['meta']['_yoast_wpseo_opengraph-title']:
            post_data['meta']['_yoast_wpseo_opengraph-title'] = self._sanitize_content(post_data['meta']['_yoast_wpseo_opengraph-title'])
        if post_data['meta']['_yoast_wpseo_opengraph-description']:
            post_data['meta']['_yoast_wpseo_opengraph-description'] = self._sanitize_content(post_data['meta']['_yoast_wpseo_opengraph-description'])
        
        # Create tags from keywords if available
        if seo_metadata.get('keywords'):
            # Try to get tags from cache
            cache_key = f"{wordpress_url}:tags"
            cached_tags = self._get_cached_data('tags', cache_key)
            
            if cached_tags is None:
                # Get existing tags if not in cache
                tags_endpoint = f"{wordpress_url}wp/v2/tags"
                self.logger.debug(f"Fetching tags from WordPress API: {tags_endpoint}")
                existing_tags = self._make_request('GET', tags_endpoint, auth=(username, application_password))
                
                # Cache the tags
                if existing_tags:
                    cached_tags = existing_tags
                    self._set_cached_data('tags', existing_tags, cache_key)
            else:
                self.logger.debug(f"Using cached tags for {wordpress_url}")
                existing_tags = cached_tags
            
            # Map existing tag names to IDs
            tag_map = {tag['name'].lower(): tag['id'] for tag in existing_tags} if existing_tags else {}
            
            # Process keywords into tags
            tag_ids = []
            new_tags_created = False
            
            for keyword in seo_metadata['keywords'][:5]:  # Limit to 5 tags
                keyword_lower = keyword.lower()
                if keyword_lower in tag_map:
                    # Use existing tag
                    tag_ids.append(tag_map[keyword_lower])
                else:
                    # Create new tag
                    tag_data = {'name': keyword}
                    self.logger.debug(f"Creating new tag: {keyword}")
                    new_tag = self._make_request('POST', tags_endpoint, auth=(username, application_password), json=tag_data)
                    if new_tag and 'id' in new_tag:
                        tag_ids.append(new_tag['id'])
                        # Add to cache to avoid future creations
                        if cached_tags is not None:
                            cached_tags.append(new_tag)
                            new_tags_created = True
            
            # Update cache if new tags were created
            if new_tags_created and cached_tags is not None:
                self._set_cached_data('tags', cached_tags, cache_key)
            
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
    
    def publish_to_multisite(self, wordpress_url, username, application_password, title, content, site_id, seo_metadata=None):
        """
        Publish a post to a specific site in a WordPress Multisite network.
        
        Args:
            wordpress_url (str): The URL of the WordPress site
            username (str): WordPress username
            application_password (str): WordPress application password
            title (str): The title of the post
            content (str): The HTML content of the post
            site_id (int): The site ID in the multisite network
            seo_metadata (dict, optional): SEO metadata for the post
            
        Returns:
            dict: Details of the published post including post ID and URL
        """
        self.logger.info(f"Publishing post '{title}' to WordPress Multisite, site ID: {site_id}")
        
        if not self.is_multisite:
            self.logger.warning("WordPress is not configured as Multisite, using standard publish method")
            return self.publish_post(wordpress_url, username, application_password, title, content, seo_metadata or {})
        
        # Ensure WordPress URL has the correct format
        if not wordpress_url.endswith('/'):
            wordpress_url += '/'
            
        if not wordpress_url.endswith('wp-json/'):
            wordpress_url += 'wp-json/'
            
        # Create the endpoint URL for multisite API
        # Note: Mercator plugin extends the WordPress REST API with the sites endpoint
        endpoint = f"{wordpress_url}wp/v2/sites/{site_id}/posts"
        
        # Prepare post data (same as in publish_post)
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
        
        # Security: Sanitize inputs for multisite as well
        if post_data['title']:
            post_data['title'] = self._sanitize_content(post_data['title'])
        if post_data['excerpt']:
            post_data['excerpt'] = self._sanitize_content(post_data['excerpt'])
        if post_data['meta']['_yoast_wpseo_metadesc']:
            post_data['meta']['_yoast_wpseo_metadesc'] = self._sanitize_content(post_data['meta']['_yoast_wpseo_metadesc'])
        if post_data['meta']['_yoast_wpseo_opengraph-title']:
            post_data['meta']['_yoast_wpseo_opengraph-title'] = self._sanitize_content(post_data['meta']['_yoast_wpseo_opengraph-title'])
        if post_data['meta']['_yoast_wpseo_opengraph-description']:
            post_data['meta']['_yoast_wpseo_opengraph-description'] = self._sanitize_content(post_data['meta']['_yoast_wpseo_opengraph-description'])
        
        # Handle tags same as in publish_post
        if seo_metadata and seo_metadata.get('keywords'):
            # Try to get tags from cache
            cache_key = f"{wordpress_url}:site:{site_id}:tags"
            cached_tags = self._get_cached_data('tags', cache_key)
            
            if cached_tags is None:
                # Get existing tags if not in cache for this specific site
                tags_endpoint = f"{wordpress_url}wp/v2/sites/{site_id}/tags"
                self.logger.debug(f"Fetching tags from WordPress API for site {site_id}: {tags_endpoint}")
                existing_tags = self._make_request('GET', tags_endpoint, auth=(username, application_password))
                
                # Cache the tags
                if existing_tags:
                    cached_tags = existing_tags
                    self._set_cached_data('tags', existing_tags, cache_key)
            else:
                self.logger.debug(f"Using cached tags for {wordpress_url} site {site_id}")
                existing_tags = cached_tags
            
            # Map existing tag names to IDs
            tag_map = {tag['name'].lower(): tag['id'] for tag in existing_tags} if existing_tags else {}
            
            # Process keywords into tags
            tag_ids = []
            new_tags_created = False
            
            for keyword in seo_metadata['keywords'][:5]:  # Limit to 5 tags
                keyword_lower = keyword.lower()
                if keyword_lower in tag_map:
                    # Use existing tag
                    tag_ids.append(tag_map[keyword_lower])
                else:
                    # Create new tag
                    tag_data = {'name': keyword}
                    self.logger.debug(f"Creating new tag for site {site_id}: {keyword}")
                    new_tag = self._make_request('POST', tags_endpoint, auth=(username, application_password), json=tag_data)
                    if new_tag and 'id' in new_tag:
                        tag_ids.append(new_tag['id'])
                        # Add to cache to avoid future creations
                        if cached_tags is not None:
                            cached_tags.append(new_tag)
                            new_tags_created = True
            
            # Update cache if new tags were created
            if new_tags_created and cached_tags is not None:
                self._set_cached_data('tags', cached_tags, cache_key)
            
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
                    
                    self.logger.info(f"Successfully published post with ID {post_id} at {post_url} to site {site_id}")
                    
                    return {
                        'post_id': post_id,
                        'post_url': post_url,
                        'site_id': site_id,
                        'status': 'published'
                    }
                else:
                    raise Exception(f"Failed to publish post to multisite: {response}")
                    
            except Exception as e:
                self.logger.error(f"Error publishing post to multisite (attempt {attempt+1}/{max_retries}): {str(e)}")
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)  # Exponential backoff
                else:
                    raise Exception(f"Failed to publish post to multisite after {max_retries} attempts: {str(e)}")

    def get_site_list(self):
        """
        Get a list of all sites in the WordPress Multisite network.
        Uses caching to reduce API calls.
        
        Returns:
            list: List of site information dictionaries with id, name, url, and domain
        """
        # Check if we have cached data
        cached_sites = self._get_cached_data('sites')
        if cached_sites is not None:
            return cached_sites
            
        if not self.is_multisite:
            self.logger.warning("WordPress is not configured as Multisite")
            sites = [{'id': 1, 'name': 'Main Site', 'url': self.default_wordpress_url, 'is_main': True}]
            return self._set_cached_data('sites', sites)
            
        if not self.default_wordpress_url or not self.default_wordpress_username or not self.default_wordpress_password:
            raise Exception("Default WordPress credentials are not available from Key Vault")
            
        # Ensure WordPress URL has the correct format
        wordpress_url = self.default_wordpress_url
        if not wordpress_url.endswith('/'):
            wordpress_url += '/'
            
        if not wordpress_url.endswith('wp-json/'):
            wordpress_url += 'wp-json/'
            
        # Create the endpoint URL for sites list using Mercator REST API extension
        endpoint = f"{wordpress_url}wp/v2/sites"
        
        try:
            sites = self._make_request('GET', endpoint, auth=(self.default_wordpress_username, self.default_wordpress_password))
            
            if sites and isinstance(sites, list):
                # Transform site data into a simplified format
                site_list = []
                network_id = int(self.network_id) if self.network_id else 1
                
                for site in sites:
                    site_list.append({
                        'id': site['id'],
                        'name': site['name'],
                        'url': site['url'],
                        'domain': site.get('domain', ''),
                        'path': site.get('path', '/'),
                        'is_main': site['id'] == network_id
                    })
                    
                # Cache the site list for future requests
                return self._set_cached_data('sites', site_list)
            else:
                self.logger.warning(f"Unexpected response format from sites endpoint: {sites}")
                return []
                
        except Exception as e:
            self.logger.error(f"Error retrieving site list: {str(e)}")
            return []
            
    def get_mapped_domains(self, site_id):
        """
        Get all domains mapped to a specific site in the WordPress Multisite network.
        Uses caching to reduce API calls.
        
        Args:
            site_id (int): The site ID to get mapped domains for
            
        Returns:
            list: List of mapped domain information including primary domain and aliases
        """
        # Check cache first
        site_id_str = str(site_id)  # Convert to string for dictionary key
        cached_domains = self._get_cached_data('domains', site_id_str)
        if cached_domains is not None:
            return cached_domains
            
        if not self.is_multisite:
            self.logger.warning("WordPress is not configured as Multisite")
            return []
            
        if not self.default_wordpress_url or not self.default_wordpress_username or not self.default_wordpress_password:
            raise Exception("Default WordPress credentials are not available from Key Vault")
            
        # Ensure WordPress URL has the correct format
        wordpress_url = self.default_wordpress_url
        if not wordpress_url.endswith('/'):
            wordpress_url += '/'
            
        if not wordpress_url.endswith('wp-json/'):
            wordpress_url += 'wp-json/'
            
        # Create the endpoint URL for domains using Mercator REST API extension
        endpoint = f"{wordpress_url}wp/v2/sites/{site_id}/domains"
        
        try:
            domains = self._make_request('GET', endpoint, auth=(self.default_wordpress_username, self.default_wordpress_password))
            
            if domains and isinstance(domains, list):
                # Cache the domains for this site
                return self._set_cached_data('domains', domains, site_id_str)
            else:
                self.logger.warning(f"Unexpected response format from domains endpoint: {domains}")
                return []
                
        except Exception as e:
            self.logger.error(f"Error retrieving mapped domains: {str(e)}")
            return []
            
    def map_domain(self, site_id, domain):
        """
        Map a domain to a specific site in the WordPress Multisite network.
        
        Args:
            site_id (int): The site ID to map the domain to
            domain (str): The domain to map
            
        Returns:
            dict: Result of the domain mapping operation
        """
        if not self.is_multisite:
            raise Exception("WordPress is not configured as Multisite")
            
        if not self.default_wordpress_url or not self.default_wordpress_username or not self.default_wordpress_password:
            raise Exception("Default WordPress credentials are not available from Key Vault")
            
        # Ensure WordPress URL has the correct format
        wordpress_url = self.default_wordpress_url
        if not wordpress_url.endswith('/'):
            wordpress_url += '/'
            
        if not wordpress_url.endswith('wp-json/'):
            wordpress_url += 'wp-json/'
            
        # Create the endpoint URL for domains using Mercator REST API extension
        endpoint = f"{wordpress_url}wp/v2/sites/{site_id}/domains"
        
        # Prepare domain mapping data
        domain_data = {
            'domain': domain,
            'active': True
        }
        
        try:
            result = self._make_request('POST', endpoint, auth=(self.default_wordpress_username, self.default_wordpress_password), json=domain_data)
            
            if result and 'id' in result:
                self.logger.info(f"Successfully mapped domain {domain} to site {site_id}")
                
                # Invalidate site domains cache since we've added a new domain
                if 'domains' in self._cache and str(site_id) in self._cache['domains']:
                    del self._cache['domains'][str(site_id)]
                    self.logger.debug(f"Invalidated domains cache for site ID {site_id}")
                
                return {
                    'success': True,
                    'domain_id': result['id'],
                    'domain': result['domain'],
                    'site_id': site_id
                }
            else:
                raise Exception(f"Failed to map domain: {result}")
                
        except Exception as e:
            self.logger.error(f"Error mapping domain: {str(e)}")
            raise Exception(f"Failed to map domain {domain} to site {site_id}: {str(e)}")
            
    def delete_domain_mapping(self, site_id, domain_id):
        """
        Delete a domain mapping from a site in the WordPress Multisite network.
        
        Args:
            site_id (int): The site ID the domain is mapped to
            domain_id (int): The ID of the domain mapping to delete
            
        Returns:
            dict: Result of the domain mapping deletion operation
        """
        if not self.is_multisite:
            raise Exception("WordPress is not configured as Multisite")
            
        if not self.default_wordpress_url or not self.default_wordpress_username or not self.default_wordpress_password:
            raise Exception("Default WordPress credentials are not available from Key Vault")
            
        # Ensure WordPress URL has the correct format
        wordpress_url = self.default_wordpress_url
        if not wordpress_url.endswith('/'):
            wordpress_url += '/'
            
        if not wordpress_url.endswith('wp-json/'):
            wordpress_url += 'wp-json/'
            
        # Create the endpoint URL for the specific domain using Mercator REST API extension
        endpoint = f"{wordpress_url}wp/v2/sites/{site_id}/domains/{domain_id}"
        
        try:
            # DELETE request to remove the domain mapping
            result = self._make_request('DELETE', endpoint, auth=(self.default_wordpress_username, self.default_wordpress_password))
            
            self.logger.info(f"Successfully deleted domain mapping ID {domain_id} from site {site_id}")
            
            # Invalidate site domains cache since we've removed a domain
            if 'domains' in self._cache and str(site_id) in self._cache['domains']:
                del self._cache['domains'][str(site_id)]
                self.logger.debug(f"Invalidated domains cache for site ID {site_id}")
            
            return {
                'success': True,
                'domain_id': domain_id,
                'site_id': site_id
            }
                
        except Exception as e:
            self.logger.error(f"Error deleting domain mapping: {str(e)}")
            raise Exception(f"Failed to delete domain mapping ID {domain_id} from site {site_id}: {str(e)}")
    
    # Create a session with connection pooling for better performance
    _session = None
    
    @property
    def session(self):
        """Get or create a requests session with connection pooling"""
        if self._session is None:
            self._session = requests.Session()
            # Set up reasonable timeouts
            self._session.mount('https://', requests.adapters.HTTPAdapter(
                max_retries=3,  # Auto-retry on certain errors
                pool_connections=10,  # Connection pool size
                pool_maxsize=20  # Maximum number of connections to keep in the pool
            ))
            self._session.mount('http://', requests.adapters.HTTPAdapter(
                max_retries=3,
                pool_connections=10,
                pool_maxsize=20
            ))
        return self._session
    
    def _make_request(self, method, url, **kwargs):
        """
        Make HTTP request with error handling, logging, connection pooling and retries.
        
        Args:
            method (str): HTTP method (GET, POST, etc.)
            url (str): The URL to call
            **kwargs: Additional arguments to pass to the request
            
        Returns:
            dict: The JSON response as a dictionary
            
        Raises:
            Exception: If the request fails
        """
        # Set defaults if not provided
        if 'timeout' not in kwargs:
            kwargs['timeout'] = (5, 30)  # (connect timeout, read timeout)
            
        try:
            # Use session for connection pooling
            response = self.session.request(method, url, **kwargs)
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
            error_msg = f"Timeout when calling {url} (timeout settings: {kwargs.get('timeout')})"
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
            
    def _sanitize_content(self, content):
        """
        Sanitize content to prevent WordPress injection attacks and XSS.
        
        Args:
            content (str): The content to sanitize
            
        Returns:
            str: Sanitized content
        """
        if not content:
            return content
            
        # Basic HTML sanitization for WordPress
        import re
        import html
        
        # First, escape HTML entities
        sanitized = html.escape(content)
        
        # Allow specific HTML tags that WordPress allows by default
        allowed_tags = [
            'p', 'br', 'em', 'strong', 'ul', 'ol', 'li', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
            'blockquote', 'code', 'pre', 'a', 'img'
        ]
        
        # Replace escaped tags with their original form for allowed tags
        for tag in allowed_tags:
            # Opening tags
            sanitized = re.sub(
                r'&lt;' + tag + r'(\s+[^&>]*)&gt;',
                r'<' + tag + r'\1>',
                sanitized
            )
            # Closing tags
            sanitized = re.sub(
                r'&lt;/' + tag + r'&gt;',
                r'</' + tag + r'>',
                sanitized
            )
            
        # Remove potential script injections (even if escaped)
        sanitized = re.sub(r'&lt;script.*?&gt;.*?&lt;/script&gt;', '', sanitized, flags=re.DOTALL)
        sanitized = re.sub(r'<script.*?>.*?</script>', '', sanitized, flags=re.DOTALL)
        
        # Remove on* attributes that could contain JavaScript
        sanitized = re.sub(r'(\s)on\w+\s*=\s*["\'][^"\']*["\']', '', sanitized)
        
        # Remove iframe tags that could embed malicious content
        sanitized = re.sub(r'&lt;iframe.*?&gt;.*?&lt;/iframe&gt;', '', sanitized, flags=re.DOTALL)
        sanitized = re.sub(r'<iframe.*?>.*?</iframe>', '', sanitized, flags=re.DOTALL)
        
        return sanitized
