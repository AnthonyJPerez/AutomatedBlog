"""
Content processor function for the blog automation pipeline.
This function is triggered by a queue message and handles content generation.
"""
import logging
import json
import azure.functions as func
from datetime import datetime
import sys
import os

# Add the src directory to the Python path to allow imports from shared modules
sys.path.append(os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'src'))

# Import shared modules
from src.shared.storage_service import StorageService
from src.shared.openai_service import OpenAIService
from src.shared.blog_service import BlogService
from src.shared.content_generator import ContentGenerator

# Initialize logging
logger = logging.getLogger('processor')

# Create a blueprint for the v2 programming model
bp = func.Blueprint()

@bp.queue_trigger(arg_name="msg", 
                queue_name="content-queue", 
                connection="AzureWebJobsStorage")
@bp.blob_output(arg_name="outputBlob",
                path="generated/{blog_id}/{run_id}/content.json",
                connection="AzureWebJobsStorage")
def process_content(msg: func.QueueMessage, outputBlob: func.Out[str]) -> None:
    """
    Queue trigger function to process content generation.
    
    Args:
        msg: The queue message trigger input binding.
        outputBlob: The blob output binding for storing the generated content.
    """
    try:
        logger.info(f"Processing content generation at: {datetime.utcnow().isoformat()}")
        
        # Parse the message
        message_text = msg.get_body().decode('utf-8')
        message = json.loads(message_text)
        blog_id = message.get('blog_id')
        run_id = message.get('run_id')
        
        if not blog_id or not run_id:
            raise ValueError("Missing required fields in message: blog_id or run_id")
            
        logger.info(f"Processing content for blog: {blog_id}, run: {run_id}")
        
        # Initialize services
        storage_service = StorageService()
        openai_service = OpenAIService()
        blog_service = BlogService(storage_service)
        content_generator = ContentGenerator(openai_service, storage_service)
        
        # Get blog configuration
        blog = blog_service.get_blog_by_id(blog_id)
        if not blog:
            raise ValueError(f"Blog not found: {blog_id}")
            
        # Get topic to generate content for
        topic = blog_service.get_next_topic(blog_id)
        if not topic:
            logger.warning(f"No topics available for blog: {blog_id}")
            blog_service.update_run_status(blog_id, run_id, "completed", "No topics available")
            return
            
        # Generate content
        logger.info(f"Generating content for topic: {topic['title']}")
        content = content_generator.generate_content(blog, topic)
        
        # Save the generated content
        result = {
            'blog_id': blog_id,
            'run_id': run_id,
            'topic': topic,
            'content': content,
            'timestamp': datetime.utcnow().isoformat()
        }
        
        # Write to blob storage
        outputBlob.set(json.dumps(result, indent=2))
        
        # Queue publishing process
        publish_message = {
            'blog_id': blog_id,
            'run_id': run_id,
            'timestamp': datetime.utcnow().isoformat()
        }
        
        # In a real implementation, you'd queue this message for the publisher function
        # This is a placeholder for now
        logger.info(f"Content generation complete, queuing for publishing: {json.dumps(publish_message)}")
        
        # Update run status
        blog_service.update_run_status(blog_id, run_id, "content_generated", f"Content generated for {topic['title']}")
        
    except Exception as e:
        logger.error(f"Error in processor function: {str(e)}", exc_info=True)
        # Update run status with error
        if blog_id and run_id:
            blog_service = BlogService(StorageService())
            blog_service.update_run_status(blog_id, run_id, "error", f"Error: {str(e)}")
        raise