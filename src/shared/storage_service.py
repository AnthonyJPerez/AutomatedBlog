import os
import logging
import json
import time
import datetime
from pathlib import Path
from azure.storage.blob import BlobServiceClient, BlobClient, ContainerClient, ContentSettings
from azure.identity import DefaultAzureCredential
from azure.core.exceptions import ResourceNotFoundError, ResourceExistsError

class StorageService:
    """
    Service for managing Azure Storage operations.
    Handles reading and writing blog data in blob storage.
    """
    
    def __init__(self):
        """Initialize the storage service with Azure Storage account credentials."""
        # Configure logger
        self.logger = logging.getLogger('storage_service')
        
        # Try to get connection string from environment variable
        self.connection_string = os.environ.get("AzureWebJobsStorage")
        
        # If not in environment, try to construct from account name and key
        if not self.connection_string:
            account_name = os.environ.get("STORAGE_ACCOUNT_NAME")
            account_key = os.environ.get("STORAGE_ACCOUNT_KEY")
            
            if account_name and account_key:
                self.connection_string = f"DefaultEndpointsProtocol=https;AccountName={account_name};AccountKey={account_key};EndpointSuffix=core.windows.net"
        
        # If still no connection string, try to use Managed Identity
        self.use_managed_identity = False
        if not self.connection_string:
            account_name = os.environ.get("STORAGE_ACCOUNT_NAME")
            if account_name:
                self.use_managed_identity = True
                self.account_name = account_name
                self.logger.info(f"Using Managed Identity for Azure Storage account: {account_name}")
        
        # Initialize blob client if credentials are available
        self.blob_service_client = None
        self.use_local_storage = False
        
        if self.connection_string:
            try:
                self.blob_service_client = BlobServiceClient.from_connection_string(self.connection_string)
                self.logger.info("Successfully initialized Azure Storage with connection string")
            except Exception as e:
                self.logger.error(f"Error initializing Azure Storage with connection string: {str(e)}")
                self.use_local_storage = True
        elif self.use_managed_identity:
            try:
                credential = DefaultAzureCredential()
                account_url = f"https://{self.account_name}.blob.core.windows.net"
                self.blob_service_client = BlobServiceClient(account_url=account_url, credential=credential)
                self.logger.info("Successfully initialized Azure Storage with Managed Identity")
            except Exception as e:
                self.logger.error(f"Error initializing Azure Storage with Managed Identity: {str(e)}")
                self.use_local_storage = True
        else:
            self.logger.warning("Azure Storage credentials not available, using local file system")
            self.use_local_storage = True
        
        # Create local storage directories if using local storage
        if self.use_local_storage:
            self._create_local_storage_dirs()
    
    def _create_local_storage_dirs(self):
        """Create local directories for blob storage emulation."""
        try:
            # Create root dirs
            Path('./data').mkdir(exist_ok=True)
            Path('./data/generated').mkdir(exist_ok=True)
            Path('./data/integrations').mkdir(exist_ok=True)
            
            self.logger.info("Local storage directories created")
        except Exception as e:
            self.logger.error(f"Error creating local storage directories: {str(e)}")
    
    def get_blob(self, container_name, blob_name):
        """
        Get a blob from storage.
        
        Args:
            container_name (str): Name of the container
            blob_name (str): Name of the blob
            
        Returns:
            str: Blob content as string, or None if not found
        """
        try:
            if self.use_local_storage:
                # Handle container and blob paths for local storage
                if container_name:
                    file_path = f"./data/{container_name}/{blob_name}"
                else:
                    file_path = f"./data/{blob_name}"
                
                # Ensure directory exists
                os.makedirs(os.path.dirname(file_path), exist_ok=True)
                
                if os.path.exists(file_path):
                    with open(file_path, 'r') as file:
                        return file.read()
                return None
            else:
                # Get the container client
                if container_name:
                    container_client = self.blob_service_client.get_container_client(container_name)
                else:
                    container_client = self.blob_service_client.get_container_client("")
                
                # Get the blob client
                blob_client = container_client.get_blob_client(blob_name)
                
                # Check if blob exists
                if not blob_client.exists():
                    return None
                
                # Download the blob
                download_stream = blob_client.download_blob()
                return download_stream.readall().decode('utf-8')
        
        except ResourceNotFoundError:
            self.logger.warning(f"Blob not found: {container_name}/{blob_name}")
            return None
        except Exception as e:
            self.logger.error(f"Error getting blob {container_name}/{blob_name}: {str(e)}")
            return None
    
    def set_blob(self, container_name, blob_name, content, content_type=None):
        """
        Create or update a blob in storage.
        
        Args:
            container_name (str): Name of the container
            blob_name (str): Name of the blob
            content (str): Content to store in the blob
            content_type (str): Content type for the blob
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            if self.use_local_storage:
                # Handle container and blob paths for local storage
                if container_name:
                    file_path = f"./data/{container_name}/{blob_name}"
                else:
                    file_path = f"./data/{blob_name}"
                
                # Ensure directory exists
                os.makedirs(os.path.dirname(file_path), exist_ok=True)
                
                with open(file_path, 'w') as file:
                    file.write(content)
                return True
            else:
                # Get the container client
                if container_name:
                    container_client = self.blob_service_client.get_container_client(container_name)
                else:
                    container_client = self.blob_service_client.get_container_client("")
                
                # Ensure container exists
                try:
                    container_client.create_container()
                except ResourceExistsError:
                    pass
                
                # Set content settings if provided
                content_settings = None
                if content_type:
                    content_settings = ContentSettings(content_type=content_type)
                
                # Upload the blob
                blob_client = container_client.get_blob_client(blob_name)
                blob_client.upload_blob(content, overwrite=True, content_settings=content_settings)
                return True
        
        except Exception as e:
            self.logger.error(f"Error setting blob {container_name}/{blob_name}: {str(e)}")
            return False
    
    def delete_blob(self, container_name, blob_name):
        """
        Delete a blob from storage.
        
        Args:
            container_name (str): Name of the container
            blob_name (str): Name of the blob
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            if self.use_local_storage:
                # Handle container and blob paths for local storage
                if container_name:
                    file_path = f"./data/{container_name}/{blob_name}"
                else:
                    file_path = f"./data/{blob_name}"
                
                if os.path.exists(file_path):
                    os.remove(file_path)
                return True
            else:
                # Get the container client
                if container_name:
                    container_client = self.blob_service_client.get_container_client(container_name)
                else:
                    container_client = self.blob_service_client.get_container_client("")
                
                # Delete the blob
                blob_client = container_client.get_blob_client(blob_name)
                blob_client.delete_blob()
                return True
        
        except ResourceNotFoundError:
            # If the blob doesn't exist, consider it a success
            return True
        except Exception as e:
            self.logger.error(f"Error deleting blob {container_name}/{blob_name}: {str(e)}")
            return False
    
    def blob_exists(self, container_name, blob_name):
        """
        Check if a blob exists in storage.
        
        Args:
            container_name (str): Name of the container
            blob_name (str): Name of the blob
            
        Returns:
            bool: True if the blob exists, False otherwise
        """
        try:
            if self.use_local_storage:
                # Handle container and blob paths for local storage
                if container_name:
                    file_path = f"./data/{container_name}/{blob_name}"
                else:
                    file_path = f"./data/{blob_name}"
                
                return os.path.exists(file_path)
            else:
                # Get the container client
                if container_name:
                    container_client = self.blob_service_client.get_container_client(container_name)
                else:
                    container_client = self.blob_service_client.get_container_client("")
                
                # Check if blob exists
                blob_client = container_client.get_blob_client(blob_name)
                return blob_client.exists()
        
        except Exception as e:
            self.logger.error(f"Error checking if blob exists {container_name}/{blob_name}: {str(e)}")
            return False
    
    def list_blobs(self, container_name, prefix=None):
        """
        List blobs in a container with an optional prefix.
        
        Args:
            container_name (str): Name of the container
            prefix (str): Prefix to filter blobs
            
        Returns:
            list: List of blob names
        """
        try:
            if self.use_local_storage:
                # Handle container path for local storage
                if container_name:
                    dir_path = f"./data/{container_name}"
                else:
                    dir_path = "./data"
                
                # Get all files in the directory and subdirectories
                all_files = []
                for root, dirs, files in os.walk(dir_path):
                    for file in files:
                        # Get relative path from dir_path
                        file_path = os.path.join(root, file)
                        rel_path = os.path.relpath(file_path, dir_path)
                        
                        # Check prefix if provided
                        if prefix is None or rel_path.startswith(prefix):
                            all_files.append(rel_path)
                
                return all_files
            else:
                # Get the container client
                if container_name:
                    container_client = self.blob_service_client.get_container_client(container_name)
                else:
                    container_client = self.blob_service_client.get_container_client("")
                
                # List blobs with prefix
                blobs = container_client.list_blobs(name_starts_with=prefix)
                return [blob.name for blob in blobs]
        
        except Exception as e:
            self.logger.error(f"Error listing blobs in {container_name} with prefix {prefix}: {str(e)}")
            return []
    
    def get_run_id(self):
        """
        Generate a new run ID for a content generation run.
        
        Returns:
            str: A unique run ID based on timestamp
        """
        timestamp = datetime.datetime.utcnow().strftime('%Y%m%d_%H%M%S')
        return f"{timestamp}_{int(time.time() * 1000) % 1000:03d}"