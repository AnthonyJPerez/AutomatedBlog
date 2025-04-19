import datetime
import json
import logging
import azure.functions as func

from ..shared.config_service import ConfigService
from ..shared.storage_service import StorageService
from ..shared.logging_service import LoggingService
from ..shared.models import BlogTask

def main(mytimer: func.TimerRequest, outputBlob: func.Out[str]) -> None:
    """
    Timer trigger that schedules blog content generation tasks.
    This function runs on a schedule and creates new blog tasks based on configuration.
    
    Parameters:
        mytimer: The timer trigger that invoked this function
        outputBlob: Output binding to the blog-data container
    """
    logger = LoggingService.get_logger("scheduler")
    
    # Log function start
    logger.info(f'Scheduler function triggered at: {datetime.datetime.utcnow()}')
    
    if mytimer.past_due:
        logger.warning('The timer is past due!')
    
    try:
        # Initialize services
        config_service = ConfigService()
        storage_service = StorageService()
        
        # Get all blog configurations
        blog_configs = config_service.get_all_blog_configs()
        logger.info(f"Found {len(blog_configs)} blog configurations to process")
        
        tasks_created = 0
        
        # Process each blog configuration and create tasks
        for blog_config in blog_configs:
            # Check if it's time to generate new content for this blog
            if should_generate_content(blog_config):
                # Create a new blog task
                task = create_blog_task(blog_config)
                
                # Save task to blob storage
                task_blob_name = f"{task.id}.json"
                outputBlob.set(json.dumps(task.to_dict()))
                
                logger.info(f"Created task {task.id} for blog {blog_config.blog_name}")
                tasks_created += 1
            else:
                logger.info(f"Skipping blog {blog_config.blog_name} - not scheduled for content generation now")
        
        logger.info(f"Scheduler completed successfully. Created {tasks_created} new tasks.")
        
    except Exception as e:
        logger.error(f"Error in scheduler function: {str(e)}", exc_info=True)
        raise

def should_generate_content(blog_config):
    """Determine if it's time to generate new content for this blog based on schedule"""
    now = datetime.datetime.utcnow()
    
    # Parse the frequency from the blog configuration
    frequency = blog_config.publishing_frequency.lower()
    last_published = blog_config.last_published_date
    
    if not last_published:
        return True  # No content has been published yet
    
    last_published = datetime.datetime.fromisoformat(last_published)
    days_since_last_publish = (now - last_published).days
    
    # Check if it's time to publish based on frequency
    if frequency == 'daily':
        return days_since_last_publish >= 1
    elif frequency == 'weekly':
        return days_since_last_publish >= 7
    elif frequency == 'biweekly':
        return days_since_last_publish >= 14
    elif frequency == 'monthly':
        return days_since_last_publish >= 30
    else:
        # Default to weekly if frequency is unknown
        return days_since_last_publish >= 7

def create_blog_task(blog_config):
    """Create a new blog task from a blog configuration"""
    now = datetime.datetime.utcnow()
    task_id = f"task_{blog_config.blog_id}_{now.strftime('%Y%m%d%H%M%S')}"
    
    # Create task object
    task = BlogTask(
        id=task_id,
        blog_id=blog_config.blog_id,
        blog_name=blog_config.blog_name,
        status="pending",
        created_at=now.isoformat(),
        updated_at=now.isoformat(),
        theme=blog_config.theme,
        tone=blog_config.tone,
        target_audience=blog_config.target_audience,
        content_types=blog_config.content_types,
        wordpress_url=blog_config.wordpress_url,
        wordpress_username=blog_config.wordpress_username,
        adsense_ad_slots=blog_config.adsense_ad_slots
    )
    
    return task
