"""
Publisher function for the blog automation pipeline.
This function is triggered by a queue message and handles publishing content to WordPress.
"""
import logging
import json
import azure.functions as func
from datetime import datetime
import sys
import os
from typing import Dict, Any, Optional

# Add the src directory to the Python path to allow imports from shared modules
sys.path.append(os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'src'))

# Import shared modules
from src.shared.storage_service import StorageService
from src.shared.blog_service import BlogService
from src.shared.wordpress_service import WordPressService
from src.shared.social_media_service import SocialMediaService

# Initialize logging
logger = logging.getLogger('publisher')

# Create a blueprint for the v2 programming model
bp = func.Blueprint()

@bp.queue_trigger(arg_name="msg", 
                queue_name="publish-queue", 
                connection="AzureWebJobsStorage")
@bp.blob_input(arg_name="contentBlob",
               path="generated/{blog_id}/{run_id}/content.json",
               connection="AzureWebJobsStorage")
def publish_content(msg: func.QueueMessage, contentBlob: str) -> None:
    """
    Queue trigger function to publish content to WordPress.
    
    Args:
        msg: The queue message trigger input binding.
        contentBlob: The blob input binding containing the generated content.
    """
    try:
        logger.info(f"Publishing content at: {datetime.utcnow().isoformat()}")
        
        # Parse the message
        message_text = msg.get_body().decode('utf-8')
        message = json.loads(message_text)
        blog_id = message.get('blog_id')
        run_id = message.get('run_id')
        
        if not blog_id or not run_id:
            raise ValueError("Missing required fields in message: blog_id or run_id")
            
        logger.info(f"Publishing content for blog: {blog_id}, run: {run_id}")
        
        # Load content from blob
        if not contentBlob:
            raise ValueError(f"Content not found for blog: {blog_id}, run: {run_id}")
            
        content_data = json.loads(contentBlob)
        
        # Initialize services
        storage_service = StorageService()
        blog_service = BlogService(storage_service)
        
        # Get blog configuration
        blog = blog_service.get_blog_by_id(blog_id)
        if not blog:
            raise ValueError(f"Blog not found: {blog_id}")
            
        # Initialize WordPress service
        wordpress_service = WordPressService(blog.get('wordpress', {}))
        
        # Publish to WordPress
        logger.info(f"Publishing to WordPress: {blog.get('title')}")
        post_id = wordpress_service.publish_post(
            title=content_data['content']['title'],
            content=content_data['content']['html'],
            excerpt=content_data['content']['excerpt'],
            featured_image_url=content_data['content'].get('featured_image_url'),
            categories=content_data['content'].get('categories', []),
            tags=content_data['content'].get('tags', [])
        )
        
        if not post_id:
            raise ValueError("Failed to publish post to WordPress")
            
        logger.info(f"Successfully published post to WordPress with ID: {post_id}")
        
        # Save post information
        publish_result = {
            'blog_id': blog_id,
            'run_id': run_id,
            'post_id': post_id,
            'url': wordpress_service.get_post_url(post_id),
            'timestamp': datetime.utcnow().isoformat()
        }
        
        # Save the publish result
        storage_service.save_json(
            f"generated/{blog_id}/{run_id}/publish_result.json", 
            publish_result
        )
        
        # Queue social media promotion
        if blog.get('social_media', {}).get('enabled', False):
            promote_message = {
                'blog_id': blog_id,
                'run_id': run_id,
                'post_id': post_id,
                'url': publish_result['url'],
                'timestamp': datetime.utcnow().isoformat()
            }
            
            # In a real implementation, you'd queue this message for the promoter function
            # This is a placeholder for now
            logger.info(f"Content published, queuing for social media promotion: {json.dumps(promote_message)}")
        
        # Update run status
        blog_service.update_run_status(
            blog_id, 
            run_id, 
            "published", 
            f"Published to WordPress with ID: {post_id}"
        )
        
    except Exception as e:
        logger.error(f"Error in publisher function: {str(e)}", exc_info=True)
        # Update run status with error
        if blog_id and run_id:
            blog_service = BlogService(StorageService())
            blog_service.update_run_status(blog_id, run_id, "error", f"Publishing error: {str(e)}")
        raise