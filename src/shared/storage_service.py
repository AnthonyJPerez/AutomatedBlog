import os
import json
import logging
import traceback
from azure.storage.blob import BlobServiceClient, ContentSettings
from azure.identity import DefaultAzureCredential

class StorageService:
    """
    Service for interacting with Azure Blob Storage.
    Handles saving and retrieving configuration, tasks, content, and results.
    """
    
    def __init__(self):
        self.logger = logging.getLogger('storage_service')
        
        # Get storage connection string from environment variable
        self.connection_string = os.environ.get("AzureWebJobsStorage")
        
        # Container names
        self.config_container = "configuration"
        self.blog_data_container = "blog-data"
        self.results_container = "results"
        
        # Initialize blob service client
        try:
            if self.connection_string:
                self.blob_service_client = BlobServiceClient.from_connection_string(self.connection_string)
            else:
                # Use managed identity if connection string not available
                account_name = os.environ.get("STORAGE_ACCOUNT_NAME")
                if account_name:
                    account_url = f"https://{account_name}.blob.core.windows.net"
                    credential = DefaultAzureCredential()
                    self.blob_service_client = BlobServiceClient(account_url, credential=credential)
                else:
                    self.logger.error("Storage account credentials not available")
                    self.blob_service_client = None
        except Exception as e:
            self.logger.error(f"Error initializing storage service: {str(e)}")
            self.blob_service_client = None
    
    def ensure_containers_exist(self):
        """Ensure that all required containers exist"""
        if not self.blob_service_client:
            self.logger.error("Blob service client not initialized")
            return False
        
        try:
            containers = [self.config_container, self.blog_data_container, self.results_container]
            
            for container_name in containers:
                # Check if container exists
                container_client = self.blob_service_client.get_container_client(container_name)
                
                try:
                    # Try to get container properties
                    container_client.get_container_properties()
                except Exception:
                    # Container doesn't exist, create it
                    self.logger.info(f"Creating container: {container_name}")
                    container_client.create_container()
            
            return True
        except Exception as e:
            self.logger.error(f"Error ensuring containers exist: {str(e)}")
            return False
    
    def save_blob(self, container_name, blob_name, data, content_type="application/json"):
        """
        Save data to a blob in Azure Storage.
        
        Args:
            container_name (str): The name of the container
            blob_name (str): The name of the blob
            data (str/dict): The data to save (string or dictionary that will be converted to JSON)
            content_type (str): The content type of the blob
            
        Returns:
            bool: True if successful, False otherwise
        """
        if not self.blob_service_client:
            self.logger.error("Blob service client not initialized")
            return False
        
        try:
            # Get container client
            container_client = self.blob_service_client.get_container_client(container_name)
            
            # Get blob client
            blob_client = container_client.get_blob_client(blob_name)
            
            # Convert data to JSON string if it's a dictionary
            if isinstance(data, dict):
                data = json.dumps(data, indent=2)
            
            # Set content settings
            content_settings = ContentSettings(content_type=content_type)
            
            # Upload blob
            blob_client.upload_blob(data, overwrite=True, content_settings=content_settings)
            
            self.logger.info(f"Successfully saved blob: {container_name}/{blob_name}")
            return True
        except Exception as e:
            self.logger.error(f"Error saving blob {container_name}/{blob_name}: {str(e)}")
            self.logger.debug(traceback.format_exc())
            return False
    
    def get_blob(self, container_name, blob_name):
        """
        Get data from a blob in Azure Storage.
        
        Args:
            container_name (str): The name of the container
            blob_name (str): The name of the blob
            
        Returns:
            str: The blob data as a string, or None if not found
        """
        if not self.blob_service_client:
            self.logger.error("Blob service client not initialized")
            return None
        
        try:
            # Get container client
            container_client = self.blob_service_client.get_container_client(container_name)
            
            # Get blob client
            blob_client = container_client.get_blob_client(blob_name)
            
            # Download blob
            blob_data = blob_client.download_blob()
            
            # Read data
            data = blob_data.readall()
            
            # Convert from bytes to string
            if isinstance(data, bytes):
                data = data.decode('utf-8')
            
            return data
        except Exception as e:
            self.logger.error(f"Error getting blob {container_name}/{blob_name}: {str(e)}")
            return None
    
    def list_blobs(self, container_name, prefix=None):
        """
        List blobs in a container.
        
        Args:
            container_name (str): The name of the container
            prefix (str): Optional prefix to filter blobs
            
        Returns:
            list: List of blob names, or empty list if error or none found
        """
        if not self.blob_service_client:
            self.logger.error("Blob service client not initialized")
            return []
        
        try:
            # Get container client
            container_client = self.blob_service_client.get_container_client(container_name)
            
            # List blobs
            blob_list = container_client.list_blobs(name_starts_with=prefix)
            
            # Extract names
            blob_names = [blob.name for blob in blob_list]
            
            return blob_names
        except Exception as e:
            self.logger.error(f"Error listing blobs in {container_name}: {str(e)}")
            return []
    
    def delete_blob(self, container_name, blob_name):
        """
        Delete a blob from Azure Storage.
        
        Args:
            container_name (str): The name of the container
            blob_name (str): The name of the blob
            
        Returns:
            bool: True if successful, False otherwise
        """
        if not self.blob_service_client:
            self.logger.error("Blob service client not initialized")
            return False
        
        try:
            # Get container client
            container_client = self.blob_service_client.get_container_client(container_name)
            
            # Get blob client
            blob_client = container_client.get_blob_client(blob_name)
            
            # Delete blob
            blob_client.delete_blob()
            
            self.logger.info(f"Successfully deleted blob: {container_name}/{blob_name}")
            return True
        except Exception as e:
            self.logger.error(f"Error deleting blob {container_name}/{blob_name}: {str(e)}")
            return False
    
    def save_blog_config(self, blog_config):
        """
        Save a blog configuration to blob storage.
        
        Args:
            blog_config (BlogConfig or dict): The blog configuration to save
            
        Returns:
            bool: True if successful, False otherwise
        """
        if hasattr(blog_config, 'to_dict'):
            config_data = blog_config.to_dict()
        else:
            config_data = blog_config
            
        blob_name = f"blog_{config_data['blog_id']}.json"
        return self.save_blob(self.config_container, blob_name, config_data)
    
    def get_blog_config(self, blog_id):
        """
        Get a blog configuration from blob storage.
        
        Args:
            blog_id (str): The ID of the blog
            
        Returns:
            dict: The blog configuration, or None if not found
        """
        blob_name = f"blog_{blog_id}.json"
        data = self.get_blob(self.config_container, blob_name)
        
        if data:
            try:
                return json.loads(data)
            except json.JSONDecodeError:
                self.logger.error(f"Error decoding JSON for blog config {blog_id}")
                return None
        
        return None
    
    def save_blog_task(self, task):
        """
        Save a blog task to blob storage.
        
        Args:
            task (BlogTask or dict): The blog task to save
            
        Returns:
            bool: True if successful, False otherwise
        """
        if hasattr(task, 'to_dict'):
            task_data = task.to_dict()
        else:
            task_data = task
            
        blob_name = f"task_{task_data['id']}.json"
        return self.save_blob(self.blog_data_container, blob_name, task_data)
    
    def get_blog_task(self, task_id):
        """
        Get a blog task from blob storage.
        
        Args:
            task_id (str): The ID of the task
            
        Returns:
            dict: The blog task, or None if not found
        """
        blob_name = f"task_{task_id}.json"
        data = self.get_blob(self.blog_data_container, blob_name)
        
        if data:
            try:
                return json.loads(data)
            except json.JSONDecodeError:
                self.logger.error(f"Error decoding JSON for task {task_id}")
                return None
        
        return None
