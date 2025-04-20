"""
Main function app for the blog automation pipeline.
This file uses the v2 programming model to register all function blueprints.
"""
import azure.functions as func
import logging
import sys
import os

# Add the src directory to the Python path to allow imports from shared modules
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

# Import function blueprints
from functions.scheduler import bp as scheduler_bp
from functions.processor import bp as processor_bp 
from functions.publisher import bp as publisher_bp
from functions.promoter import bp as promoter_bp

# Initialize logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('function_app')

# Create the function app
app = func.FunctionApp()

# Register all blueprints
app.register_blueprint(scheduler_bp)
app.register_blueprint(processor_bp)
app.register_blueprint(publisher_bp)
app.register_blueprint(promoter_bp)

logger.info("Function app initialized with all blueprints registered")