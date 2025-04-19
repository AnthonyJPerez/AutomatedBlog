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
            
            # Reinitialize platforms with new credentials
            self._init_twitter()
            self._init_linkedin()
            self._init_facebook()
            self._init_reddit()
            self._init_medium()
            
            logger.info("Social media credentials reloaded successfully")
            return True
        except Exception as e:
            logger.error(f"Failed to reload social media credentials: {str(e)}")
            return False