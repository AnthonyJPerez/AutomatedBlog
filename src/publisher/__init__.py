import json
import logging
import azure.functions as func
import datetime
import traceback

from ..shared.config_service import ConfigService
from ..shared.storage_service import StorageService
from ..shared.wordpress_service import WordPressService
from ..shared.logging_service import LoggingService
from ..shared.models import BlogContent, PublishResult

def main(inputBlob: func.InputStream, outputBlob: func.Out[str]) -> None:
    """
    Blob trigger that publishes generated blog content to WordPress.
    This function is triggered when new blog content is created by the processor.
    It publishes the content to the associated WordPress site and tracks results.
    
    Parameters:
        inputBlob: The input blob that triggered this function (blog content)
        outputBlob: Output binding for the publish result
    """
    logger = LoggingService.get_logger("publisher")
    
    # Log function start
    blob_name = inputBlob.name.split('/')[-1]
    logger.info(f'Publishing blog content from blob: {blob_name}')
    
    try:
        # Parse the input blob (blog content)
        content_data = json.loads(inputBlob.read())
        blog_content = BlogContent.from_dict(content_data)
        
        # Initialize services
        config_service = ConfigService()
        storage_service = StorageService()
        wordpress_service = WordPressService()
        
        # Get blog configuration for additional details
        blog_config = config_service.get_blog_config(blog_content.blog_id)
        
        logger.info(f"Publishing content for blog {blog_content.blog_name} with title: {blog_content.title}")
        
        # Step 1: Format content with AdSense ad slots if configured
        if blog_config.adsense_ad_slots and blog_config.adsense_publisher_id:
            blog_content.content = wordpress_service.insert_adsense_ads(
                content=blog_content.content,
                publisher_id=blog_config.adsense_publisher_id,
                ad_slots=blog_config.adsense_ad_slots
            )
        
        # Step 2: Publish content to WordPress
        # Try blog-specific credentials first
        if blog_config.wordpress_url and blog_config.wordpress_username and blog_config.wordpress_app_password:
            logger.info(f"Using blog-specific WordPress credentials for blog {blog_content.blog_id}")
            publish_result = wordpress_service.publish_post(
                wordpress_url=blog_config.wordpress_url,
                username=blog_config.wordpress_username,
                application_password=blog_config.wordpress_app_password,
                title=blog_content.title,
                content=blog_content.content,
                seo_metadata=blog_content.seo_metadata
            )
        else:
            # Fall back to default WordPress credentials from Key Vault
            logger.info(f"Using default WordPress credentials from Key Vault for blog {blog_content.blog_id}")
            try:
                publish_result = wordpress_service.publish_to_default_wordpress(
                    title=blog_content.title,
                    content=blog_content.content,
                    seo_metadata=blog_content.seo_metadata
                )
            except Exception as e:
                logger.error(f"Error using default WordPress credentials: {str(e)}")
                raise Exception(f"No WordPress credentials available. Either configure blog-specific credentials or set up default WordPress in Key Vault. Error: {str(e)}")
        
        # Create result object
        result = PublishResult(
            id=f"result_{blog_content.id}",
            content_id=blog_content.id,
            task_id=blog_content.task_id,
            blog_id=blog_content.blog_id,
            blog_name=blog_content.blog_name,
            title=blog_content.title,
            post_id=publish_result['post_id'],
            post_url=publish_result['post_url'],
            status="published",
            published_at=datetime.datetime.utcnow().isoformat()
        )
        
        # Update blog configuration with last published date
        blog_config.last_published_date = datetime.datetime.utcnow().isoformat()
        blog_config.previous_topics.append(blog_content.title)
        config_service.update_blog_config(blog_config)
        
        # Save result to output blob
        outputBlob.set(json.dumps(result.to_dict()))
        
        logger.info(f"Successfully published content for blog {blog_content.blog_name} to {publish_result['post_url']}")
        
    except Exception as e:
        error_details = traceback.format_exc()
        logger.error(f"Error publishing blog content: {str(e)}\n{error_details}")
        
        # Try to create a failed result if possible
        try:
            if 'blog_content' in locals():
                result = PublishResult(
                    id=f"result_failed_{blog_content.id}",
                    content_id=blog_content.id,
                    task_id=blog_content.task_id,
                    blog_id=blog_content.blog_id,
                    blog_name=blog_content.blog_name,
                    title=blog_content.title if hasattr(blog_content, 'title') else "Unknown",
                    post_id=None,
                    post_url=None,
                    status="failed",
                    error_message=str(e),
                    published_at=datetime.datetime.utcnow().isoformat()
                )
                outputBlob.set(json.dumps(result.to_dict()))
        except Exception as inner_e:
            logger.error(f"Failed to create failure result: {str(inner_e)}")
        
        raise
