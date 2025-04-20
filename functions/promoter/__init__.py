"""
Social media promoter function for the blog automation pipeline.
This function is triggered by a queue message and handles promoting content on social media.
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
from src.shared.social_media_service import SocialMediaService

# Initialize logging
logger = logging.getLogger('promoter')

# Create a blueprint for the v2 programming model
bp = func.Blueprint()

@bp.queue_trigger(arg_name="msg", 
                queue_name="social-queue", 
                connection="AzureWebJobsStorage")
@bp.blob_input(arg_name="contentBlob",
               path="generated/{blog_id}/{run_id}/content.json",
               connection="AzureWebJobsStorage")
def promote_content(msg: func.QueueMessage, contentBlob: str) -> None:
    """
    Queue trigger function to promote content on social media.
    
    Args:
        msg: The queue message trigger input binding.
        contentBlob: The blob input binding containing the generated content.
    """
    try:
        logger.info(f"Promoting content at: {datetime.utcnow().isoformat()}")
        
        # Parse the message
        message_text = msg.get_body().decode('utf-8')
        message = json.loads(message_text)
        blog_id = message.get('blog_id')
        run_id = message.get('run_id')
        post_id = message.get('post_id')
        post_url = message.get('url')
        
        if not all([blog_id, run_id, post_id, post_url]):
            raise ValueError("Missing required fields in message")
            
        logger.info(f"Promoting content for blog: {blog_id}, run: {run_id}, post: {post_id}")
        
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
            
        # Initialize social media service
        social_media_service = SocialMediaService()
        
        # Get social media platforms to publish to
        social_config = blog.get('social_media', {})
        platforms = social_config.get('platforms', [])
        
        if not platforms:
            logger.info(f"No social media platforms configured for blog: {blog_id}")
            blog_service.update_run_status(blog_id, run_id, "completed", "No social media platforms configured")
            return
            
        # Prepare promotion content
        title = content_data['content']['title']
        excerpt = content_data['content']['excerpt']
        featured_image_url = content_data['content'].get('featured_image_url')
        
        # Promote to each platform
        promotion_results = {}
        for platform in platforms:
            platform_name = platform.get('name')
            if not platform_name:
                continue
                
            logger.info(f"Promoting to platform: {platform_name}")
            
            try:
                result = social_media_service.post_to_platform(
                    platform=platform_name,
                    title=title,
                    excerpt=excerpt,
                    url=post_url,
                    image_url=featured_image_url,
                    platform_config=platform
                )
                
                promotion_results[platform_name] = {
                    'success': bool(result),
                    'post_id': result if result else None,
                    'timestamp': datetime.utcnow().isoformat()
                }
                
                logger.info(f"Promoted to {platform_name}: {result}")
                
            except Exception as platform_error:
                logger.error(f"Error promoting to {platform_name}: {str(platform_error)}")
                promotion_results[platform_name] = {
                    'success': False,
                    'error': str(platform_error),
                    'timestamp': datetime.utcnow().isoformat()
                }
        
        # Save the promotion results
        promotion_data = {
            'blog_id': blog_id,
            'run_id': run_id,
            'post_id': post_id,
            'url': post_url,
            'platforms': promotion_results,
            'timestamp': datetime.utcnow().isoformat()
        }
        
        storage_service.save_json(
            f"generated/{blog_id}/{run_id}/promotion_results.json", 
            promotion_data
        )
        
        # Update run status
        blog_service.update_run_status(
            blog_id, 
            run_id, 
            "completed", 
            f"Content published and promoted to {len(promotion_results)} platforms"
        )
        
    except Exception as e:
        logger.error(f"Error in promoter function: {str(e)}", exc_info=True)
        # Update run status with error
        if blog_id and run_id:
            blog_service = BlogService(StorageService())
            blog_service.update_run_status(blog_id, run_id, "error", f"Promotion error: {str(e)}")
        raise