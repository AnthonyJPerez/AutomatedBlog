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
        
        # Format messages for each platform
        twitter_msg = f"{title}\n\n{excerpt[:100]}... {url}"
        linkedin_msg = f"{excerpt[:500]}... Read more at the link."
        facebook_msg = f"{title}\n\n{excerpt[:250]}... Click the link to read more!"
        
        # Post to Twitter
        twitter_result = self.post_to_twitter(twitter_msg, image_url)
        results["platforms"]["twitter"] = twitter_result
        
        # Post to LinkedIn
        linkedin_result = self.post_to_linkedin(title, linkedin_msg, url, image_url)
        results["platforms"]["linkedin"] = linkedin_result
        
        # Post to Facebook
        facebook_result = self.post_to_facebook(facebook_msg, url, image_url)
        results["platforms"]["facebook"] = facebook_result
        
        # Determine overall success
        all_success = all([
            twitter_result.get("success", False),
            linkedin_result.get("success", False),
            facebook_result.get("success", False)
        ])
        
        results["success"] = all_success
        
        logger.info(f"Content promotion completed for {blog_id}/{run_id} with success={all_success}")
        return results
    
    def get_enabled_platforms(self):
        """
        Get a list of enabled social media platforms.
        
        Returns:
            list: Names of enabled platforms
        """
        return [name for name, config in self.platforms.items() if config.get("enabled", False)]