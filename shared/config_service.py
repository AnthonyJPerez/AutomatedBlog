import os
import json
import logging
from .storage_service import StorageService
from .models import BlogConfig

class ConfigService:
    """
    Service for managing configuration of the blog automation system.
    Handles reading and writing blog configurations.
    """
    
    def __init__(self):
        self.logger = logging.getLogger('config_service')
        self.storage_service = StorageService()
        
        # Ensure required containers exist
        self.storage_service.ensure_containers_exist()
    
    def get_blog_config(self, blog_id):
        """
        Get configuration for a specific blog.
        
        Args:
            blog_id (str): The ID of the blog
            
        Returns:
            BlogConfig: The blog configuration object, or None if not found
        """
        # Get blog config from storage
        config_data = self.storage_service.get_blog_config(blog_id)
        
        if config_data:
            try:
                return BlogConfig.from_dict(config_data)
            except Exception as e:
                self.logger.error(f"Error parsing blog config for {blog_id}: {str(e)}")
                return None
        
        self.logger.warning(f"Blog config for {blog_id} not found")
        return None
    
    def get_all_blog_configs(self):
        """
        Get configurations for all blogs.
        
        Returns:
            list: List of BlogConfig objects
        """
        # List all blog config blobs
        blob_names = self.storage_service.list_blobs("configuration", prefix="blog_")
        
        configs = []
        
        for blob_name in blob_names:
            try:
                # Extract blog ID from blob name
                blog_id = blob_name.replace("blog_", "").replace(".json", "")
                
                # Get the blog config
                config = self.get_blog_config(blog_id)
                
                if config:
                    configs.append(config)
            except Exception as e:
                self.logger.error(f"Error loading blog config from {blob_name}: {str(e)}")
        
        return configs
    
    def create_blog_config(self, config):
        """
        Create a new blog configuration.
        
        Args:
            config (BlogConfig): The blog configuration to create
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Save the blog config to storage
            result = self.storage_service.save_blog_config(config)
            
            if result:
                self.logger.info(f"Created new blog config for {config.blog_name} with ID {config.blog_id}")
            else:
                self.logger.error(f"Failed to create blog config for {config.blog_name}")
            
            return result
        except Exception as e:
            self.logger.error(f"Error creating blog config: {str(e)}")
            return False
    
    def update_blog_config(self, config):
        """
        Update an existing blog configuration.
        
        Args:
            config (BlogConfig): The blog configuration to update
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Check if the blog config exists
            existing_config = self.get_blog_config(config.blog_id)
            
            if not existing_config:
                self.logger.error(f"Blog config with ID {config.blog_id} not found for update")
                return False
            
            # Save the updated blog config to storage
            result = self.storage_service.save_blog_config(config)
            
            if result:
                self.logger.info(f"Updated blog config for {config.blog_name} with ID {config.blog_id}")
            else:
                self.logger.error(f"Failed to update blog config for {config.blog_name}")
            
            return result
        except Exception as e:
            self.logger.error(f"Error updating blog config: {str(e)}")
            return False
    
    def delete_blog_config(self, blog_id):
        """
        Delete a blog configuration.
        
        Args:
            blog_id (str): The ID of the blog to delete
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Check if the blog config exists
            existing_config = self.get_blog_config(blog_id)
            
            if not existing_config:
                self.logger.error(f"Blog config with ID {blog_id} not found for deletion")
                return False
            
            # Delete the blog config from storage
            blob_name = f"blog_{blog_id}.json"
            result = self.storage_service.delete_blob("configuration", blob_name)
            
            if result:
                self.logger.info(f"Deleted blog config with ID {blog_id}")
            else:
                self.logger.error(f"Failed to delete blog config with ID {blog_id}")
            
            return result
        except Exception as e:
            self.logger.error(f"Error deleting blog config: {str(e)}")
            return False
    
    def create_default_blog_config(self, blog_name, theme, wordpress_url, wordpress_username, wordpress_app_password):
        """
        Create a new blog configuration with default settings.
        
        Args:
            blog_name (str): The name of the blog
            theme (str): The theme of the blog
            wordpress_url (str): The URL of the WordPress site
            wordpress_username (str): The WordPress username
            wordpress_app_password (str): The WordPress application password
            
        Returns:
            BlogConfig: The created blog configuration, or None if failed
        """
        import uuid
        import datetime
        
        try:
            # Generate a unique blog ID
            blog_id = str(uuid.uuid4())
            
            # Create new blog config with default settings
            config = BlogConfig(
                blog_id=blog_id,
                blog_name=blog_name,
                theme=theme,
                tone="professional",
                target_audience="general",
                content_types=["article", "listicle"],
                publishing_frequency="weekly",
                wordpress_url=wordpress_url,
                wordpress_username=wordpress_username,
                wordpress_app_password=wordpress_app_password,
                adsense_publisher_id="",
                adsense_ad_slots=[],
                region="US",
                previous_topics=[],
                needs_domain=False,
                created_at=datetime.datetime.utcnow().isoformat(),
                last_published_date=None
            )
            
            # Save the new config
            success = self.create_blog_config(config)
            
            if success:
                return config
            else:
                return None
        except Exception as e:
            self.logger.error(f"Error creating default blog config: {str(e)}")
            return None
