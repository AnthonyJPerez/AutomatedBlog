import os
import json
import logging
import time
import requests
from azure.identity import DefaultAzureCredential
from azure.keyvault.secrets import SecretClient

class GoDaddyService:
    """
    Service for suggesting domain names using the GoDaddy API.
    Provides domain availability checking and suggestions based on blog themes.
    """
    
    def __init__(self):
        self.logger = logging.getLogger('godaddy_service')
        
        # Get Key Vault name from environment variable
        key_vault_name = os.environ.get("KEY_VAULT_NAME")
        
        if key_vault_name:
            # Use managed identity to access Key Vault
            credential = DefaultAzureCredential()
            key_vault_uri = f"https://{key_vault_name}.vault.azure.net/"
            secret_client = SecretClient(vault_url=key_vault_uri, credential=credential)
            
            # Get GoDaddy API keys from Key Vault
            try:
                self.api_key = secret_client.get_secret("GoDaddyApiKey").value
                self.api_secret = secret_client.get_secret("GoDaddyApiSecret").value
            except Exception as e:
                self.logger.error(f"Error retrieving GoDaddy secrets from Key Vault: {str(e)}")
                # Fall back to environment variables
                self.api_key = os.environ.get("GODADDY_API_KEY")
                self.api_secret = os.environ.get("GODADDY_API_SECRET")
        else:
            # Use environment variables
            self.api_key = os.environ.get("GODADDY_API_KEY")
            self.api_secret = os.environ.get("GODADDY_API_SECRET")
        
        # GoDaddy API base URL
        self.base_url = "https://api.godaddy.com/v1"
        
        # Headers for API requests
        self.headers = {
            "Authorization": f"sso-key {self.api_key}:{self.api_secret}",
            "Content-Type": "application/json"
        }
    
    def suggest_domains(self, theme, topic, blog_name, tlds=None, max_suggestions=5):
        """
        Suggest domain names based on blog theme and topic.
        
        Args:
            theme (str): The blog theme
            topic (str): The blog topic
            blog_name (str): The name of the blog
            tlds (list): List of TLDs to check (default: ['.com', '.net', '.org', '.io', '.blog'])
            max_suggestions (int): Maximum number of domain suggestions to return
            
        Returns:
            list: List of domain suggestions with availability and pricing
        """
        self.logger.info(f"Generating domain suggestions for blog: {blog_name}, theme: {theme}, topic: {topic}")
        
        if not self.api_key or not self.api_secret:
            self.logger.warning("GoDaddy API credentials not available. Using fallback domain suggestions.")
            return self._generate_fallback_suggestions(blog_name, theme, topic)
        
        # Default TLDs if not provided
        if tlds is None:
            tlds = ['.com', '.net', '.org', '.io', '.blog']
        
        # Generate domain name ideas
        domain_ideas = self._generate_domain_ideas(blog_name, theme, topic)
        
        suggestions = []
        
        # Check availability for each domain idea with each TLD
        for domain in domain_ideas:
            for tld in tlds:
                # Skip if we already have enough suggestions
                if len(suggestions) >= max_suggestions:
                    break
                
                domain_name = f"{domain}{tld}"
                
                try:
                    # Check domain availability
                    availability_result = self._check_domain_availability(domain_name)
                    
                    if availability_result:
                        suggestions.append(availability_result)
                except Exception as e:
                    self.logger.error(f"Error checking availability for {domain_name}: {str(e)}")
            
            # Break if we have enough suggestions
            if len(suggestions) >= max_suggestions:
                break
        
        # If we don't have enough suggestions, try the suggestion API
        if len(suggestions) < max_suggestions:
            try:
                # Use the first domain idea as the seed for suggestions
                seed_domain = domain_ideas[0] if domain_ideas else blog_name.lower().replace(' ', '')
                additional_suggestions = self._get_domain_suggestions(seed_domain, max_suggestions - len(suggestions))
                
                if additional_suggestions:
                    suggestions.extend(additional_suggestions)
            except Exception as e:
                self.logger.error(f"Error getting domain suggestions: {str(e)}")
        
        # Limit to max_suggestions
        suggestions = suggestions[:max_suggestions]
        
        # If we still don't have enough suggestions, add fallback suggestions
        if len(suggestions) < max_suggestions:
            fallback_count = max_suggestions - len(suggestions)
            fallback_suggestions = self._generate_fallback_suggestions(blog_name, theme, topic)[:fallback_count]
            suggestions.extend(fallback_suggestions)
        
        self.logger.info(f"Generated {len(suggestions)} domain suggestions")
        return suggestions
    
    def _check_domain_availability(self, domain_name):
        """Check availability of a specific domain name"""
        endpoint = f"{self.base_url}/domains/available"
        
        max_retries = 3
        for attempt in range(max_retries):
            try:
                response = requests.get(
                    endpoint,
                    headers=self.headers,
                    params={"domain": domain_name, "checkType": "FULL"}
                )
                response.raise_for_status()
                
                data = response.json()
                
                return {
                    'domain': domain_name,
                    'available': data.get('available', False),
                    'price': data.get('price', 0) / 1000000 if 'price' in data else None,  # Convert from micros
                    'currency': data.get('currency', 'USD')
                }
                
            except Exception as e:
                self.logger.error(f"Error checking domain availability (attempt {attempt+1}/{max_retries}): {str(e)}")
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)  # Exponential backoff
        
        # Fallback if all attempts fail
        return None
    
    def _get_domain_suggestions(self, domain, limit=5):
        """Get domain suggestions from GoDaddy API"""
        endpoint = f"{self.base_url}/domains/suggest"
        
        max_retries = 3
        for attempt in range(max_retries):
            try:
                response = requests.get(
                    endpoint,
                    headers=self.headers,
                    params={"query": domain, "limit": limit}
                )
                response.raise_for_status()
                
                suggestions = response.json()
                
                # Format the response
                formatted_suggestions = []
                for suggestion in suggestions:
                    formatted_suggestions.append({
                        'domain': suggestion.get('domain', ''),
                        'available': True,  # These suggestions should all be available
                        'price': suggestion.get('price', 0) / 1000000 if 'price' in suggestion else None,  # Convert from micros
                        'currency': suggestion.get('currency', 'USD')
                    })
                
                return formatted_suggestions
                
            except Exception as e:
                self.logger.error(f"Error getting domain suggestions (attempt {attempt+1}/{max_retries}): {str(e)}")
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)  # Exponential backoff
        
        # Fallback if all attempts fail
        return []
    
    def _generate_domain_ideas(self, blog_name, theme, topic):
        """Generate domain name ideas based on blog name, theme, and topic"""
        # Clean up inputs for domain names
        blog_name_clean = blog_name.lower().replace(' ', '')
        theme_clean = theme.lower().replace(' ', '')
        
        # Extract keywords from topic
        topic_words = topic.lower().split()
        topic_clean = ''.join(word for word in topic_words if len(word) > 3)[:10]  # Use longer words, limit length
        
        # Generate multiple combinations
        ideas = [
            blog_name_clean,
            f"{blog_name_clean}{theme_clean}",
            f"{theme_clean}{blog_name_clean}",
            f"{blog_name_clean}blog",
            f"{theme_clean}blog",
            f"my{theme_clean}",
            f"best{theme_clean}",
            f"{theme_clean}hub",
            f"{theme_clean}zone",
            f"{blog_name_clean}{topic_clean}",
            f"{topic_clean}{blog_name_clean}",
            f"{topic_clean}blog"
        ]
        
        # Remove duplicates and ensure clean domain name format
        unique_ideas = []
        for idea in ideas:
            # Ensure only alphanumeric characters and hyphens
            cleaned_idea = ''.join(c if c.isalnum() else '-' for c in idea)
            
            # Remove consecutive hyphens
            while '--' in cleaned_idea:
                cleaned_idea = cleaned_idea.replace('--', '-')
            
            # Remove starting and ending hyphens
            cleaned_idea = cleaned_idea.strip('-')
            
            # Add to unique ideas if not already present
            if cleaned_idea and cleaned_idea not in unique_ideas:
                unique_ideas.append(cleaned_idea)
        
        return unique_ideas
    
    def _generate_fallback_suggestions(self, blog_name, theme, topic):
        """Generate fallback domain suggestions when API is unavailable"""
        # Generate domain ideas
        domain_ideas = self._generate_domain_ideas(blog_name, theme, topic)
        
        # Default TLDs
        tlds = ['.com', '.net', '.org', '.io', '.blog']
        
        # Generate fallback suggestions
        fallback_suggestions = []
        
        for domain in domain_ideas[:3]:  # Limit to first 3 ideas
            for tld in tlds[:2]:  # Limit to first 2 TLDs
                fallback_suggestions.append({
                    'domain': f"{domain}{tld}",
                    'available': None,  # Unknown availability
                    'price': None,
                    'currency': 'USD',
                    'is_fallback': True
                })
        
        return fallback_suggestions
