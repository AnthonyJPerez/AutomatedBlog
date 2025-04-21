import os
import json
import logging
import requests
from datetime import datetime
from azure.identity import DefaultAzureCredential
from azure.keyvault.secrets import SecretClient

logger = logging.getLogger(__name__)

class SocialMediaService:
    """
    Service for promoting content on social media platforms.
    Manages authentication, content formatting, and posting to different platforms.
    """
    
    def __init__(self, use_key_vault=True):
        """
        Initialize the social media service.
        
        Args:
            use_key_vault (bool): Whether to try to use Azure Key Vault for credentials
        """
        self.use_key_vault = use_key_vault
        self.key_vault_url = os.environ.get("KEY_VAULT_URL")
        self.secret_client = None
        self.platforms = {}
        
        # Initialize platform configurations
        self._init_twitter()
        self._init_linkedin()
        self._init_facebook()
        self._init_reddit()
        self._init_medium()
        self._init_bluesky()
        self._init_truth_social()
        self._init_devto()
        
        logger.info("Social Media service initialized.")
    
    def _init_twitter(self):
        """Initialize Twitter configuration"""
        try:
            # Try to get Twitter credentials
            api_key = self._get_secret("TWITTER-API-KEY")
            api_secret = self._get_secret("TWITTER-API-SECRET")
            access_token = self._get_secret("TWITTER-ACCESS-TOKEN")
            access_secret = self._get_secret("TWITTER-ACCESS-SECRET")
            
            if api_key and api_secret and access_token and access_secret:
                self.platforms["twitter"] = {
                    "enabled": True,
                    "api_key": api_key,
                    "api_secret": api_secret,
                    "access_token": access_token,
                    "access_secret": access_secret
                }
                logger.info("Twitter configuration loaded.")
            else:
                self.platforms["twitter"] = {"enabled": False}
                logger.warning("Twitter credentials incomplete, platform disabled.")
        except Exception as e:
            self.platforms["twitter"] = {"enabled": False}
            logger.warning(f"Failed to initialize Twitter: {str(e)}")
    
    def _init_linkedin(self):
        """Initialize LinkedIn configuration"""
        try:
            # Try to get LinkedIn credentials
            client_id = self._get_secret("LINKEDIN-CLIENT-ID")
            client_secret = self._get_secret("LINKEDIN-CLIENT-SECRET")
            access_token = self._get_secret("LINKEDIN-ACCESS-TOKEN")
            
            if client_id and client_secret and access_token:
                self.platforms["linkedin"] = {
                    "enabled": True,
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "access_token": access_token
                }
                logger.info("LinkedIn configuration loaded.")
            else:
                self.platforms["linkedin"] = {"enabled": False}
                logger.warning("LinkedIn credentials incomplete, platform disabled.")
        except Exception as e:
            self.platforms["linkedin"] = {"enabled": False}
            logger.warning(f"Failed to initialize LinkedIn: {str(e)}")
    
    def _init_facebook(self):
        """Initialize Facebook configuration"""
        try:
            # Try to get Facebook credentials
            app_id = self._get_secret("FACEBOOK-APP-ID")
            app_secret = self._get_secret("FACEBOOK-APP-SECRET")
            access_token = self._get_secret("FACEBOOK-ACCESS-TOKEN")
            page_id = self._get_secret("FACEBOOK-PAGE-ID")
            
            if app_id and app_secret and access_token and page_id:
                self.platforms["facebook"] = {
                    "enabled": True,
                    "app_id": app_id,
                    "app_secret": app_secret,
                    "access_token": access_token,
                    "page_id": page_id
                }
                logger.info("Facebook configuration loaded.")
            else:
                self.platforms["facebook"] = {"enabled": False}
                logger.warning("Facebook credentials incomplete, platform disabled.")
        except Exception as e:
            self.platforms["facebook"] = {"enabled": False}
            logger.warning(f"Failed to initialize Facebook: {str(e)}")
            
    def _init_reddit(self):
        """Initialize Reddit configuration"""
        try:
            # Try to get Reddit credentials
            client_id = self._get_secret("REDDIT-CLIENT-ID")
            client_secret = self._get_secret("REDDIT-CLIENT-SECRET")
            username = self._get_secret("REDDIT-USERNAME")
            password = self._get_secret("REDDIT-PASSWORD")
            user_agent = self._get_secret("REDDIT-USER-AGENT") or "ContentSyndicator/1.0"
            
            if client_id and client_secret and username and password:
                self.platforms["reddit"] = {
                    "enabled": True,
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "username": username,
                    "password": password,
                    "user_agent": user_agent
                }
                logger.info("Reddit configuration loaded.")
            else:
                self.platforms["reddit"] = {"enabled": False}
                logger.warning("Reddit credentials incomplete, platform disabled.")
        except Exception as e:
            self.platforms["reddit"] = {"enabled": False}
            logger.warning(f"Failed to initialize Reddit: {str(e)}")
            
    def _init_medium(self):
        """Initialize Medium configuration"""
        try:
            # Try to get Medium credentials
            integration_token = self._get_secret("MEDIUM-INTEGRATION-TOKEN")
            author_id = self._get_secret("MEDIUM-AUTHOR-ID")
            
            if integration_token and author_id:
                self.platforms["medium"] = {
                    "enabled": True,
                    "integration_token": integration_token,
                    "author_id": author_id
                }
                logger.info("Medium configuration loaded.")
            else:
                self.platforms["medium"] = {"enabled": False}
                logger.warning("Medium credentials incomplete, platform disabled.")
        except Exception as e:
            self.platforms["medium"] = {"enabled": False}
            logger.warning(f"Failed to initialize Medium: {str(e)}")
            
    def _init_bluesky(self):
        """Initialize Bluesky configuration"""
        try:
            # Try to get Bluesky credentials
            identifier = self._get_secret("BLUESKY-IDENTIFIER")  # username/handle
            app_password = self._get_secret("BLUESKY-APP-PASSWORD")
            pds_url = self._get_secret("BLUESKY-PDS-URL") or "https://bsky.social"
            
            # Store for session tokens from authentication
            access_jwt = None
            refresh_jwt = None
            
            if identifier and app_password:
                self.platforms["bluesky"] = {
                    "enabled": True,
                    "identifier": identifier,
                    "app_password": app_password,
                    "pds_url": pds_url,
                    "access_jwt": access_jwt,
                    "refresh_jwt": refresh_jwt,
                    "jwt_expiration": None
                }
                logger.info("Bluesky configuration loaded.")
            else:
                self.platforms["bluesky"] = {"enabled": False}
                logger.warning("Bluesky credentials incomplete, platform disabled.")
        except Exception as e:
            self.platforms["bluesky"] = {"enabled": False}
            logger.warning(f"Failed to initialize Bluesky: {str(e)}")
            
    def _init_truth_social(self):
        """Initialize Truth Social configuration"""
        try:
            # Truth Social uses OAuth 2.0 (Mastodon API)
            client_id = self._get_secret("TRUTH-SOCIAL-CLIENT-ID")
            client_secret = self._get_secret("TRUTH-SOCIAL-CLIENT-SECRET")
            username = self._get_secret("TRUTH-SOCIAL-USERNAME")
            access_token = self._get_secret("TRUTH-SOCIAL-ACCESS-TOKEN")
            
            # Either need client credentials + username for OAuth flow
            # or a pre-obtained access token
            if (client_id and client_secret and username) or access_token:
                self.platforms["truth_social"] = {
                    "enabled": True,
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "username": username,
                    "access_token": access_token,
                    "api_base": "https://truthsocial.com/api/v1/"
                }
                logger.info("Truth Social configuration loaded.")
            else:
                self.platforms["truth_social"] = {"enabled": False}
                logger.warning("Truth Social credentials incomplete, platform disabled.")
        except Exception as e:
            self.platforms["truth_social"] = {"enabled": False}
            logger.warning(f"Failed to initialize Truth Social: {str(e)}")
            
    def _init_devto(self):
        """Initialize DEV.to configuration"""
        try:
            # DEV.to uses API Key authentication
            api_key = self._get_secret("DEVTO-API-KEY")
            organization_name = self._get_secret("DEVTO-ORGANIZATION") # Optional, for publishing to organization
            
            if api_key:
                self.platforms["devto"] = {
                    "enabled": True,
                    "api_key": api_key,
                    "organization_name": organization_name,
                    "api_base": "https://dev.to/api/"
                }
                logger.info("DEV.to configuration loaded.")
            else:
                self.platforms["devto"] = {"enabled": False}
                logger.warning("DEV.to credentials incomplete, platform disabled.")
        except Exception as e:
            self.platforms["devto"] = {"enabled": False}
            logger.warning(f"Failed to initialize DEV.to: {str(e)}")
    
    def _get_secret(self, secret_name):
        """
        Get a secret from environment variables or Key Vault.
        
        Args:
            secret_name (str): The name of the secret
            
        Returns:
            str: The secret value, or None if not found
        """
        # First try environment variables (direct and normalized)
        env_value = os.environ.get(secret_name)
        if env_value:
            return env_value
        
        env_value = os.environ.get(secret_name.replace("-", "_"))
        if env_value:
            return env_value
        
        # Then try Key Vault if enabled
        if self.use_key_vault and self.key_vault_url:
            try:
                if not self.secret_client:
                    credential = DefaultAzureCredential()
                    self.secret_client = SecretClient(vault_url=self.key_vault_url, credential=credential)
                
                secret = self.secret_client.get_secret(secret_name)
                return secret.value
            except Exception as e:
                logger.warning(f"Failed to get secret {secret_name} from Key Vault: {str(e)}")
        
        return None
    
    def post_to_twitter(self, message, media_url=None):
        """
        Post a message to Twitter.
        
        Args:
            message (str): The message to post
            media_url (str, optional): URL of image to attach
            
        Returns:
            dict: Response from the API
        """
        if not self.platforms.get("twitter", {}).get("enabled", False):
            logger.warning("Twitter is not configured or disabled.")
            return {"success": False, "error": "Twitter is not configured"}
        
        try:
            # In a production app, we would use the Twitter API SDK
            # For this demo, we'll simulate the posting
            logger.info(f"Posting to Twitter: {message[:30]}...")
            
            # Placeholder for actual Twitter API integration
            # In real implementation, use tweepy or Twitter API v2
            
            return {
                "success": True,
                "platform": "twitter",
                "post_id": "simulated_tweet_id_123",
                "timestamp": datetime.now().isoformat()
            }
        except Exception as e:
            logger.error(f"Failed to post to Twitter: {str(e)}")
            return {"success": False, "platform": "twitter", "error": str(e)}
    
    def post_to_linkedin(self, title, message, url, image_url=None):
        """
        Post a message to LinkedIn.
        
        Args:
            title (str): Title of the post
            message (str): The message body
            url (str): URL to the article
            image_url (str, optional): URL of image to attach
            
        Returns:
            dict: Response from the API
        """
        if not self.platforms.get("linkedin", {}).get("enabled", False):
            logger.warning("LinkedIn is not configured or disabled.")
            return {"success": False, "error": "LinkedIn is not configured"}
        
        try:
            # In a production app, we would use the LinkedIn API
            # For this demo, we'll simulate the posting
            logger.info(f"Posting to LinkedIn: {title}")
            
            # Placeholder for actual LinkedIn API integration
            
            return {
                "success": True,
                "platform": "linkedin",
                "post_id": "simulated_linkedin_post_123",
                "timestamp": datetime.now().isoformat()
            }
        except Exception as e:
            logger.error(f"Failed to post to LinkedIn: {str(e)}")
            return {"success": False, "platform": "linkedin", "error": str(e)}
    
    def post_to_facebook(self, message, link=None, image_url=None):
        """
        Post a message to Facebook.
        
        Args:
            message (str): The message to post
            link (str, optional): URL to share
            image_url (str, optional): URL of image to attach
            
        Returns:
            dict: Response from the API
        """
        if not self.platforms.get("facebook", {}).get("enabled", False):
            logger.warning("Facebook is not configured or disabled.")
            return {"success": False, "error": "Facebook is not configured"}
        
        try:
            # In a production app, we would use the Facebook Graph API
            # For this demo, we'll simulate the posting
            logger.info(f"Posting to Facebook: {message[:30]}...")
            
            # Placeholder for actual Facebook API integration
            
            return {
                "success": True,
                "platform": "facebook",
                "post_id": "simulated_fb_post_123",
                "timestamp": datetime.now().isoformat()
            }
        except Exception as e:
            logger.error(f"Failed to post to Facebook: {str(e)}")
            return {"success": False, "platform": "facebook", "error": str(e)}
            
    def post_to_reddit(self, title, text=None, url=None, subreddit=""):
        """
        Post a message to Reddit.
        
        Args:
            title (str): The post title
            text (str, optional): Text for a self post
            url (str, optional): URL for a link post
            subreddit (str): Subreddit to post to
            
        Returns:
            dict: Response from the API
        """
        if not self.platforms.get("reddit", {}).get("enabled", False):
            logger.warning("Reddit is not configured or disabled.")
            return {"success": False, "error": "Reddit is not configured"}
        
        if not subreddit:
            logger.warning("No subreddit specified for Reddit post.")
            return {"success": False, "error": "No subreddit specified"}
            
        if not (text or url):
            logger.warning("Either text or URL must be provided for Reddit post.")
            return {"success": False, "error": "Either text or URL must be provided"}
        
        try:
            # In a production app, we would use PRAW (Python Reddit API Wrapper)
            # For this demo, we'll simulate the posting
            post_type = "link" if url else "self"
            logger.info(f"Posting to Reddit (r/{subreddit}): {title} [{post_type}]")
            
            # Placeholder for actual Reddit API integration
            # Example PRAW code:
            # reddit = praw.Reddit(
            #     client_id=self.platforms["reddit"]["client_id"],
            #     client_secret=self.platforms["reddit"]["client_secret"],
            #     username=self.platforms["reddit"]["username"],
            #     password=self.platforms["reddit"]["password"],
            #     user_agent=self.platforms["reddit"]["user_agent"]
            # )
            # subreddit = reddit.subreddit(subreddit)
            # if url:
            #     submission = subreddit.submit(title, url=url)
            # else:
            #     submission = subreddit.submit(title, selftext=text)
            
            return {
                "success": True,
                "platform": "reddit",
                "subreddit": subreddit,
                "post_id": "simulated_reddit_post_123",
                "post_url": f"https://reddit.com/r/{subreddit}/comments/simulated_id/",
                "timestamp": datetime.now().isoformat()
            }
        except Exception as e:
            logger.error(f"Failed to post to Reddit: {str(e)}")
            return {"success": False, "platform": "reddit", "error": str(e)}
            
    def post_to_medium(self, title, content, tags=None, publish_status="draft"):
        """
        Post an article to Medium.
        
        Args:
            title (str): The article title
            content (str): The article content in markdown or HTML format
            tags (list, optional): List of tags for the article
            publish_status (str): Either "draft", "unlisted", or "public"
            
        Returns:
            dict: Response from the API
        """
        if not self.platforms.get("medium", {}).get("enabled", False):
            logger.warning("Medium is not configured or disabled.")
            return {"success": False, "error": "Medium is not configured"}
        
        if not tags:
            tags = []
            
        if publish_status not in ["draft", "unlisted", "public"]:
            publish_status = "draft"
        
        try:
            # In a production app, we would use Medium API
            # For this demo, we'll simulate the posting
            logger.info(f"Posting to Medium: {title} ({publish_status}) with {len(tags)} tags")
            
            # Placeholder for actual Medium API integration
            # Example code:
            # headers = {
            #     "Authorization": f"Bearer {self.platforms['medium']['integration_token']}",
            #     "Content-Type": "application/json"
            # }
            # 
            # data = {
            #     "title": title,
            #     "contentFormat": "markdown",
            #     "content": content,
            #     "tags": tags,
            #     "publishStatus": publish_status
            # }
            # 
            # response = requests.post(
            #     f"https://api.medium.com/v1/users/{self.platforms['medium']['author_id']}/posts",
            #     headers=headers,
            #     json=data
            # )
            # response_data = response.json()
            
            return {
                "success": True,
                "platform": "medium",
                "post_id": "simulated_medium_post_123",
                "post_url": "https://medium.com/@user/simulated-post-123",
                "status": publish_status,
                "timestamp": datetime.now().isoformat()
            }
        except Exception as e:
            logger.error(f"Failed to post to Medium: {str(e)}")
            return {"success": False, "platform": "medium", "error": str(e)}
    
    def promote_content(self, blog_id, run_id, content, publish_data):
        """
        Promote content across multiple social media platforms.
        
        Args:
            blog_id (str): ID of the blog
            run_id (str): ID of the content run
            content (dict): The content data (title, excerpt, etc)
            publish_data (dict): Publishing data including URL
            
        Returns:
            dict: Results from each platform
        """
        if not content or not publish_data or not publish_data.get("url"):
            logger.warning(f"Missing required data for social media promotion: blog_id={blog_id}, run_id={run_id}")
            return {"success": False, "error": "Missing required data for promotion"}
        
        results = {
            "timestamp": datetime.now().isoformat(),
            "blog_id": blog_id,
            "run_id": run_id,
            "platforms": {}
        }
        
        # Extract content details
        title = content.get("title", "New Blog Post")
        excerpt = content.get("excerpt", "")
        url = publish_data.get("url", "")
        image_url = content.get("featured_image")
        full_content = content.get("content", "")
        tags = content.get("tags", [])
        
        # Try to detect a relevant subreddit from the blog configuration
        # This would normally be stored in the blog config
        subreddit = "blogging"  # Default fallback
        
        # Get subreddit from config if available
        blog_config = publish_data.get("blog_config", {})
        if blog_config and "integrations" in blog_config:
            subreddit = blog_config.get("integrations", {}).get("reddit_subreddit", subreddit)
        
        # Format messages for each platform
        twitter_msg = f"{title}\n\n{excerpt[:100]}... {url}"
        linkedin_msg = f"{excerpt[:500]}... Read more at the link."
        facebook_msg = f"{title}\n\n{excerpt[:250]}... Click the link to read more!"
        reddit_text = f"{excerpt[:500]}...\n\nRead the full article: {url}"
        bluesky_msg = f"{title}\n\n{excerpt[:300]}...\n\n{url}"
        truth_social_msg = f"{title}\n\n{excerpt[:280]}... {url}"
        
        # List to track platform results
        platform_results = []
        
        # Post to Twitter (if enabled)
        if "twitter" in self.platforms and self.platforms["twitter"].get("enabled", False):
            twitter_result = self.post_to_twitter(twitter_msg, image_url)
            results["platforms"]["twitter"] = twitter_result
            platform_results.append(twitter_result.get("success", False))
        
        # Post to LinkedIn (if enabled)
        if "linkedin" in self.platforms and self.platforms["linkedin"].get("enabled", False):
            linkedin_result = self.post_to_linkedin(title, linkedin_msg, url, image_url)
            results["platforms"]["linkedin"] = linkedin_result
            platform_results.append(linkedin_result.get("success", False))
        
        # Post to Facebook (if enabled)
        if "facebook" in self.platforms and self.platforms["facebook"].get("enabled", False):
            facebook_result = self.post_to_facebook(facebook_msg, url, image_url)
            results["platforms"]["facebook"] = facebook_result
            platform_results.append(facebook_result.get("success", False))
        
        # Post to Reddit (if enabled)
        if "reddit" in self.platforms and self.platforms["reddit"].get("enabled", False):
            reddit_result = self.post_to_reddit(title, reddit_text, None, subreddit)
            results["platforms"]["reddit"] = reddit_result
            platform_results.append(reddit_result.get("success", False))
        
        # Post to Medium (if enabled)
        if "medium" in self.platforms and self.platforms["medium"].get("enabled", False):
            # Medium gets the full content in markdown format
            medium_result = self.post_to_medium(
                title, 
                full_content, 
                tags=tags, 
                publish_status="public"  # Can be configurable
            )
            results["platforms"]["medium"] = medium_result
            platform_results.append(medium_result.get("success", False))
            
        # Post to Bluesky (if enabled)
        if "bluesky" in self.platforms and self.platforms["bluesky"].get("enabled", False):
            bluesky_result = self.post_to_bluesky(
                bluesky_msg,
                image_url=image_url,
                alt_text=title,
                external_url=url
            )
            results["platforms"]["bluesky"] = bluesky_result
            platform_results.append(bluesky_result.get("success", False))
            
        # Post to Truth Social (if enabled)
        if "truth_social" in self.platforms and self.platforms["truth_social"].get("enabled", False):
            truth_social_result = self.post_to_truth_social(
                truth_social_msg,
                media_url=image_url
            )
            results["platforms"]["truth_social"] = truth_social_result
            platform_results.append(truth_social_result.get("success", False))
            
        # Post to DEV.to (if enabled)
        if "devto" in self.platforms and self.platforms["devto"].get("enabled", False):
            # DEV.to gets the full content in markdown format
            # Determine publish status based on blog configuration
            should_publish = blog_config.get("integrations", {}).get("devto_publish_immediately", False)
            
            devto_result = self.post_to_devto(
                title,
                full_content,
                tags=tags[:4],  # DEV.to has a limit of 4 tags
                canonical_url=url,  # Set the original blog as canonical to avoid SEO issues
                publish=should_publish
            )
            results["platforms"]["devto"] = devto_result
            platform_results.append(devto_result.get("success", False))
        
        # Determine overall success (at least one platform worked)
        if platform_results:
            results["success"] = any(platform_results)
        else:
            results["success"] = False
            results["message"] = "No social media platforms are enabled"
        
        logger.info(f"Content promotion completed for {blog_id}/{run_id} with success={results['success']}")
        return results
    
    def get_enabled_platforms(self):
        """
        Get a list of enabled social media platforms.
        
        Returns:
            list: Names of enabled platforms
        """
        return [name for name, config in self.platforms.items() if config.get("enabled", False)]
        
    def post_to_bluesky(self, text, image_url=None, alt_text=None, external_url=None):
        """
        Post a message to Bluesky.
        
        Args:
            text (str): The message text to post
            image_url (str, optional): URL of image to attach
            alt_text (str, optional): Alt text for the image
            external_url (str, optional): External URL to include
            
        Returns:
            dict: Response from the API
        """
        if not self.platforms.get("bluesky", {}).get("enabled", False):
            logger.warning("Bluesky is not configured or disabled.")
            return {"success": False, "error": "Bluesky is not configured"}
        
        try:
            # In a production app, we would use the atproto Python library
            logger.info(f"Posting to Bluesky: {text[:30]}...")
            
            bluesky_config = self.platforms["bluesky"]
            
            # Authentication with AT Protocol works by:
            # 1. Create a session with identifier (handle) and app password
            # 2. Get access JWT and refresh JWT tokens
            # 3. Use the access JWT for subsequent API calls
            # 4. Refresh the token when expired with the refresh JWT
            
            # Example implementation with the atproto library:
            # from atproto import Client
            # import datetime
            # import json
            # import requests
            # 
            # # Check if we need to authenticate or refresh tokens
            # current_time = datetime.datetime.now()
            # needs_auth = (
            #     not bluesky_config.get("access_jwt") or 
            #     not bluesky_config.get("jwt_expiration") or 
            #     current_time >= bluesky_config.get("jwt_expiration")
            # )
            #
            # if needs_auth:
            #     # AT Protocol authentication
            #     pds_url = bluesky_config.get("pds_url", "https://bsky.social")
            #     auth_url = f"{pds_url}/xrpc/com.atproto.server.createSession"
            #     
            #     auth_data = {
            #         "identifier": bluesky_config["identifier"],
            #         "password": bluesky_config["app_password"]
            #     }
            #     
            #     response = requests.post(auth_url, json=auth_data)
            #     if response.status_code != 200:
            #         raise Exception(f"Authentication failed: {response.text}")
            #         
            #     session_data = response.json()
            #     bluesky_config["access_jwt"] = session_data["accessJwt"]
            #     bluesky_config["refresh_jwt"] = session_data["refreshJwt"]
            #     bluesky_config["did"] = session_data["did"]
            #     
            #     # Set expiration (typically 2 hours from now)
            #     bluesky_config["jwt_expiration"] = current_time + datetime.timedelta(hours=2)
            #
            # # Now create the post using the authenticated session
            # create_post_url = f"{bluesky_config.get('pds_url', 'https://bsky.social')}/xrpc/com.atproto.repo.createRecord"
            # 
            # headers = {
            #     "Authorization": f"Bearer {bluesky_config['access_jwt']}",
            #     "Content-Type": "application/json"
            # }
            # 
            # # Prepare post data
            # post_data = {
            #     "repo": bluesky_config["did"],
            #     "collection": "app.bsky.feed.post",
            #     "record": {
            #         "$type": "app.bsky.feed.post",
            #         "text": text,
            #         "createdAt": datetime.datetime.now().isoformat(),
            #         "langs": ["en"]
            #     }
            # }
            # 
            # # If we have an external URL, add it as a facet
            # if external_url and external_url in text:
            #     start = text.find(external_url)
            #     if start != -1:
            #         end = start + len(external_url)
            #         post_data["record"]["facets"] = [{
            #             "index": {
            #                 "byteStart": start,
            #                 "byteEnd": end
            #             },
            #             "features": [{
            #                 "$type": "app.bsky.richtext.facet#link",
            #                 "uri": external_url
            #             }]
            #         }]
            # 
            # # If we have an image, upload it first
            # if image_url:
            #     # Download image
            #     img_response = requests.get(image_url)
            #     if img_response.status_code == 200:
            #         # Upload blob to Bluesky
            #         upload_url = f"{bluesky_config.get('pds_url', 'https://bsky.social')}/xrpc/com.atproto.repo.uploadBlob"
            #         files = {"file": img_response.content}
            #         upload_response = requests.post(upload_url, headers=headers, files=files)
            #         
            #         if upload_response.status_code == 200:
            #             blob_data = upload_response.json()["blob"]
            #             post_data["record"]["embed"] = {
            #                 "$type": "app.bsky.embed.images",
            #                 "images": [{
            #                     "alt": alt_text or "",
            #                     "image": blob_data
            #                 }]
            #             }
            # 
            # # Send the post request
            # response = requests.post(create_post_url, headers=headers, json=post_data)
            # if response.status_code != 200:
            #     raise Exception(f"Failed to create post: {response.text}")
            # 
            # result = response.json()
            # return {
            #     "success": True,
            #     "platform": "bluesky",
            #     "post_id": result.get("cid", "unknown"),
            #     "post_uri": result.get("uri", "unknown"),
            #     "timestamp": datetime.datetime.now().isoformat()
            # }
            
            # For now, we'll simulate the posting
            logger.info("Simulating Bluesky post (AT Protocol implementation not activated)")
            return {
                "success": True,
                "platform": "bluesky",
                "post_id": "simulated_bluesky_post_123",
                "post_uri": "at://did:plc:simulated/app.bsky.feed.post/simulated123",
                "timestamp": datetime.now().isoformat()
            }
        except Exception as e:
            logger.error(f"Failed to post to Bluesky: {str(e)}")
            return {"success": False, "platform": "bluesky", "error": str(e)}
    
    def post_to_devto(self, title, content, tags=None, canonical_url=None, series=None, publish=False):
        """
        Post an article to DEV.to.
        
        Args:
            title (str): The article title
            content (str): The article content in markdown format
            tags (list, optional): List of tags for the article (max 4)
            canonical_url (str, optional): The canonical URL of the original article
            series (str, optional): The series name if part of a series
            publish (bool): Whether to publish immediately (True) or save as draft (False)
            
        Returns:
            dict: Response from the API
        """
        if not self.platforms.get("devto", {}).get("enabled", False):
            logger.warning("DEV.to is not configured or disabled.")
            return {"success": False, "error": "DEV.to is not configured"}
        
        if not tags:
            tags = []
        
        # DEV.to only allows up to 4 tags
        if len(tags) > 4:
            tags = tags[:4]
            logger.warning("DEV.to only supports up to 4 tags. Truncating to first 4.")
        
        try:
            # Prepare the API call
            api_key = self.platforms["devto"]["api_key"]
            api_url = f"{self.platforms['devto']['api_base']}articles"
            organization_name = self.platforms["devto"].get("organization_name")
            
            # Build the request payload
            payload = {
                "article": {
                    "title": title,
                    "body_markdown": content,
                    "published": publish,
                    "tags": tags
                }
            }
            
            # Add optional fields if provided
            if canonical_url:
                payload["article"]["canonical_url"] = canonical_url
            
            if series:
                payload["article"]["series"] = series
                
            if organization_name:
                payload["article"]["organization_id"] = organization_name
            
            logger.info(f"Posting to DEV.to: {title} (publish: {publish}) with {len(tags)} tags")
            
            # Make the actual API call to DEV.to
            headers = {
                "Content-Type": "application/json",
                "api-key": api_key
            }
            response = requests.post(api_url, headers=headers, json=payload)
            response.raise_for_status()
            result = response.json()
            
            return {
                "success": True,
                "platform": "devto",
                "article_id": result["id"],
                "url": result.get("url", f"https://dev.to/article/{result['id']}"),
                "timestamp": datetime.now().isoformat(),
                "status": "draft" if not publish else "published"
            }
        except Exception as e:
            logger.error(f"Failed to post to DEV.to: {str(e)}")
            return {"success": False, "platform": "devto", "error": str(e)}
    
    def post_to_truth_social(self, message, media_url=None):
        """
        Post a message to Truth Social.
        
        Args:
            message (str): The message to post
            media_url (str, optional): URL of image or video to attach
            
        Returns:
            dict: Response from the API
        """
        if not self.platforms.get("truth_social", {}).get("enabled", False):
            logger.warning("Truth Social is not configured or disabled.")
            return {"success": False, "error": "Truth Social is not configured"}
        
        try:
            # Truth Social uses Mastodon API with OAuth 2.0
            logger.info(f"Posting to Truth Social: {message[:30]}...")
            
            truth_config = self.platforms["truth_social"]
            
            # Authentication flow for Truth Social:
            # 1. If we already have an access token, use it directly
            # 2. Otherwise, use client credentials (client_id, client_secret) to obtain an access token
            # 3. Then use the access token for API calls
            
            # Example implementation with requests:
            # import requests
            # import json
            # import base64
            # import datetime
            # 
            # # Check if we need to get an access token
            # needs_token = not truth_config.get("access_token") or not truth_config.get("token_expiration") or datetime.datetime.now() >= truth_config.get("token_expiration")
            # 
            # if needs_token and truth_config.get("client_id") and truth_config.get("client_secret"):
            #     # Get access token using OAuth 2.0 client credentials flow
            #     token_url = "https://truthsocial.com/oauth/token"
            #     
            #     # Prepare credentials
            #     auth_header = base64.b64encode(
            #         f"{truth_config['client_id']}:{truth_config['client_secret']}".encode()
            #     ).decode()
            #     
            #     headers = {
            #         "Authorization": f"Basic {auth_header}",
            #         "Content-Type": "application/x-www-form-urlencoded"
            #     }
            #     
            #     data = {
            #         "grant_type": "client_credentials",
            #         "scope": "read write"
            #     }
            #     
            #     # Add username if available for user-specific access
            #     if truth_config.get("username"):
            #         data["username"] = truth_config["username"]
            #     
            #     response = requests.post(token_url, headers=headers, data=data)
            #     
            #     if response.status_code != 200:
            #         raise Exception(f"Failed to get Truth Social access token: {response.text}")
            #     
            #     token_data = response.json()
            #     truth_config["access_token"] = token_data["access_token"]
            #     
            #     # Set expiration based on expires_in (usually in seconds)
            #     if "expires_in" in token_data:
            #         expiry_seconds = int(token_data["expires_in"])
            #         truth_config["token_expiration"] = datetime.datetime.now() + datetime.timedelta(seconds=expiry_seconds)
            # 
            # # Now use the access token to post
            # if not truth_config.get("access_token"):
            #     raise Exception("No access token available for Truth Social")
            # 
            # api_base = truth_config.get("api_base", "https://truthsocial.com/api/v1/")
            # headers = {
            #     "Authorization": f"Bearer {truth_config['access_token']}",
            #     "Content-Type": "application/json"
            # }
            # 
            # # If we have media to upload, do that first
            # media_ids = []
            # if media_url:
            #     # Download the media file
            #     media_response = requests.get(media_url)
            #     if media_response.status_code == 200:
            #         # Upload to Truth Social
            #         upload_url = f"{api_base}media"
            #         
            #         # Determine content type from URL
            #         content_type = "image/jpeg"  # Default
            #         if media_url.lower().endswith(".png"):
            #             content_type = "image/png"
            #         elif media_url.lower().endswith(".gif"):
            #             content_type = "image/gif"
            #         
            #         files = {
            #             "file": (
            #                 "media_file", 
            #                 media_response.content, 
            #                 content_type
            #             )
            #         }
            #         
            #         upload_response = requests.post(
            #             upload_url, 
            #             headers={"Authorization": f"Bearer {truth_config['access_token']}"},
            #             files=files
            #         )
            #         
            #         if upload_response.status_code == 200:
            #             media_data = upload_response.json()
            #             media_ids.append(media_data["id"])
            # 
            # # Create the post (or "truth")
            # status_url = f"{api_base}statuses"
            # post_data = {
            #     "status": message,
            #     "visibility": "public"
            # }
            # 
            # if media_ids:
            #     post_data["media_ids"] = media_ids
            # 
            # post_response = requests.post(status_url, headers=headers, json=post_data)
            # 
            # if post_response.status_code != 200:
            #     raise Exception(f"Failed to post to Truth Social: {post_response.text}")
            # 
            # result = post_response.json()
            # return {
            #     "success": True,
            #     "platform": "truth_social",
            #     "post_id": result.get("id", "unknown"),
            #     "post_url": result.get("url", "unknown"),
            #     "timestamp": datetime.datetime.now().isoformat()
            # }
            
            # For now, we'll simulate the posting
            logger.info("Simulating Truth Social post (OAuth implementation not activated)")
            return {
                "success": True,
                "platform": "truth_social",
                "post_id": "simulated_truth_social_post_123",
                "timestamp": datetime.now().isoformat()
            }
        except Exception as e:
            logger.error(f"Failed to post to Truth Social: {str(e)}")
            return {"success": False, "platform": "truth_social", "error": str(e)}
            
    def reload_credentials(self):
        """
        Reload credentials from environment variables or global config file.
        Used when credentials are updated programmatically.
        
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Check if global config file exists
            if os.path.exists("data/global_config.json"):
                with open("data/global_config.json", 'r') as f:
                    global_config = json.load(f)
                    
                if "credentials" in global_config:
                    credentials = global_config["credentials"]
                    
                    # Update Twitter credentials if available
                    if "twitter_api_key" in credentials:
                        os.environ["TWITTER-API-KEY"] = credentials["twitter_api_key"]
                    
                    # Update LinkedIn credentials if available
                    if "linkedin_api_key" in credentials:
                        os.environ["LINKEDIN-ACCESS-TOKEN"] = credentials["linkedin_api_key"]
                    
                    # Update Facebook credentials if available
                    if "facebook_api_key" in credentials:
                        os.environ["FACEBOOK-ACCESS-TOKEN"] = credentials["facebook_api_key"]
                        
                    # Update Reddit credentials if available
                    if "reddit_client_id" in credentials:
                        os.environ["REDDIT-CLIENT-ID"] = credentials["reddit_client_id"]
                    if "reddit_client_secret" in credentials:
                        os.environ["REDDIT-CLIENT-SECRET"] = credentials["reddit_client_secret"]
                        
                    # Update Medium credentials if available
                    if "medium_integration_token" in credentials:
                        os.environ["MEDIUM-INTEGRATION-TOKEN"] = credentials["medium_integration_token"]
                    
                    # Update Bluesky credentials if available
                    if "bluesky_identifier" in credentials:
                        os.environ["BLUESKY-IDENTIFIER"] = credentials["bluesky_identifier"]
                    if "bluesky_app_password" in credentials:
                        os.environ["BLUESKY-APP-PASSWORD"] = credentials["bluesky_app_password"]
                    if "bluesky_pds_url" in credentials:
                        os.environ["BLUESKY-PDS-URL"] = credentials["bluesky_pds_url"]
                    
                    # Update Truth Social credentials if available
                    if "truth_social_client_id" in credentials:
                        os.environ["TRUTH-SOCIAL-CLIENT-ID"] = credentials["truth_social_client_id"]
                    if "truth_social_client_secret" in credentials:
                        os.environ["TRUTH-SOCIAL-CLIENT-SECRET"] = credentials["truth_social_client_secret"]
                    if "truth_social_username" in credentials:
                        os.environ["TRUTH-SOCIAL-USERNAME"] = credentials["truth_social_username"]
                    if "truth_social_access_token" in credentials:
                        os.environ["TRUTH-SOCIAL-ACCESS-TOKEN"] = credentials["truth_social_access_token"]
                        
                    # Update DEV.to credentials if available
                    if "devto_api_key" in credentials:
                        os.environ["DEVTO-API-KEY"] = credentials["devto_api_key"]
                    if "devto_organization" in credentials:
                        os.environ["DEVTO-ORGANIZATION"] = credentials["devto_organization"]
            
            # Reinitialize platforms with new credentials
            self._init_twitter()
            self._init_linkedin()
            self._init_facebook()
            self._init_reddit()
            self._init_medium()
            self._init_bluesky()
            self._init_truth_social()
            self._init_devto()
            
            logger.info("Social media credentials reloaded successfully")
            return True
        except Exception as e:
            logger.error(f"Failed to reload social media credentials: {str(e)}")
            return False