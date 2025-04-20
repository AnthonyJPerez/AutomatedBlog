"""
Processor Function Module
This module contains Azure Functions for content generation and processing.

The main functions in this module include:
- ContentGenerator: Queue-triggered function that generates content based on topics
- ResearchTopic: Queue-triggered function that researches trending topics for a blog
- ContentOutline: Queue-triggered function that generates content outlines
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
logger = logging.getLogger('processor_functions')

# Import shared services
from shared.blog_service import BlogService
from shared.content_generator import ContentGenerator
from shared.storage_service import StorageService
from shared.research_service import ResearchService
from shared.openai_service import OpenAIService

# Initialize services
storage_service = StorageService()
blog_service = BlogService(storage_service)
openai_service = OpenAIService()
research_service = ResearchService()
content_generator = ContentGenerator(openai_service, storage_service)


@bp.queue_trigger(arg_name="msg", queue_name="content-generation-queue",
                 connection="AzureWebJobsStorage")
def generate_content(msg: func.QueueMessage) -> None:
    """
    Queue-triggered function that generates content for a blog.
    
    This function is triggered by messages in the content-generation-queue
    which are placed there by the scheduler functions. It handles generating
    content by selecting a topic, researching it, and generating the full content.
    
    Args:
        msg (func.QueueMessage): The queue message containing job information
    """
    logger.info('Content generator triggered')
    
    try:
        # Parse message
        message_body = msg.get_body().decode('utf-8')
        message_json = json.loads(message_body)
        
        blog_id = message_json.get('blog_id')
        run_id = message_json.get('run_id')
        trigger_type = message_json.get('trigger_type', 'unknown')
        
        logger.info(f"Generating content for blog {blog_id}, run {run_id}, trigger: {trigger_type}")
        
        # Get blog configuration
        blog = blog_service.get_blog(blog_id)
        if not blog:
            logger.error(f"Blog with ID {blog_id} not found")
            return
            
        # Get blog theme information
        theme = storage_service.get_local_json(blog_id, 'theme.json')
        if not theme:
            logger.warning(f"No theme.json found for blog {blog_id}, using default theme")
            theme = {}
            
        # Select a topic
        topic = blog_service.select_topic(blog_id)
        if not topic:
            logger.error(f"No suitable topic found for blog {blog_id}")
            # Output to error queue for notification
            error_message = {
                "blog_id": blog_id,
                "run_id": run_id,
                "error": "No suitable topic found",
                "timestamp": datetime.datetime.utcnow().isoformat()
            }
            error_queue_message = func.QueueMessage(
                body=json.dumps(error_message).encode('utf-8')
            )
            func.Queue("error-notification-queue").set(error_queue_message)
            return
            
        # Save selected topic to run folder
        storage_service.save_json(blog_id, run_id, 'topic.json', topic)
        
        # Research the topic
        research_data = research_service.research_topic(topic['title'], blog_id=blog_id)
        
        # Save research data to run folder
        storage_service.save_json(blog_id, run_id, 'research.json', research_data)
        
        # Generate outline
        outline = content_generator.generate_outline(topic['title'], research_data, theme)
        
        # Save outline to run folder
        storage_service.save_json(blog_id, run_id, 'outline.json', outline)
        
        # Generate content
        content = content_generator.generate_content(topic['title'], outline, research_data, theme)
        
        # Save content to run folder
        storage_service.save_json(blog_id, run_id, 'content.json', content)
        
        # Queue for publishing
        publish_message = {
            "blog_id": blog_id,
            "run_id": run_id,
            "timestamp": datetime.datetime.utcnow().isoformat()
        }
        publish_queue_message = func.QueueMessage(
            body=json.dumps(publish_message).encode('utf-8')
        )
        func.Queue("publish-queue").set(publish_queue_message)
        
        logger.info(f"Content generation complete for blog {blog_id}, run {run_id}")
        
    except Exception as e:
        logger.error(f"Error in content generation: {str(e)}", exc_info=True)
        # Output to error queue for notification
        try:
            error_message = {
                "blog_id": blog_id,
                "run_id": run_id,
                "error": str(e),
                "timestamp": datetime.datetime.utcnow().isoformat()
            }
            error_queue_message = func.QueueMessage(
                body=json.dumps(error_message).encode('utf-8')
            )
            func.Queue("error-notification-queue").set(error_queue_message)
        except Exception as ex:
            logger.error(f"Failed to send error notification: {str(ex)}")


@bp.queue_trigger(arg_name="msg", queue_name="topic-research-queue",
                 connection="AzureWebJobsStorage")
def research_topics(msg: func.QueueMessage) -> None:
    """
    Queue-triggered function that researches trending topics for a blog.
    
    This function is triggered periodically to update the list of potential
    topics for each blog based on trends and keywords.
    
    Args:
        msg (func.QueueMessage): The queue message containing job information
    """
    logger.info('Topic research triggered')
    
    try:
        # Parse message
        message_body = msg.get_body().decode('utf-8')
        message_json = json.loads(message_body)
        
        blog_id = message_json.get('blog_id')
        logger.info(f"Researching topics for blog {blog_id}")
        
        # Get blog configuration
        blog = blog_service.get_blog(blog_id)
        if not blog:
            logger.error(f"Blog with ID {blog_id} not found")
            return
            
        # Get existing topics
        existing_topics = blog_service.get_topics(blog_id)
        
        # Get blog theme for contextual topic research
        theme = storage_service.get_local_json(blog_id, 'theme.json')
        
        # Research new topics
        new_topics = research_service.find_trending_topics(
            blog_category=blog.get('category', ''),
            keywords=blog.get('keywords', []),
            theme=theme
        )
        
        # Merge with existing topics, avoiding duplicates
        for topic in new_topics:
            if not any(existing_topic['title'] == topic['title'] for existing_topic in existing_topics):
                existing_topics.append(topic)
                
        # Save updated topics
        blog_service.save_topics(blog_id, existing_topics)
        
        logger.info(f"Topic research complete for blog {blog_id}, added {len(new_topics)} new topics")
        
    except Exception as e:
        logger.error(f"Error in topic research: {str(e)}", exc_info=True)