#!/bin/bash
# Startup script for Azure App Service
# This script is used to start the Flask application in Azure

# Default port is 5000, but use environment variable if available
PORT=${PORT:-5000}

# Log startup details
echo "Starting admin portal application..."
echo "Current directory: $(pwd)"
echo "Python version: $(python --version)"
echo "Packages installed:"
pip list

# Run the Flask application using Gunicorn
echo "Starting Gunicorn on port $PORT..."
gunicorn --bind=0.0.0.0:$PORT --timeout 600 main:app