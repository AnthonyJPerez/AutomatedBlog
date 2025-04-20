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
logger.info(f"Python version: {sys.version}")
logger.info(f"Current directory: {os.getcwd()}")
logger.info(f"Files in current directory: {os.listdir('.')}")

# Try to import the Flask application
try:
    from main import app as application
    logger.info("Successfully imported Flask application from main.py")
except Exception as e:
    logger.error(f"Error importing Flask application: {str(e)}")
    
    # Create a simple fallback application for diagnostics
    from flask import Flask, jsonify
    
    application = Flask(__name__)
    
    @application.route('/')
    def index():
        return """
        <html>
        <head>
            <title>Admin Portal - Error</title>
            <style>
                body { font-family: Arial, sans-serif; padding: 20px; }
                .error { background-color: #f8d7da; border: 1px solid #f5c6cb; padding: 15px; border-radius: 4px; }
                pre { background: #f8f9fa; padding: 10px; overflow: auto; }
            </style>
        </head>
        <body>
            <h1>Admin Portal Error</h1>
            <div class="error">
                <p>The main application could not be loaded.</p>
                <p>Please check the application logs for more details.</p>
                <pre>""" + str(e) + """</pre>
            </div>
            <p><a href="/api/status">Check API Status</a></p>
        </body>
        </html>
        """
    
    @application.route('/api/status')
    def status():
        return jsonify({
            'status': 'error',
            'message': 'Application failed to load: ' + str(e),
            'python_version': sys.version,
            'environment': {k: v for k, v in os.environ.items() 
                          if not k.lower().startswith(('key', 'secret', 'password'))}
        })
    
    logger.info("Created fallback diagnostic application")

# This allows the application to be run directly
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    logger.info(f"Starting Flask application on port {port}")
    application.run(host='0.0.0.0', port=port)