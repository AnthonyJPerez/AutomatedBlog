import json
import logging
import azure.functions as func
import datetime
import traceback

from ..shared.config_service import ConfigService
from ..shared.storage_service import StorageService
from ..shared.research_service import ResearchService
from ..shared.openai_service import OpenAIService
from ..shared.logging_service import LoggingService
from ..shared.models import BlogTask, BlogContent

def main(inputBlob: func.InputStream, outputBlob: func.Out[str]) -> None:
    """
    Blob trigger that processes a blog task.
    This function is triggered when a new blog task is created in the blog-data container.
    It performs research, generates content, and prepares it for publishing.
    
    Parameters:
        inputBlob: The input blob that triggered this function (blog task)
        outputBlob: Output binding for the generated content
    """
    logger = LoggingService.get_logger("processor")
    
    # Log function start
    blob_name = inputBlob.name.split('/')[-1]
    logger.info(f'Processing blog task from blob: {blob_name}')
    
    try:
        # Parse the input blob (blog task)
        task_data = json.loads(inputBlob.read())
        task = BlogTask.from_dict(task_data)
        
        # Update task status
        task.status = "processing"
        task.updated_at = datetime.datetime.utcnow().isoformat()
        
        # Initialize services
        config_service = ConfigService()
        storage_service = StorageService()
        research_service = ResearchService()
        openai_service = OpenAIService()
        
        # Get blog configuration for additional details
        blog_config = config_service.get_blog_config(task.blog_id)
        
        logger.info(f"Processing task {task.id} for blog {task.blog_name}")
        
        # Step 1: Research topics based on blog theme and trending topics
        logger.info(f"Researching topics for {task.blog_name} with theme {task.theme}")
        research_results = research_service.research_topics(
            theme=task.theme,
            target_audience=task.target_audience,
            region=blog_config.region
        )
        
        # Step 2: Select the best topic based on trends and relevance
        selected_topic = research_service.select_best_topic(research_results, blog_config.previous_topics)
        logger.info(f"Selected topic: {selected_topic['title']}")
        
        # Step 3: Generate outline for the content
        outline = openai_service.generate_outline(
            topic=selected_topic['title'],
            theme=task.theme,
            tone=task.tone,
            target_audience=task.target_audience
        )
        
        # Step 4: Generate the full content based on the outline
        content_type = task.content_types[0] if task.content_types else "article"
        content = openai_service.generate_content(
            topic=selected_topic['title'],
            outline=outline,
            theme=task.theme,
            tone=task.tone,
            target_audience=task.target_audience,
            content_type=content_type
        )
        
        # Step 5: Generate SEO metadata
        seo_metadata = openai_service.generate_seo_metadata(
            title=selected_topic['title'],
            content=content
        )
        
        # Step 6: Suggest domain name if needed
        domain_suggestions = []
        if blog_config.needs_domain:
            from ..shared.godaddy_service import GoDaddyService
            godaddy_service = GoDaddyService()
            domain_suggestions = godaddy_service.suggest_domains(
                theme=task.theme,
                topic=selected_topic['title'],
                blog_name=task.blog_name
            )
        
        # Create BlogContent object with the generated content
        blog_content = BlogContent(
            id=f"content_{task.id}",
            task_id=task.id,
            blog_id=task.blog_id,
            blog_name=task.blog_name,
            title=selected_topic['title'],
            content=content,
            outline=outline,
            seo_metadata=seo_metadata,
            research_data=research_results,
            domain_suggestions=domain_suggestions,
            created_at=datetime.datetime.utcnow().isoformat(),
            status="ready_to_publish"
        )
        
        # Update task status
        task.status = "content_generated"
        task.updated_at = datetime.datetime.utcnow().isoformat()
        
        # Save updated task
        storage_service.save_blog_task(task)
        
        # Save blog content to output blob
        outputBlob.set(json.dumps(blog_content.to_dict()))
        
        logger.info(f"Successfully processed task {task.id} and generated content")
        
    except Exception as e:
        error_details = traceback.format_exc()
        logger.error(f"Error processing blog task: {str(e)}\n{error_details}")
        
        # Try to update task status to failed if possible
        try:
            if 'task' in locals():
                task.status = "failed"
                task.error_message = str(e)
                task.updated_at = datetime.datetime.utcnow().isoformat()
                storage_service = StorageService()
                storage_service.save_blog_task(task)
        except Exception as inner_e:
            logger.error(f"Failed to update task status: {str(inner_e)}")
        
        raise
