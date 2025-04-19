"""
Function app entry point
This file is necessary for the Azure Functions runtime
"""
import azure.functions as func
import logging

# Initialize logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

logger.info("Function app initialized")

# The following modules will be loaded by the Functions runtime
# scheduler - Triggers the blog generation pipeline on a schedule
# processor - Processes blog content generation tasks
# publisher - Publishes generated content to WordPress sites
# setup - Handles initial setup and bootstrap process
