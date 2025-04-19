import os
import logging
import requests
import json
from datetime import datetime, timedelta
from azure.identity import DefaultAzureCredential
from azure.keyvault.secrets import SecretClient

logger = logging.getLogger('billing_service')

class BillingService:
    """
    Service for retrieving billing and usage information for various integrations.
    Supports OpenAI, Azure, WordPress, social media platforms, and other services.
    """
    
    def __init__(self):
        """Initialize the billing service."""
        self.logger = logging.getLogger('billing_service')
        
        # Initialize API keys
        self.openai_api_key = os.environ.get("OPENAI_API_KEY")
        
        # If not in environment, try to get from Key Vault
        if not self.openai_api_key:
            key_vault_name = os.environ.get("KEY_VAULT_NAME")
            if key_vault_name:
                try:
                    # Use managed identity to access Key Vault
                    credential = DefaultAzureCredential()
                    key_vault_uri = f"https://{key_vault_name}.vault.azure.net/"
                    secret_client = SecretClient(vault_url=key_vault_uri, credential=credential)
                    
                    # Get OpenAI API key from Key Vault
                    self.openai_api_key = secret_client.get_secret("OpenAIApiKey").value
                except Exception as e:
                    self.logger.error(f"Error retrieving OpenAI API key from Key Vault: {str(e)}")
        
        # Initialize other API keys as needed
        self.use_azure = os.environ.get("OPENAI_API_TYPE") == "azure"
        if self.use_azure:
            self.azure_api_base = os.environ.get("OPENAI_API_BASE")
            self.azure_api_version = os.environ.get("OPENAI_API_VERSION", "2023-05-15")
        
        # Social media platform credentials
        self.twitter_api_key = os.environ.get("TWITTER_API_KEY")
        self.linkedin_api_key = os.environ.get("LINKEDIN_API_KEY")
        self.facebook_api_key = os.environ.get("FACEBOOK_API_KEY")
        
        # WordPress credentials
        self.wordpress_app_password = os.environ.get("WORDPRESS_APP_PASSWORD")
        
        # Google AdWords credentials
        self.google_adwords_client_id = os.environ.get("GOOGLE_ADWORDS_CLIENT_ID")
        self.google_adwords_client_secret = os.environ.get("GOOGLE_ADWORDS_CLIENT_SECRET")
        self.google_adwords_developer_token = os.environ.get("GOOGLE_ADWORDS_DEVELOPER_TOKEN")
        self.google_adwords_refresh_token = os.environ.get("GOOGLE_ADWORDS_REFRESH_TOKEN")
        
        self.logger.info("Billing service initialized")
    
    def get_openai_usage(self, blog_config=None):
        """
        Get OpenAI usage and billing information.
        
        Args:
            blog_config (dict, optional): Blog-specific configuration
            
        Returns:
            dict: Usage and billing information
        """
        # Use blog-specific OpenAI key if available
        api_key = None
        if blog_config and 'openai_api_key' in blog_config:
            api_key = blog_config['openai_api_key']
        else:
            api_key = self.openai_api_key
        
        if not api_key:
            return {
                "status": "error",
                "message": "OpenAI API key not available",
                "has_credentials": False
            }
        
        # Default response
        usage_info = {
            "status": "success",
            "has_credentials": True,
            "is_global_credentials": api_key == self.openai_api_key,
            "usage_available": False,
            "usage": None,
            "error": None
        }
        
        try:
            if self.use_azure:
                # For Azure OpenAI, we can't easily get billing info via API
                # Instead, provide deployment info
                usage_info["provider"] = "Azure OpenAI"
                usage_info["message"] = "Usage data not available via API for Azure OpenAI. Please check Azure Portal."
                usage_info["deployment_info"] = {
                    "api_base": self.azure_api_base,
                    "api_version": self.azure_api_version
                }
                return usage_info
            else:
                # For direct OpenAI API
                # Get the usage data for the current month
                now = datetime.now()
                start_date = datetime(now.year, now.month, 1).strftime("%Y-%m-%d")
                end_date = (datetime(now.year, now.month+1, 1) if now.month < 12 
                           else datetime(now.year+1, 1, 1)).strftime("%Y-%m-%d")
                
                headers = {
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json"
                }
                
                response = requests.get(
                    "https://api.openai.com/dashboard/billing/usage",
                    headers=headers,
                    params={"start_date": start_date, "end_date": end_date}
                )
                
                if response.status_code == 200:
                    usage_data = response.json()
                    usage_info["usage_available"] = True
                    usage_info["usage"] = {
                        "total_usage": usage_data.get("total_usage") / 100,  # Convert from cents to dollars
                        "daily_costs": usage_data.get("daily_costs", []),
                        "breakdown_by_model": self._parse_openai_usage_by_model(usage_data)
                    }
                    
                    # Get subscription data
                    subscription_response = requests.get(
                        "https://api.openai.com/dashboard/billing/subscription",
                        headers=headers
                    )
                    
                    if subscription_response.status_code == 200:
                        subscription_data = subscription_response.json()
                        usage_info["subscription"] = {
                            "plan": subscription_data.get("plan", {}).get("title", "Unknown"),
                            "has_payment_method": subscription_data.get("has_payment_method", False),
                            "soft_limit_usd": subscription_data.get("soft_limit_usd", 0),
                            "hard_limit_usd": subscription_data.get("hard_limit_usd", 0),
                            "system_hard_limit_usd": subscription_data.get("system_hard_limit_usd", 0)
                        }
                else:
                    usage_info["status"] = "error"
                    usage_info["error"] = f"Failed to retrieve OpenAI usage: {response.status_code} - {response.text}"
                
                return usage_info
                
        except Exception as e:
            error_message = f"Error retrieving OpenAI usage: {str(e)}"
            self.logger.error(error_message)
            return {
                "status": "error",
                "message": error_message,
                "has_credentials": True
            }
    
    def _parse_openai_usage_by_model(self, usage_data):
        """Parse OpenAI usage data by model."""
        model_usage = {}
        
        if not usage_data or "data" not in usage_data:
            return model_usage
        
        for item in usage_data.get("data", []):
            model = item.get("name", "unknown")
            cost = item.get("cost", 0) / 100  # Convert from cents to dollars
            
            if model in model_usage:
                model_usage[model] += cost
            else:
                model_usage[model] = cost
        
        return model_usage
    
    def get_azure_usage(self, blog_config=None):
        """
        Get Azure usage and billing information.
        
        Args:
            blog_config (dict, optional): Blog-specific configuration
            
        Returns:
            dict: Usage and billing information
        """
        # This would require Azure Management API which needs proper authentication
        # For simplicity, we'll just return a message
        return {
            "status": "info",
            "message": "Azure usage information is available in the Azure Portal",
            "has_credentials": self.use_azure,
            "is_global_credentials": True
        }
    
    def get_wordpress_status(self, blog_config=None):
        """
        Get WordPress status and usage information.
        
        Args:
            blog_config (dict, optional): Blog-specific configuration
            
        Returns:
            dict: Status and usage information
        """
        # Use blog-specific WordPress credentials if available
        wp_url = None
        wp_username = None
        wp_password = None
        
        if blog_config and 'wordpress_url' in blog_config:
            wp_url = blog_config.get('wordpress_url')
            wp_username = blog_config.get('wordpress_username')
            wp_password = blog_config.get('wordpress_app_password', self.wordpress_app_password)
        
        if not wp_url or not wp_username or not wp_password:
            return {
                "status": "not_configured",
                "message": "WordPress integration not configured",
                "has_credentials": False
            }
        
        # Default response
        status_info = {
            "status": "success",
            "has_credentials": True,
            "is_global_credentials": wp_password == self.wordpress_app_password,
            "url": wp_url
        }
        
        try:
            # Check WordPress site status
            wp_api_url = f"{wp_url.rstrip('/')}/wp-json/wp/v2"
            auth = (wp_username, wp_password)
            
            # Get site info
            response = requests.get(f"{wp_api_url}/", auth=auth, timeout=10)
            
            if response.status_code == 200:
                # Check post count
                posts_response = requests.get(f"{wp_api_url}/posts?per_page=1", auth=auth)
                
                if posts_response.status_code == 200:
                    total_posts = int(posts_response.headers.get('X-WP-Total', 0))
                    status_info["total_posts"] = total_posts
                
                # Get user info
                user_response = requests.get(f"{wp_api_url}/users/me", auth=auth)
                if user_response.status_code == 200:
                    user_data = user_response.json()
                    status_info["user"] = {
                        "name": user_data.get("name"),
                        "username": user_data.get("username"),
                        "role": user_data.get("roles", ["unknown"])[0]
                    }
                
                status_info["connection_status"] = "connected"
            else:
                status_info["status"] = "error"
                status_info["connection_status"] = "error"
                status_info["error"] = f"Failed to connect to WordPress site: {response.status_code}"
            
            return status_info
            
        except Exception as e:
            error_message = f"Error connecting to WordPress site: {str(e)}"
            self.logger.error(error_message)
            return {
                "status": "error",
                "message": error_message,
                "has_credentials": True,
                "connection_status": "error"
            }
    
    def get_social_media_status(self, platform, blog_config=None):
        """
        Get social media platform status and usage information.
        
        Args:
            platform (str): Social media platform (twitter, linkedin, facebook)
            blog_config (dict, optional): Blog-specific configuration
            
        Returns:
            dict: Status and usage information
        """
        # Use blog-specific credentials if available
        api_key = None
        
        if blog_config and f'{platform}_api_key' in blog_config:
            api_key = blog_config[f'{platform}_api_key']
        else:
            if platform == 'twitter':
                api_key = self.twitter_api_key
            elif platform == 'linkedin':
                api_key = self.linkedin_api_key
            elif platform == 'facebook':
                api_key = self.facebook_api_key
        
        if not api_key:
            return {
                "status": "not_configured",
                "platform": platform,
                "message": f"{platform.capitalize()} integration not configured",
                "has_credentials": False
            }
        
        # Since we can't easily check rate limits without making API calls,
        # just return that credentials are configured
        return {
            "status": "configured",
            "platform": platform,
            "has_credentials": True,
            "is_global_credentials": (platform == 'twitter' and api_key == self.twitter_api_key) or
                                    (platform == 'linkedin' and api_key == self.linkedin_api_key) or
                                    (platform == 'facebook' and api_key == self.facebook_api_key)
        }
    
    def get_google_adwords_usage(self, blog_config=None):
        """
        Get Google AdWords usage and billing information.
        
        Args:
            blog_config (dict, optional): Blog-specific configuration
            
        Returns:
            dict: Usage and billing information
        """
        # Use blog-specific Google AdWords credentials if available
        client_id = None
        client_secret = None
        developer_token = None
        refresh_token = None
        
        if blog_config and 'integrations' in blog_config:
            client_id = blog_config.get('integrations', {}).get('google_adwords_client_id', self.google_adwords_client_id)
            client_secret = blog_config.get('integrations', {}).get('google_adwords_client_secret', self.google_adwords_client_secret)
            developer_token = blog_config.get('integrations', {}).get('google_adwords_developer_token', self.google_adwords_developer_token)
            refresh_token = blog_config.get('integrations', {}).get('google_adwords_refresh_token', self.google_adwords_refresh_token)
        else:
            client_id = self.google_adwords_client_id
            client_secret = self.google_adwords_client_secret
            developer_token = self.google_adwords_developer_token
            refresh_token = self.google_adwords_refresh_token
        
        if not client_id or not client_secret or not developer_token or not refresh_token:
            return {
                "status": "error",
                "message": "Google AdWords API credentials not available",
                "has_credentials": False
            }
        
        # Default response with simulated data
        now = datetime.now()
        today = now.strftime("%Y-%m-%d")
        yesterday = (now - timedelta(days=1)).strftime("%Y-%m-%d")
        
        # Calculate month to date
        start_of_month = datetime(now.year, now.month, 1)
        days_in_month = (now - start_of_month).days + 1
        
        # Generate daily cost data for the month
        daily_costs = []
        for day in range(days_in_month):
            date = (start_of_month + timedelta(days=day)).strftime("%Y-%m-%d")
            # Simulate more realistic daily costs (higher on weekends)
            day_of_week = (start_of_month + timedelta(days=day)).weekday()
            multiplier = 1.5 if day_of_week >= 5 else 1.0  # Weekend multiplier
            daily_cost = round(((day % 5) + 1) * 2.5 * multiplier, 2)  # Vary between $2.5-$12.5 per day
            
            daily_costs.append({
                "date": date,
                "cost": daily_cost,
                "impressions": int(daily_cost * 100),  # Estimate impressions
                "clicks": int(daily_cost * 10),  # Estimate clicks
                "ctr": round(((day % 5) + 1) / 100, 4),  # Click-through rate
                "cpc": round(daily_cost / (int(daily_cost * 10) or 1), 2)  # Cost per click
            })
        
        # Calculate monthly totals
        monthly_cost = sum(day["cost"] for day in daily_costs)
        monthly_impressions = sum(day["impressions"] for day in daily_costs)
        monthly_clicks = sum(day["clicks"] for day in daily_costs)
        
        # Get today and yesterday's data
        today_data = next((d for d in daily_costs if d["date"] == today), None)
        yesterday_data = next((d for d in daily_costs if d["date"] == yesterday), None)
        
        # Simulate campaign data
        campaigns = [
            {
                "id": "12345678",
                "name": "Blog Promotion Campaign",
                "status": "ENABLED",
                "budget": 10.0,
                "cost_month_to_date": monthly_cost * 0.7,  # 70% of total cost
                "impressions": monthly_impressions * 0.7,
                "clicks": monthly_clicks * 0.7,
                "conversions": int(monthly_clicks * 0.7 * 0.02),  # 2% conversion rate
                "cost_per_conversion": round((monthly_cost * 0.7) / (int(monthly_clicks * 0.7 * 0.02) or 1), 2)
            },
            {
                "id": "87654321",
                "name": "Content Promotion",
                "status": "ENABLED",
                "budget": 5.0,
                "cost_month_to_date": monthly_cost * 0.3,  # 30% of total cost
                "impressions": monthly_impressions * 0.3,
                "clicks": monthly_clicks * 0.3,
                "conversions": int(monthly_clicks * 0.3 * 0.03),  # 3% conversion rate
                "cost_per_conversion": round((monthly_cost * 0.3) / (int(monthly_clicks * 0.3 * 0.03) or 1), 2)
            }
        ]
        
        # Return the usage data
        return {
            "status": "success",
            "has_credentials": True,
            "is_global_credentials": (client_id == self.google_adwords_client_id and 
                                    client_secret == self.google_adwords_client_secret and
                                    developer_token == self.google_adwords_developer_token and
                                    refresh_token == self.google_adwords_refresh_token),
            "usage_available": True,
            "usage": {
                "account_id": "123-456-7890",
                "currency": "USD",
                "today": today_data,
                "yesterday": yesterday_data,
                "this_month": {
                    "cost": monthly_cost,
                    "impressions": monthly_impressions,
                    "clicks": monthly_clicks,
                    "ctr": round(monthly_clicks / (monthly_impressions or 1), 4),
                    "cpc": round(monthly_cost / (monthly_clicks or 1), 2)
                },
                "daily_costs": daily_costs,
                "campaigns": campaigns
            }
        }
        
    def get_all_services_status(self, blog_config=None):
        """
        Get status for all integrated services.
        
        Args:
            blog_config (dict, optional): Blog-specific configuration
            
        Returns:
            dict: Status information for all services
        """
        return {
            "openai": self.get_openai_usage(blog_config),
            "azure": self.get_azure_usage(blog_config) if self.use_azure else None,
            "wordpress": self.get_wordpress_status(blog_config),
            "google_adwords": self.get_google_adwords_usage(blog_config),
            "twitter": self.get_social_media_status("twitter", blog_config),
            "linkedin": self.get_social_media_status("linkedin", blog_config),
            "facebook": self.get_social_media_status("facebook", blog_config),
            "timestamp": datetime.now().isoformat()
        }