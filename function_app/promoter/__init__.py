"""
Promoter Function Module
This module contains Azure Functions for promoting content on social media platforms.

The main functions in this module include:
- SocialMediaPromoter: Queue-triggered function that shares content on social media platforms
- ScheduledPromotion: Timer-triggered function for scheduled re-sharing of content
"""
import os
import json
import logging
import datetime
import random
from typing import List, Dict, Any, Optional

import azure.functions as func

# Create a blueprint for Azure Functions v2 programming model
bp = func.Blueprint()

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('promoter_functions')

# Import shared services
from src.shared.blog_service import BlogService
from src.shared.storage_service import StorageService
from src.shared.social_media_service import SocialMediaService

# Initialize services
storage_service = StorageService()
blog_service = BlogService(storage_service)
social_media_service = SocialMediaService()


@bp.queue_trigger(arg_name="msg", queue_name="social-media-queue",
                 connection="AzureWebJobsStorage")
def promote_on_social_media(msg: func.QueueMessage) -> None:
    """
    Queue-triggered function that promotes content on social media platforms.
    
    This function is triggered by messages in the social-media-queue,
    sharing newly published content across configured social media platforms.
    
    Args:
        msg (func.QueueMessage): The queue message containing job information
    """
    logger.info('Social media promoter triggered')
    
    try:
        # Parse message
        message_body = msg.get_body().decode('utf-8')
        message_json = json.loads(message_body)
        
        blog_id = message_json.get('blog_id')
        run_id = message_json.get('run_id')
        post_url = message_json.get('post_url')
        
        logger.info(f"Promoting content for blog {blog_id}, run {run_id}")
        
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
            
        # Get social media configuration
        social_media_config = storage_service.get_local_json(blog_id, 'social_media.json')
        if not social_media_config:
            logger.warning(f"No social media configuration found for blog {blog_id}, using defaults")
            social_media_config = {
                "platforms": ["twitter", "facebook", "linkedin"],
                "message_templates": {
                    "twitter": "New post: {title} {url} #{tags}",
                    "facebook": "Check out our new post: {title}\n\n{excerpt}\n\n{url}",
                    "linkedin": "New post: {title}\n\n{excerpt}\n\n{url}"
                }
            }
            
        # Process each configured platform
        promotion_results = []
        for platform in social_media_config.get('platforms', []):
            try:
                # Skip disabled platforms
                if not blog.get(f'social_media_{platform}_enabled', True):
                    logger.info(f"Platform {platform} disabled for blog {blog_id}, skipping")
                    continue
                    
                # Generate message from template
                template = social_media_config.get('message_templates', {}).get(
                    platform, "New post: {title} {url}"
                )
                
                # Format tags for the platform
                hashtags = ""
                if content.get('tags'):
                    if platform == "twitter":
                        hashtags = " ".join([f"#{tag.replace(' ', '')}" for tag in content.get('tags', [])])
                    else:
                        hashtags = ", ".join(content.get('tags', []))
                        
                # Format the message with content data
                message = template.format(
                    title=content['title'],
                    excerpt=content.get('excerpt', ''),
                    url=post_url,
                    tags=hashtags
                )
                
                # Post to the platform
                result = social_media_service.post_to_platform(
                    platform=platform,
                    message=message,
                    url=post_url,
                    title=content['title'],
                    image_path=storage_service.get_featured_image_path(blog_id, run_id),
                    blog_id=blog_id
                )
                
                if result.get('success'):
                    logger.info(f"Posted to {platform} successfully for blog {blog_id}")
                    promotion_results.append({
                        "platform": platform,
                        "success": True,
                        "post_id": result.get('post_id'),
                        "post_url": result.get('post_url'),
                        "timestamp": datetime.datetime.utcnow().isoformat()
                    })
                else:
                    logger.error(f"Failed to post to {platform} for blog {blog_id}: {result.get('error')}")
                    promotion_results.append({
                        "platform": platform,
                        "success": False,
                        "error": result.get('error'),
                        "timestamp": datetime.datetime.utcnow().isoformat()
                    })
                    
            except Exception as e:
                logger.error(f"Error posting to {platform}: {str(e)}", exc_info=True)
                promotion_results.append({
                    "platform": platform,
                    "success": False,
                    "error": str(e),
                    "timestamp": datetime.datetime.utcnow().isoformat()
                })
                
        # Save promotion results
        storage_service.save_json(blog_id, run_id, 'promotion_results.json', promotion_results)
        
        logger.info(f"Social media promotion complete for blog {blog_id}, run {run_id}")
        
    except Exception as e:
        logger.error(f"Error in social media promoter: {str(e)}", exc_info=True)
        # Output to error queue for notification
        try:
            error_message = {
                "blog_id": blog_id,
                "run_id": run_id,
                "error": str(e),
                "stage": "promotion",
                "timestamp": datetime.datetime.utcnow().isoformat()
            }
            error_queue_message = func.QueueMessage(
                body=json.dumps(error_message).encode('utf-8')
            )
            func.Queue("error-notification-queue").set(error_queue_message)
        except Exception as ex:
            logger.error(f"Failed to send error notification: {str(ex)}")


@bp.timer_trigger(schedule="0 10 * * *", arg_name="timer", 
                 run_on_startup=False, use_monitor=True)
def scheduled_promotion(timer: func.TimerRequest) -> None:
    """
    Timer-triggered function that schedules re-sharing of older content.
    
    This function runs daily at 10am UTC and selects older content
    to re-share on social media platforms for increased visibility.
    
    Args:
        timer (func.TimerRequest): Timer trigger information
    """
    logger.info('Scheduled content promotion triggered at %s', 
               datetime.datetime.utcnow().isoformat())
    
    try:
        # Get all blogs
        blogs = blog_service.get_all_blogs()
        
        for blog in blogs:
            # Skip blogs with scheduled promotion disabled
            if not blog.get('scheduled_promotion_enabled', False):
                logger.info(f"Blog {blog['id']} - Scheduled promotion disabled, skipping")
                continue
                
            logger.info(f"Processing scheduled promotion for blog {blog['id']}")
            
            # Get social media configuration
            social_media_config = storage_service.get_local_json(blog['id'], 'social_media.json')
            if not social_media_config:
                logger.warning(f"No social media configuration found for blog {blog['id']}, skipping")
                continue
                
            # Get published content runs, oldest first (for re-sharing)
            published_runs = blog_service.get_published_content_runs(blog['id'])
            
            # Skip if no published content
            if not published_runs:
                logger.info(f"No published content found for blog {blog['id']}, skipping")
                continue
                
            # Filter out recently re-shared content
            # Avoid re-sharing content that was shared in the last 30 days
            thirty_days_ago = datetime.datetime.utcnow() - datetime.timedelta(days=30)
            eligible_runs = []
            
            for run in published_runs:
                # Check if this run has been re-shared recently
                promotion_history = storage_service.get_json(
                    blog['id'], 
                    run['run_id'], 
                    'reshare_history.json'
                )
                
                # If no history or last share was more than 30 days ago
                if not promotion_history or not promotion_history.get('last_reshare'):
                    eligible_runs.append(run)
                else:
                    # Check if the last reshare was more than 30 days ago
                    last_reshare = datetime.datetime.fromisoformat(promotion_history['last_reshare'])
                    if last_reshare < thirty_days_ago:
                        eligible_runs.append(run)
            
            # Skip if no eligible content to re-share
            if not eligible_runs:
                logger.info(f"No eligible content to re-share for blog {blog['id']}, skipping")
                continue
                
            # Select a random run to re-share
            selected_run = random.choice(eligible_runs)
            
            # Get content and publish information
            content = storage_service.get_json(blog['id'], selected_run['run_id'], 'content.json')
            publish_results = storage_service.get_json(blog['id'], selected_run['run_id'], 'publish_results.json')
            
            if not content or not publish_results:
                logger.warning(f"Missing content or publish results for run {selected_run['run_id']}, skipping")
                continue
                
            post_url = publish_results.get('post_url')
            if not post_url:
                logger.warning(f"No post URL found for run {selected_run['run_id']}, skipping")
                continue
                
            # Queue for social media promotion
            promotion_message = {
                "blog_id": blog['id'],
                "run_id": selected_run['run_id'],
                "post_url": post_url,
                "reshare": True,
                "timestamp": datetime.datetime.utcnow().isoformat()
            }
            promotion_queue_message = func.QueueMessage(
                body=json.dumps(promotion_message).encode('utf-8')
            )
            func.Queue("social-media-queue").set(promotion_queue_message)
            
            # Update reshare history
            reshare_history = storage_service.get_json(blog['id'], selected_run['run_id'], 'reshare_history.json') or {
                "reshare_count": 0,
                "reshares": []
            }
            
            reshare_history['reshare_count'] = reshare_history.get('reshare_count', 0) + 1
            reshare_history['last_reshare'] = datetime.datetime.utcnow().isoformat()
            reshare_history['reshares'].append({
                "timestamp": datetime.datetime.utcnow().isoformat(),
                "trigger": "scheduled"
            })
            
            storage_service.save_json(blog['id'], selected_run['run_id'], 'reshare_history.json', reshare_history)
            
            logger.info(f"Scheduled promotion queued for blog {blog['id']}, run {selected_run['run_id']}")
            
    except Exception as e:
        logger.error(f"Error in scheduled promotion: {str(e)}", exc_info=True)