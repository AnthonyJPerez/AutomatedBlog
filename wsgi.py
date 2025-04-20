#!/usr/bin/env python
"""
wsgi.py - WSGI entry point for the Admin Portal application
This file is the entry point for Gunicorn and other WSGI servers.
"""
import sys
import os
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger('wsgi')

# Add the current directory to the path to ensure imports work
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import the Flask application
from main import app as application

# This allows the application to be run directly
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    logger.info(f"Starting Flask application on port {port}")
    application.run(host='0.0.0.0', port=port)