"""
Scheduler function for the blog automation pipeline.
This function runs on a timed trigger and initiates the content generation process.
"""
import logging
import json
import azure.functions as func
from azure.identity import DefaultAzureCredential
from azure.keyvault.secrets import SecretClient
from datetime import datetime
import sys
import os

# Add the src directory to the Python path to allow imports from shared modules
sys.path.append(os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'src'))

# Import shared modules
from src.shared.storage_service import StorageService
from src.shared.blog_service import BlogService

# Initialize logging
logger = logging.getLogger('scheduler')

# Create a blueprint for the v2 programming model
bp = func.Blueprint()

@bp.timer_trigger(schedule="0 */6 * * *", arg_name="timer", run_on_startup=False)
def run_scheduler(timer: func.TimerRequest) -> None:
    """
    Timer trigger function to start the blog generation process.
    Runs every 6 hours by default.
    
    Args:
        timer: The timer trigger input binding.
    """
    logger.info(f"Scheduler function triggered at: {datetime.utcnow().isoformat()}")
    
    try:
        # Initialize services
        storage_service = StorageService()
        blog_service = BlogService(storage_service)
        
        # Get list of blogs to process
        blogs = blog_service.get_all_blogs()
        logger.info(f"Found {len(blogs)} blogs to process")
        
        for blog in blogs:
            if blog_service.should_generate_content(blog['id']):
                logger.info(f"Starting content generation for blog: {blog['id']}")
                
                # Create a new run record
                run_id = blog_service.create_run(blog['id'])
                
                # Queue the content generation process
                message = {
                    'blog_id': blog['id'],
                    'run_id': run_id,
                    'timestamp': datetime.utcnow().isoformat()
                }
                
                # In a real implementation, you'd queue this message for the next function
                # This is a placeholder for now
                logger.info(f"Queued content generation: {json.dumps(message)}")
            else:
                logger.info(f"Skipping blog {blog['id']} - no generation needed at this time")
                
        logger.info("Scheduler run completed successfully")
    except Exception as e:
        logger.error(f"Error in scheduler function: {str(e)}", exc_info=True)
        raise