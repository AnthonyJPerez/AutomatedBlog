"""
Publisher Function Module
This module contains Azure Functions for publishing content to WordPress and other platforms.

The main functions in this module include:
- ContentPublisher: Queue-triggered function that publishes content to WordPress
- ImageUploader: Queue-triggered function that uploads images to WordPress
"""
import os
import json
import logging
import datetime
from typing import List, Dict, Any, Optional

import azure.functions as func

# Create a blueprint for Azure Functions v2 programming model
bp = func.Blueprint()

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('publisher_functions')

# Import shared services
from shared.blog_service import BlogService
from shared.storage_service import StorageService
from shared.wordpress_service import WordPressService
from shared.image_generator import ImageGenerator

# Initialize services
storage_service = StorageService()
blog_service = BlogService(storage_service)
wordpress_service = WordPressService()
image_generator = ImageGenerator()


@bp.queue_trigger(arg_name="msg", queue_name="publish-queue",
                 connection="AzureWebJobsStorage")
def publish_content(msg: func.QueueMessage) -> None:
    """
    Queue-triggered function that publishes content to WordPress.
    
    This function is triggered by messages in the publish-queue,
    taking generated content and publishing it to the configured WordPress site.
    
    Args:
        msg (func.QueueMessage): The queue message containing job information
    """
    logger.info('Content publisher triggered')
    
    try:
        # Parse message
        message_body = msg.get_body().decode('utf-8')
        message_json = json.loads(message_body)
        
        blog_id = message_json.get('blog_id')
        run_id = message_json.get('run_id')
        
        logger.info(f"Publishing content for blog {blog_id}, run {run_id}")
        
        # Get blog configuration
        blog = blog_service.get_blog(blog_id)
        if not blog:
            logger.error(f"Blog with ID {blog_id} not found")
            return
            
        # Get content from run folder
        content = storage_service.get_json(blog_id, run_id, 'content.json')
        if not content:
            logger.error(f"Content not found for blog {blog_id}, run {run_id}")
            return
            
        # Generate featured image
        image_prompt = content.get('featured_image_prompt', f"Featured image for article about {content['title']}")
        featured_image_path = image_generator.generate_image(image_prompt, blog_id, run_id)
        
        # Prepare WordPress credentials
        wp_credentials = blog_service.get_wordpress_credentials(blog_id)
        
        # Upload featured image
        featured_image_url = wordpress_service.upload_media(
            featured_image_path,
            wordpress_url=wp_credentials.get('url'),
            username=wp_credentials.get('username'),
            application_password=wp_credentials.get('password')
        )
        
        # Publish content to WordPress
        post_id = wordpress_service.publish_post(
            title=content['title'],
            content=content['html_content'],
            excerpt=content.get('excerpt', ''),
            featured_image_url=featured_image_url,
            categories=content.get('categories', []),
            tags=content.get('tags', []),
            seo_metadata=content.get('seo_metadata', {})
        )
        
        if post_id:
            logger.info(f"Content published successfully for blog {blog_id}, run {run_id}, post ID: {post_id}")
            
            # Get the public URL of the post
            post_url = wordpress_service.get_post_url(post_id, wp_credentials.get('url'))
            
            # Save publishing results
            results = {
                "published": True,
                "post_id": post_id,
                "post_url": post_url,
                "timestamp": datetime.datetime.utcnow().isoformat()
            }
            storage_service.save_json(blog_id, run_id, 'publish_results.json', results)
            
            # Queue for social media promotion
            promotion_message = {
                "blog_id": blog_id,
                "run_id": run_id,
                "post_id": post_id,
                "post_url": post_url,
                "timestamp": datetime.datetime.utcnow().isoformat()
            }
            promotion_queue_message = func.QueueMessage(
                body=json.dumps(promotion_message).encode('utf-8')
            )
            func.Queue("social-media-queue").set(promotion_queue_message)
        else:
            logger.error(f"Failed to publish content for blog {blog_id}, run {run_id}")
            # Save error results
            results = {
                "published": False,
                "error": "Failed to publish to WordPress",
                "timestamp": datetime.datetime.utcnow().isoformat()
            }
            storage_service.save_json(blog_id, run_id, 'publish_results.json', results)
            
    except Exception as e:
        logger.error(f"Error in content publisher: {str(e)}", exc_info=True)
        # Output to error queue for notification
        try:
            error_message = {
                "blog_id": blog_id,
                "run_id": run_id,
                "error": str(e),
                "stage": "publishing",
                "timestamp": datetime.datetime.utcnow().isoformat()
            }
            error_queue_message = func.QueueMessage(
                body=json.dumps(error_message).encode('utf-8')
            )
            func.Queue("error-notification-queue").set(error_queue_message)
        except Exception as ex:
            logger.error(f"Failed to send error notification: {str(ex)}")


@bp.queue_trigger(arg_name="msg", queue_name="image-upload-queue",
                 connection="AzureWebJobsStorage")
def upload_image(msg: func.QueueMessage) -> None:
    """
    Queue-triggered function that uploads images to WordPress.
    
    This function is used for uploading additional images to WordPress media library,
    outside of the main content publishing flow.
    
    Args:
        msg (func.QueueMessage): The queue message containing job information
    """
    logger.info('Image uploader triggered')
    
    try:
        # Parse message
        message_body = msg.get_body().decode('utf-8')
        message_json = json.loads(message_body)
        
        blog_id = message_json.get('blog_id')
        image_path = message_json.get('image_path')
        
        logger.info(f"Uploading image for blog {blog_id}, path: {image_path}")
        
        # Get blog configuration
        blog = blog_service.get_blog(blog_id)
        if not blog:
            logger.error(f"Blog with ID {blog_id} not found")
            return
            
        # Prepare WordPress credentials
        wp_credentials = blog_service.get_wordpress_credentials(blog_id)
        
        # Upload image
        image_url = wordpress_service.upload_media(
            image_path,
            wordpress_url=wp_credentials.get('url'),
            username=wp_credentials.get('username'),
            application_password=wp_credentials.get('password')
        )
        
        if image_url:
            logger.info(f"Image uploaded successfully for blog {blog_id}, URL: {image_url}")
            
            # Return the image URL in the response
            response_message = {
                "blog_id": blog_id,
                "image_path": image_path,
                "image_url": image_url,
                "success": True,
                "timestamp": datetime.datetime.utcnow().isoformat()
            }
            response_queue_message = func.QueueMessage(
                body=json.dumps(response_message).encode('utf-8')
            )
            func.Queue("image-upload-response-queue").set(response_queue_message)
        else:
            logger.error(f"Failed to upload image for blog {blog_id}")
            # Return error in response
            response_message = {
                "blog_id": blog_id,
                "image_path": image_path,
                "success": False,
                "error": "Failed to upload image",
                "timestamp": datetime.datetime.utcnow().isoformat()
            }
            response_queue_message = func.QueueMessage(
                body=json.dumps(response_message).encode('utf-8')
            )
            func.Queue("image-upload-response-queue").set(response_queue_message)
            
    except Exception as e:
        logger.error(f"Error in image uploader: {str(e)}", exc_info=True)