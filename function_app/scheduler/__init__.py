"""
Scheduler Function Module
This module contains Azure Functions for scheduling and triggering content generation.

The main functions in this module include:
- TriggerContentGeneration: Timer-triggered function that initiates content generation
- ManualTrigger: HTTP-triggered function for manually starting content generation
"""
import os
import json
import logging
import datetime
from typing import List, Dict, Any, Optional

import azure.functions as func
from azure.identity import DefaultAzureCredential
from azure.keyvault.secrets import SecretClient

# Create a blueprint for Azure Functions v2 programming model
bp = func.Blueprint()

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('scheduler_functions')

# Import shared services
from src.shared.blog_service import BlogService
from src.shared.storage_service import StorageService

# Initialize services
storage_service = StorageService()
blog_service = BlogService(storage_service)


@bp.timer_trigger(schedule="0 */6 * * *", arg_name="timer", 
                 run_on_startup=False, use_monitor=True)
def trigger_content_generation(timer: func.TimerRequest) -> None:
    """
    Timer-triggered function that initiates content generation for blogs
    with automatic scheduling enabled.
    
    This function runs every 6 hours and checks which blogs are due
    for content generation based on their configured schedule.
    
    Args:
        timer (func.TimerRequest): Timer trigger information
    """
    logger.info('Content generation scheduler triggered at %s', 
               datetime.datetime.utcnow().isoformat())
    
    try:
        blogs = blog_service.get_all_blogs()
        for blog in blogs:
            # Skip blogs with automatic scheduling disabled
            if not blog.get('auto_schedule', False):
                logger.info(f"Blog {blog['id']} - Auto scheduling disabled, skipping")
                continue
                
            # Check if it's time to generate content for this blog
            if blog_service.is_due_for_content_generation(blog['id']):
                logger.info(f"Blog {blog['id']} - Due for content generation, queueing")
                # Queue the content generation job
                output_message = {
                    "blog_id": blog['id'],
                    "timestamp": datetime.datetime.utcnow().isoformat(),
                    "trigger_type": "scheduled"
                }
                
                # Store run information
                run_id = storage_service.create_run_folder(blog['id'])
                output_message["run_id"] = run_id
                
                # Create a message for the next step in the pipeline
                queue_message = func.QueueMessage(
                    body=json.dumps(output_message).encode('utf-8')
                )
                
                # Output binding will send this to the content-generation-queue
                func.Queue("content-generation-queue").set(queue_message)
                
                logger.info(f"Blog {blog['id']} - Content generation queued with run ID: {run_id}")
            else:
                logger.info(f"Blog {blog['id']} - Not due for content generation yet")
    except Exception as e:
        logger.error(f"Error in content generation scheduler: {str(e)}", exc_info=True)


@bp.route(route="trigger-blog-content/{blog_id}", auth_level=func.AuthLevel.FUNCTION)
def manual_trigger(req: func.HttpRequest) -> func.HttpResponse:
    """
    HTTP-triggered function for manually starting content generation for a blog.
    
    Args:
        req (func.HttpRequest): The HTTP request object
        
    Returns:
        func.HttpResponse: HTTP response with the run ID if successful
    """
    blog_id = req.route_params.get('blog_id')
    logger.info(f"Manual content generation triggered for blog {blog_id}")
    
    try:
        # Validate that the blog exists
        blog = blog_service.get_blog(blog_id)
        if not blog:
            return func.HttpResponse(
                json.dumps({"error": f"Blog with ID {blog_id} not found"}),
                mimetype="application/json",
                status_code=404
            )
        
        # Create a run folder for this generation
        run_id = storage_service.create_run_folder(blog_id)
        
        # Create a message for the next step in the pipeline
        output_message = {
            "blog_id": blog_id,
            "timestamp": datetime.datetime.utcnow().isoformat(),
            "trigger_type": "manual",
            "run_id": run_id
        }
        
        # Output to the content generation queue
        queue_message = func.QueueMessage(
            body=json.dumps(output_message).encode('utf-8')
        )
        
        func.Queue("content-generation-queue").set(queue_message)
        
        return func.HttpResponse(
            json.dumps({"message": "Content generation queued", "run_id": run_id}),
            mimetype="application/json",
            status_code=200
        )
        
    except Exception as e:
        logger.error(f"Error in manual trigger: {str(e)}", exc_info=True)
        return func.HttpResponse(
            json.dumps({"error": str(e)}),
            mimetype="application/json",
            status_code=500
        )