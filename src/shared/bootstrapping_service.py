"""
Bootstrapping Service for Multi-Blog Platform

This service helps quickly set up new blogs with initial configurations and 
common integrations for faster launch and consistent setup.
"""

import json
import os
import logging
import datetime
import uuid
import time
import random
import string
from urllib.parse import urlparse

# Set up logger
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

class BootstrappingService:
    """Service for bootstrapping new blogs with initial configurations"""
    
    def __init__(self, storage_service=None, research_service=None, affiliate_service=None):
        """
        Initialize the Bootstrapping Service
        
        Args:
            storage_service: Service for storing and retrieving data
            research_service: Service for content research
            affiliate_service: Service for affiliate marketing integrations
        """
        self.storage_service = storage_service
        self.research_service = research_service
        self.affiliate_service = affiliate_service
        
        # Templates directory
        self.templates_dir = "data/templates"
        
        # Create necessary directories
        self._setup_directories()
        
        logger.info("Bootstrapping Service initialized")
        
    def _setup_directories(self):
        """Create necessary directories for bootstrapping"""
        if self.storage_service:
            self.storage_service.ensure_local_directory(self.templates_dir)
            self.storage_service.ensure_local_directory(f"{self.templates_dir}/themes")
            self.storage_service.ensure_local_directory(f"{self.templates_dir}/configs")
            self.storage_service.ensure_local_directory(f"{self.templates_dir}/topics")
        else:
            # Fallback to direct directory creation
            os.makedirs(self.templates_dir, exist_ok=True)
            os.makedirs(f"{self.templates_dir}/themes", exist_ok=True)
            os.makedirs(f"{self.templates_dir}/configs", exist_ok=True)
            os.makedirs(f"{self.templates_dir}/topics", exist_ok=True)
    
    def create_blog(self, name, theme, description=None, frequency="weekly", topics=None, template=None):
        """
        Create a new blog with initial configuration
        
        Args:
            name (str): Name of the blog
            theme (str): Theme or niche of the blog
            description (str, optional): Description of the blog
            frequency (str, optional): Content generation frequency
            topics (list, optional): Initial topics for the blog
            template (str, optional): Template to use for initial configuration
            
        Returns:
            dict: Operation result with blog ID and configuration
        """
        try:
            # Generate blog ID
            blog_id = self._generate_blog_id(name)
            
            # Create blog directory structure
            self._create_blog_directories(blog_id)
            
            # Default blog description if not provided
            if not description:
                description = f"A blog about {theme.lower()}"
                
            # Default topics if not provided
            if not topics or not isinstance(topics, list) or len(topics) == 0:
                # If research service is available, generate topic ideas
                if self.research_service and hasattr(self.research_service, 'get_topic_ideas'):
                    topic_result = self.research_service.get_topic_ideas(theme, 5)
                    if topic_result.get('success', False):
                        topics = [t['title'] for t in topic_result.get('topics', [])]
                    else:
                        # Fallback to default topics
                        topics = self._generate_default_topics(theme)
                else:
                    # Fallback to default topics
                    topics = self._generate_default_topics(theme)
            
            # Create initial config
            config = {
                "name": name,
                "theme": theme,
                "description": description,
                "created_at": datetime.datetime.now().isoformat(),
                "updated_at": datetime.datetime.now().isoformat(),
                "is_active": True,
                "frequency": frequency,
                "topics": topics,
                "audience": "general",  # Default audience
                "tone": "informative",  # Default tone
                "seo_keywords": [],     # Will be populated later
                "wordpress": {
                    "connected": False,
                    "url": "",
                    "username": "",
                    "app_password": ""
                },
                "social_media": {
                    "twitter": {
                        "enabled": False,
                        "username": ""
                    },
                    "facebook": {
                        "enabled": False,
                        "page_id": ""
                    },
                    "linkedin": {
                        "enabled": False,
                        "profile_id": ""
                    }
                },
                "analytics": {
                    "google_analytics": {
                        "enabled": False,
                        "tracking_id": ""
                    },
                    "adsense": {
                        "enabled": False,
                        "publisher_id": ""
                    },
                    "search_console": {
                        "enabled": False,
                        "verified": False
                    }
                }
            }
            
            # Apply template if specified
            if template:
                template_config = self._get_template_config(template)
                if template_config:
                    # Merge template with base config
                    for key, value in template_config.items():
                        if key not in ['name', 'created_at', 'updated_at', 'is_active']:
                            config[key] = value
            
            # Create theme definition
            theme_config = self._create_theme_config(theme, description, topics)
            
            # Save configurations
            self._save_blog_config(blog_id, config)
            self._save_blog_theme(blog_id, theme_config)
            
            # Create initial topics file
            topics_config = {
                "topics": topics,
                "suggested_topics": [],
                "trending_topics": [],
                "completed_topics": []
            }
            self._save_blog_topics(blog_id, topics_config)
            
            # Create initial sources and tracking files
            self._create_initial_tracking_files(blog_id, theme)
            
            return {
                "success": True,
                "blog_id": blog_id,
                "config": config,
                "theme": theme_config,
                "message": f"Blog '{name}' created successfully with ID: {blog_id}"
            }
        except Exception as e:
            logger.error(f"Error creating blog: {str(e)}")
            return {
                "success": False,
                "error": f"Error creating blog: {str(e)}"
            }
    
    def bootstrap_from_template(self, blog_id, template_name):
        """
        Bootstrap a blog from a template
        
        Args:
            blog_id (str): ID of the blog to bootstrap
            template_name (str): Name of the template to use
            
        Returns:
            dict: Operation result
        """
        try:
            # Verify blog exists
            blog_path = f"data/blogs/{blog_id}"
            
            if self.storage_service:
                blog_exists = self.storage_service.directory_exists(blog_path)
            else:
                blog_exists = os.path.exists(blog_path)
                
            if not blog_exists:
                return {
                    "success": False,
                    "error": f"Blog not found with ID: {blog_id}"
                }
            
            # Get template config
            template_config = self._get_template_config(template_name)
            if not template_config:
                return {
                    "success": False,
                    "error": f"Template not found: {template_name}"
                }
            
            # Get current blog config
            current_config = self._get_blog_config(blog_id)
            if not current_config:
                return {
                    "success": False,
                    "error": f"Could not load blog config for ID: {blog_id}"
                }
            
            # Apply template to blog config
            for key, value in template_config.items():
                if key not in ['name', 'created_at', 'updated_at', 'is_active', 'wordpress']:
                    current_config[key] = value
                    
            # Update config
            current_config["updated_at"] = datetime.datetime.now().isoformat()
            self._save_blog_config(blog_id, current_config)
            
            # Bootstrap additional assets
            changes = []
            
            # Topic suggestions if available in template
            if 'topic_suggestions' in template_config and isinstance(template_config['topic_suggestions'], list):
                topics_config = self._get_blog_topics(blog_id) or {"topics": [], "suggested_topics": [], "trending_topics": [], "completed_topics": []}
                topics_config["suggested_topics"] = template_config['topic_suggestions']
                self._save_blog_topics(blog_id, topics_config)
                changes.append("topic_suggestions")
            
            # Apply custom theme if available
            if 'theme_config' in template_config and isinstance(template_config['theme_config'], dict):
                theme_config = template_config['theme_config']
                self._save_blog_theme(blog_id, theme_config)
                changes.append("theme_config")
            
            # Apply affiliate network suggestions if available
            if 'affiliate_suggestions' in template_config and isinstance(template_config['affiliate_suggestions'], list) and self.affiliate_service:
                for suggestion in template_config['affiliate_suggestions']:
                    try:
                        if 'network' in suggestion and 'product_url' in suggestion and 'product_name' in suggestion:
                            self.affiliate_service.create_affiliate_link(
                                blog_id=blog_id,
                                product_url=suggestion['product_url'],
                                product_name=suggestion['product_name'],
                                network=suggestion['network']
                            )
                    except Exception as e:
                        logger.warning(f"Could not create affiliate link: {str(e)}")
                
                changes.append("affiliate_links")
            
            return {
                "success": True,
                "blog_id": blog_id,
                "template": template_name,
                "changes": changes,
                "message": f"Blog bootstrapped successfully from template: {template_name}"
            }
        except Exception as e:
            logger.error(f"Error bootstrapping from template: {str(e)}")
            return {
                "success": False,
                "error": f"Error bootstrapping from template: {str(e)}"
            }
    
    def save_as_template(self, blog_id, template_name, description=None, include_theme=True, include_affiliate=True):
        """
        Save a blog configuration as a template
        
        Args:
            blog_id (str): ID of the blog to save as template
            template_name (str): Name for the new template
            description (str, optional): Description of the template
            include_theme (bool, optional): Whether to include theme configuration
            include_affiliate (bool, optional): Whether to include affiliate suggestions
            
        Returns:
            dict: Operation result
        """
        try:
            # Get blog config
            blog_config = self._get_blog_config(blog_id)
            if not blog_config:
                return {
                    "success": False,
                    "error": f"Could not load blog config for ID: {blog_id}"
                }
            
            # Create template config
            template_config = {
                "name": template_name,
                "source_blog": blog_id,
                "description": description or f"Template based on {blog_config.get('name', 'unknown blog')}",
                "created_at": datetime.datetime.now().isoformat(),
                "updated_at": datetime.datetime.now().isoformat()
            }
            
            # Copy relevant fields from blog config
            for key in ['theme', 'audience', 'tone', 'topics', 'seo_keywords', 'frequency', 'analytics', 'social_media']:
                if key in blog_config:
                    template_config[key] = blog_config[key]
            
            # Include theme config if requested
            if include_theme:
                theme_config = self._get_blog_theme(blog_id)
                if theme_config:
                    template_config['theme_config'] = theme_config
            
            # Include affiliate suggestions if requested
            if include_affiliate and self.affiliate_service:
                try:
                    links_result = self.affiliate_service.get_blog_affiliate_links(blog_id)
                    if links_result.get('success') and links_result.get('links'):
                        affiliate_suggestions = []
                        for link in links_result['links']:
                            affiliate_suggestions.append({
                                'network': link['network'],
                                'product_url': link['product_url'],
                                'product_name': link['product_name']
                            })
                        
                        template_config['affiliate_suggestions'] = affiliate_suggestions
                except Exception as e:
                    logger.warning(f"Could not get affiliate links: {str(e)}")
            
            # Get topic suggestions
            topics_config = self._get_blog_topics(blog_id)
            if topics_config and 'suggested_topics' in topics_config:
                template_config['topic_suggestions'] = topics_config['suggested_topics']
            
            # Save template
            template_path = f"{self.templates_dir}/configs/{self._slugify(template_name)}.json"
            
            if self.storage_service:
                self.storage_service.save_local_json(template_path, template_config)
            else:
                with open(template_path, 'w') as f:
                    json.dump(template_config, f, indent=2)
            
            return {
                "success": True,
                "template_name": template_name,
                "template_path": template_path,
                "message": f"Template '{template_name}' created successfully"
            }
        except Exception as e:
            logger.error(f"Error saving as template: {str(e)}")
            return {
                "success": False,
                "error": f"Error saving as template: {str(e)}"
            }
    
    def get_available_templates(self):
        """
        Get list of available templates
        
        Returns:
            dict: Operation result with template list
        """
        try:
            templates_path = f"{self.templates_dir}/configs"
            
            # Get template files
            if self.storage_service:
                template_files = self.storage_service.list_files(templates_path) or []
                template_files = [f for f in template_files if f.endswith(".json")]
            else:
                if os.path.exists(templates_path):
                    template_files = [os.path.join(templates_path, f) for f in os.listdir(templates_path) if f.endswith(".json")]
                else:
                    template_files = []
            
            # Load template data
            templates = []
            for template_file in template_files:
                try:
                    file_name = os.path.basename(template_file)
                    template_id = os.path.splitext(file_name)[0]
                    
                    if self.storage_service:
                        template_data = self.storage_service.get_local_json(template_file)
                    else:
                        with open(template_file, 'r') as f:
                            template_data = json.load(f)
                            
                    templates.append({
                        "id": template_id,
                        "name": template_data.get("name", template_id),
                        "description": template_data.get("description", ""),
                        "created_at": template_data.get("created_at", ""),
                        "theme": template_data.get("theme", ""),
                        "source_blog": template_data.get("source_blog", ""),
                        "features": self._get_template_features(template_data)
                    })
                except Exception as e:
                    logger.warning(f"Could not load template {template_file}: {str(e)}")
            
            # Sort templates by creation date (newest first)
            templates.sort(key=lambda x: x.get("created_at", ""), reverse=True)
            
            return {
                "success": True,
                "templates": templates,
                "count": len(templates)
            }
        except Exception as e:
            logger.error(f"Error getting available templates: {str(e)}")
            return {
                "success": False,
                "error": f"Error getting available templates: {str(e)}"
            }
    
    def setup_initial_wordpress_config(self, blog_id, wordpress_url, username, app_password):
        """
        Set up initial WordPress configuration for a blog
        
        Args:
            blog_id (str): ID of the blog
            wordpress_url (str): URL of the WordPress site
            username (str): WordPress username
            app_password (str): WordPress application password
            
        Returns:
            dict: Operation result
        """
        try:
            # Validate WordPress URL
            if not self._validate_url(wordpress_url):
                return {
                    "success": False,
                    "error": "Invalid WordPress URL"
                }
            
            # Get blog config
            blog_config = self._get_blog_config(blog_id)
            if not blog_config:
                return {
                    "success": False,
                    "error": f"Could not load blog config for ID: {blog_id}"
                }
            
            # Update WordPress configuration
            blog_config["wordpress"] = {
                "connected": True,
                "url": wordpress_url,
                "username": username,
                "app_password": app_password
            }
            
            # Update config
            blog_config["updated_at"] = datetime.datetime.now().isoformat()
            self._save_blog_config(blog_id, blog_config)
            
            return {
                "success": True,
                "blog_id": blog_id,
                "wordpress_url": wordpress_url,
                "message": "WordPress configuration updated successfully"
            }
        except Exception as e:
            logger.error(f"Error setting up WordPress config: {str(e)}")
            return {
                "success": False,
                "error": f"Error setting up WordPress config: {str(e)}"
            }
    
    def setup_initial_analytics(self, blog_id, analytics_type, tracking_id):
        """
        Set up initial analytics configuration for a blog
        
        Args:
            blog_id (str): ID of the blog
            analytics_type (str): Type of analytics (google_analytics, adsense, or search_console)
            tracking_id (str): Tracking ID or publisher ID
            
        Returns:
            dict: Operation result
        """
        try:
            # Get blog config
            blog_config = self._get_blog_config(blog_id)
            if not blog_config:
                return {
                    "success": False,
                    "error": f"Could not load blog config for ID: {blog_id}"
                }
            
            # Ensure analytics section exists
            if "analytics" not in blog_config:
                blog_config["analytics"] = {
                    "google_analytics": {
                        "enabled": False,
                        "tracking_id": ""
                    },
                    "adsense": {
                        "enabled": False,
                        "publisher_id": ""
                    },
                    "search_console": {
                        "enabled": False,
                        "verified": False
                    }
                }
            
            # Update analytics configuration
            if analytics_type == "google_analytics":
                blog_config["analytics"]["google_analytics"] = {
                    "enabled": True,
                    "tracking_id": tracking_id
                }
            elif analytics_type == "adsense":
                blog_config["analytics"]["adsense"] = {
                    "enabled": True,
                    "publisher_id": tracking_id
                }
            elif analytics_type == "search_console":
                blog_config["analytics"]["search_console"] = {
                    "enabled": True,
                    "verified": False  # Will be updated after verification
                }
            else:
                return {
                    "success": False,
                    "error": f"Unsupported analytics type: {analytics_type}"
                }
            
            # Update config
            blog_config["updated_at"] = datetime.datetime.now().isoformat()
            self._save_blog_config(blog_id, blog_config)
            
            return {
                "success": True,
                "blog_id": blog_id,
                "analytics_type": analytics_type,
                "message": f"{analytics_type.replace('_', ' ').title()} configuration updated successfully"
            }
        except Exception as e:
            logger.error(f"Error setting up analytics: {str(e)}")
            return {
                "success": False,
                "error": f"Error setting up analytics: {str(e)}"
            }
    
    def bootstrap_social_media(self, blog_id, platform, username, token=None):
        """
        Bootstrap social media configuration for a blog
        
        Args:
            blog_id (str): ID of the blog
            platform (str): Social media platform (twitter, facebook, linkedin, etc.)
            username (str): Username or profile ID
            token (str, optional): API token or access token
            
        Returns:
            dict: Operation result
        """
        try:
            # Get blog config
            blog_config = self._get_blog_config(blog_id)
            if not blog_config:
                return {
                    "success": False,
                    "error": f"Could not load blog config for ID: {blog_id}"
                }
            
            # Ensure social media section exists
            if "social_media" not in blog_config:
                blog_config["social_media"] = {}
            
            # Validate platform
            if platform not in ["twitter", "facebook", "linkedin", "instagram", "pinterest", "tiktok"]:
                return {
                    "success": False,
                    "error": f"Unsupported social media platform: {platform}"
                }
            
            # Create platform entry if it doesn't exist
            if platform not in blog_config["social_media"]:
                blog_config["social_media"][platform] = {
                    "enabled": False
                }
            
            # Update platform configuration
            blog_config["social_media"][platform]["enabled"] = True
            blog_config["social_media"][platform]["username"] = username
            
            # Store token if provided
            if token:
                blog_config["social_media"][platform]["token"] = token
            
            # Update config
            blog_config["updated_at"] = datetime.datetime.now().isoformat()
            self._save_blog_config(blog_id, blog_config)
            
            return {
                "success": True,
                "blog_id": blog_id,
                "platform": platform,
                "username": username,
                "message": f"{platform.title()} configuration updated successfully"
            }
        except Exception as e:
            logger.error(f"Error bootstrapping social media: {str(e)}")
            return {
                "success": False,
                "error": f"Error bootstrapping social media: {str(e)}"
            }
    
    # ===========================================================================
    # Helper Methods
    # ===========================================================================
    
    def _generate_blog_id(self, name):
        """
        Generate a unique blog ID based on the name
        
        Args:
            name (str): Name of the blog
            
        Returns:
            str: Unique blog ID
        """
        # Convert name to slug
        slug = self._slugify(name)
        
        # Add timestamp for uniqueness
        timestamp = int(time.time())
        
        # Add random string for extra uniqueness
        random_str = ''.join(random.choices(string.ascii_lowercase + string.digits, k=4))
        
        # Combine to create unique ID
        blog_id = f"{slug}-{timestamp}-{random_str}"
        
        return blog_id
    
    def _slugify(self, text):
        """
        Convert text to slug format
        
        Args:
            text (str): Text to convert
            
        Returns:
            str: Slug version of text
        """
        # Convert to lowercase
        slug = text.lower()
        
        # Replace spaces with hyphens
        slug = slug.replace(' ', '-')
        
        # Remove non-alphanumeric characters
        slug = ''.join(c for c in slug if c.isalnum() or c == '-')
        
        # Remove consecutive hyphens
        while '--' in slug:
            slug = slug.replace('--', '-')
        
        # Remove leading and trailing hyphens
        slug = slug.strip('-')
        
        return slug
    
    def _create_blog_directories(self, blog_id):
        """
        Create directory structure for a new blog
        
        Args:
            blog_id (str): ID of the blog
        """
        # Base directory
        base_dir = f"data/blogs/{blog_id}"
        
        # Create directories
        if self.storage_service:
            self.storage_service.ensure_local_directory(base_dir)
            self.storage_service.ensure_local_directory(f"{base_dir}/runs")
            self.storage_service.ensure_local_directory(f"{base_dir}/content")
            self.storage_service.ensure_local_directory(f"{base_dir}/assets")
            self.storage_service.ensure_local_directory(f"{base_dir}/analytics")
            self.storage_service.ensure_local_directory(f"{base_dir}/backlinks")
            self.storage_service.ensure_local_directory(f"{base_dir}/social")
        else:
            # Fallback to direct directory creation
            os.makedirs(base_dir, exist_ok=True)
            os.makedirs(f"{base_dir}/runs", exist_ok=True)
            os.makedirs(f"{base_dir}/content", exist_ok=True)
            os.makedirs(f"{base_dir}/assets", exist_ok=True)
            os.makedirs(f"{base_dir}/analytics", exist_ok=True)
            os.makedirs(f"{base_dir}/backlinks", exist_ok=True)
            os.makedirs(f"{base_dir}/social", exist_ok=True)
    
    def _save_blog_config(self, blog_id, config):
        """
        Save blog configuration
        
        Args:
            blog_id (str): ID of the blog
            config (dict): Blog configuration
        """
        config_path = f"data/blogs/{blog_id}/config.json"
        
        if self.storage_service:
            self.storage_service.save_local_json(config_path, config)
        else:
            with open(config_path, 'w') as f:
                json.dump(config, f, indent=2)
    
    def _save_blog_theme(self, blog_id, theme_config):
        """
        Save blog theme configuration
        
        Args:
            blog_id (str): ID of the blog
            theme_config (dict): Theme configuration
        """
        theme_path = f"data/blogs/{blog_id}/theme.json"
        
        if self.storage_service:
            self.storage_service.save_local_json(theme_path, theme_config)
        else:
            with open(theme_path, 'w') as f:
                json.dump(theme_config, f, indent=2)
    
    def _save_blog_topics(self, blog_id, topics_config):
        """
        Save blog topics configuration
        
        Args:
            blog_id (str): ID of the blog
            topics_config (dict): Topics configuration
        """
        topics_path = f"data/blogs/{blog_id}/topics.json"
        
        if self.storage_service:
            self.storage_service.save_local_json(topics_path, topics_config)
        else:
            with open(topics_path, 'w') as f:
                json.dump(topics_config, f, indent=2)
    
    def _get_blog_config(self, blog_id):
        """
        Get blog configuration
        
        Args:
            blog_id (str): ID of the blog
            
        Returns:
            dict: Blog configuration or None if not found
        """
        config_path = f"data/blogs/{blog_id}/config.json"
        
        try:
            if self.storage_service:
                if self.storage_service.file_exists(config_path):
                    return self.storage_service.get_local_json(config_path)
            else:
                if os.path.exists(config_path):
                    with open(config_path, 'r') as f:
                        return json.load(f)
                        
            return None
        except Exception as e:
            logger.error(f"Error loading blog config: {str(e)}")
            return None
    
    def _get_blog_theme(self, blog_id):
        """
        Get blog theme configuration
        
        Args:
            blog_id (str): ID of the blog
            
        Returns:
            dict: Theme configuration or None if not found
        """
        theme_path = f"data/blogs/{blog_id}/theme.json"
        
        try:
            if self.storage_service:
                if self.storage_service.file_exists(theme_path):
                    return self.storage_service.get_local_json(theme_path)
            else:
                if os.path.exists(theme_path):
                    with open(theme_path, 'r') as f:
                        return json.load(f)
                        
            return None
        except Exception as e:
            logger.error(f"Error loading blog theme: {str(e)}")
            return None
    
    def _get_blog_topics(self, blog_id):
        """
        Get blog topics configuration
        
        Args:
            blog_id (str): ID of the blog
            
        Returns:
            dict: Topics configuration or None if not found
        """
        topics_path = f"data/blogs/{blog_id}/topics.json"
        
        try:
            if self.storage_service:
                if self.storage_service.file_exists(topics_path):
                    return self.storage_service.get_local_json(topics_path)
            else:
                if os.path.exists(topics_path):
                    with open(topics_path, 'r') as f:
                        return json.load(f)
                        
            return None
        except Exception as e:
            logger.error(f"Error loading blog topics: {str(e)}")
            return None
    
    def _get_template_config(self, template_name):
        """
        Get template configuration
        
        Args:
            template_name (str): Name of the template
            
        Returns:
            dict: Template configuration or None if not found
        """
        # Try exact match first
        template_path = f"{self.templates_dir}/configs/{template_name}.json"
        
        try:
            if self.storage_service:
                if self.storage_service.file_exists(template_path):
                    return self.storage_service.get_local_json(template_path)
            else:
                if os.path.exists(template_path):
                    with open(template_path, 'r') as f:
                        return json.load(f)
            
            # Try slug match if exact match not found
            slug = self._slugify(template_name)
            template_path = f"{self.templates_dir}/configs/{slug}.json"
            
            if self.storage_service:
                if self.storage_service.file_exists(template_path):
                    return self.storage_service.get_local_json(template_path)
            else:
                if os.path.exists(template_path):
                    with open(template_path, 'r') as f:
                        return json.load(f)
                        
            return None
        except Exception as e:
            logger.error(f"Error loading template config: {str(e)}")
            return None
    
    def _create_theme_config(self, theme, description, topics):
        """
        Create a theme configuration
        
        Args:
            theme (str): Theme of the blog
            description (str): Description of the blog
            topics (list): List of topics
            
        Returns:
            dict: Theme configuration
        """
        # Create a theme-specific prompt
        theme_description = f"A blog about {theme.lower()}"
        if description:
            theme_description = description
            
        # Create target audience description
        audience_description = f"People interested in {theme.lower()}"
        
        # Create tone description
        tone_description = "Informative, educational, and engaging"
        
        # Create theme configuration
        theme_config = {
            "name": theme,
            "description": theme_description,
            "target_audience": audience_description,
            "tone": tone_description,
            "topics": topics,
            "content_structure": {
                "intro": "Engage the reader with a compelling introduction that presents the problem or question.",
                "body": "Provide comprehensive information with clear sections and examples.",
                "conclusion": "Summarize key points and provide next steps or a call to action."
            },
            "word_count": {
                "min": 800,
                "max": 2000,
                "target": 1200
            },
            "seo": {
                "meta_description_length": 155,
                "title_length": 60,
                "keyword_density": 0.02
            },
            "created_at": datetime.datetime.now().isoformat(),
            "updated_at": datetime.datetime.now().isoformat()
        }
        
        return theme_config
    
    def _create_initial_tracking_files(self, blog_id, theme):
        """
        Create initial tracking files for a blog
        
        Args:
            blog_id (str): ID of the blog
            theme (str): Theme of the blog
        """
        # Create backlinking tracking file
        backlinks_config = {
            "last_scan": None,
            "backlinks": [],
            "competitors": []
        }
        
        backlinks_path = f"data/blogs/{blog_id}/backlinks/config.json"
        
        if self.storage_service:
            self.storage_service.save_local_json(backlinks_path, backlinks_config)
        else:
            # Ensure directory exists
            os.makedirs(os.path.dirname(backlinks_path), exist_ok=True)
            with open(backlinks_path, 'w') as f:
                json.dump(backlinks_config, f, indent=2)
        
        # Create analytics tracking file
        analytics_config = {
            "page_views": [],
            "engagements": [],
            "ad_clicks": [],
            "social_shares": []
        }
        
        analytics_path = f"data/blogs/{blog_id}/analytics/data.json"
        
        if self.storage_service:
            self.storage_service.save_local_json(analytics_path, analytics_config)
        else:
            # Ensure directory exists
            os.makedirs(os.path.dirname(analytics_path), exist_ok=True)
            with open(analytics_path, 'w') as f:
                json.dump(analytics_config, f, indent=2)
    
    def _generate_default_topics(self, theme):
        """
        Generate default topics for a theme
        
        Args:
            theme (str): Theme of the blog
            
        Returns:
            list: List of default topics
        """
        # Some basic topics for common themes
        theme_lower = theme.lower()
        
        # Technology
        if any(t in theme_lower for t in ["tech", "technology", "digital", "software", "programming", "computer"]):
            return [
                "Latest technology trends",
                "Software development best practices",
                "Tech product reviews",
                "Digital transformation strategies",
                "Cybersecurity tips"
            ]
        
        # Food/Cooking
        elif any(t in theme_lower for t in ["food", "cook", "recipe", "culinary", "kitchen"]):
            return [
                "Easy weeknight dinner recipes",
                "Healthy meal prep ideas",
                "Seasonal cooking guides",
                "Kitchen gadget reviews",
                "International cuisine exploration"
            ]
        
        # Health/Fitness
        elif any(t in theme_lower for t in ["health", "fitness", "wellness", "workout", "nutrition"]):
            return [
                "Effective workout routines",
                "Nutrition and diet tips",
                "Mental wellness strategies",
                "Fitness equipment reviews",
                "Health myths debunked"
            ]
        
        # Finance/Money
        elif any(t in theme_lower for t in ["finance", "money", "invest", "budget", "economic"]):
            return [
                "Personal budgeting strategies",
                "Investment basics for beginners",
                "Retirement planning tips",
                "Financial market analysis",
                "Money-saving hacks"
            ]
        
        # Travel
        elif any(t in theme_lower for t in ["travel", "destination", "tourism", "vacation"]):
            return [
                "Hidden travel destinations",
                "Budget travel tips",
                "Travel packing guides",
                "Cultural experiences around the world",
                "Travel photography tips"
            ]
        
        # Generic default topics
        else:
            return [
                f"Getting started with {theme}",
                f"Top 10 tips for {theme}",
                f"The future of {theme}",
                f"Common myths about {theme}",
                f"Resources for learning about {theme}"
            ]
    
    def _get_template_features(self, template_data):
        """
        Get list of features included in a template
        
        Args:
            template_data (dict): Template configuration
            
        Returns:
            list: List of features
        """
        features = []
        
        if "theme_config" in template_data:
            features.append("theme_configuration")
            
        if "topics" in template_data and isinstance(template_data["topics"], list) and len(template_data["topics"]) > 0:
            features.append("topics")
            
        if "topic_suggestions" in template_data and isinstance(template_data["topic_suggestions"], list) and len(template_data["topic_suggestions"]) > 0:
            features.append("topic_suggestions")
            
        if "seo_keywords" in template_data and isinstance(template_data["seo_keywords"], list) and len(template_data["seo_keywords"]) > 0:
            features.append("seo_keywords")
            
        if "affiliate_suggestions" in template_data and isinstance(template_data["affiliate_suggestions"], list) and len(template_data["affiliate_suggestions"]) > 0:
            features.append("affiliate_suggestions")
            
        if "audience" in template_data and template_data["audience"]:
            features.append("audience_targeting")
            
        if "tone" in template_data and template_data["tone"]:
            features.append("content_tone")
            
        if "analytics" in template_data and isinstance(template_data["analytics"], dict):
            features.append("analytics_setup")
            
        if "social_media" in template_data and isinstance(template_data["social_media"], dict):
            features.append("social_media_setup")
            
        return features
    
    def _validate_url(self, url):
        """
        Validate a URL
        
        Args:
            url (str): URL to validate
            
        Returns:
            bool: True if URL is valid, False otherwise
        """
        try:
            result = urlparse(url)
            return all([result.scheme, result.netloc])
        except:
            return False