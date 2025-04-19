import logging
import datetime
import json
import azure.functions as func

from ..shared.config_service import ConfigService
from ..shared.storage_service import StorageService
from ..shared.logging_service import LoggingService
from ..shared.models import BlogConfig

def main(req: func.HttpRequest) -> func.HttpResponse:
    """
    HTTP trigger for setting up a new blog configuration.
    This function initializes a new blog with the provided configuration.
    
    Parameters:
        req: The HTTP request
    """
    logger = LoggingService.get_logger("setup")
    
    # Log function start
    logger.info("Setup function triggered")
    
    try:
        # Parse the request body
        req_body = req.get_json()
        
        # Validate required fields
        required_fields = ['blog_name', 'theme', 'wordpress_url', 'wordpress_username', 'wordpress_app_password']
        missing_fields = [field for field in required_fields if field not in req_body]
        
        if missing_fields:
            logger.error(f"Missing required fields: {', '.join(missing_fields)}")
            return func.HttpResponse(
                body=json.dumps({
                    "error": "Missing required fields",
                    "missing_fields": missing_fields
                }),
                mimetype="application/json",
                status_code=400
            )
        
        # Initialize services
        config_service = ConfigService()
        storage_service = StorageService()
        
        # Ensure storage containers exist
        storage_service.ensure_containers_exist()
        
        # Create a new blog configuration
        blog_config = config_service.create_default_blog_config(
            blog_name=req_body['blog_name'],
            theme=req_body['theme'],
            wordpress_url=req_body['wordpress_url'],
            wordpress_username=req_body['wordpress_username'],
            wordpress_app_password=req_body['wordpress_app_password']
        )
        
        if not blog_config:
            logger.error("Failed to create blog configuration")
            return func.HttpResponse(
                body=json.dumps({
                    "error": "Failed to create blog configuration"
                }),
                mimetype="application/json",
                status_code=500
            )
        
        # Apply optional configurations if provided
        if 'tone' in req_body:
            blog_config.tone = req_body['tone']
        
        if 'target_audience' in req_body:
            blog_config.target_audience = req_body['target_audience']
        
        if 'content_types' in req_body:
            blog_config.content_types = req_body['content_types']
        
        if 'publishing_frequency' in req_body:
            blog_config.publishing_frequency = req_body['publishing_frequency']
        
        if 'adsense_publisher_id' in req_body:
            blog_config.adsense_publisher_id = req_body['adsense_publisher_id']
        
        if 'adsense_ad_slots' in req_body:
            blog_config.adsense_ad_slots = req_body['adsense_ad_slots']
        
        if 'region' in req_body:
            blog_config.region = req_body['region']
        
        if 'needs_domain' in req_body:
            blog_config.needs_domain = req_body['needs_domain']
        
        # Update the blog configuration with optional fields
        config_service.update_blog_config(blog_config)
        
        # Return success response
        logger.info(f"Successfully created blog configuration for {blog_config.blog_name} with ID {blog_config.blog_id}")
        
        return func.HttpResponse(
            body=json.dumps({
                "message": "Blog configuration created successfully",
                "blog_id": blog_config.blog_id,
                "blog_name": blog_config.blog_name
            }, indent=2),
            mimetype="application/json",
            status_code=200
        )
        
    except Exception as e:
        logger.error(f"Error in setup function: {str(e)}", exc_info=True)
        
        return func.HttpResponse(
            body=json.dumps({
                "error": "Internal server error",
                "message": str(e)
            }),
            mimetype="application/json",
            status_code=500
        )
