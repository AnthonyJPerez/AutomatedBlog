"""
wsgi.py - WSGI entry point for the Admin Portal application
This file is the entry point for Gunicorn and other WSGI servers.
"""
from main import app as application

if __name__ == "__main__":
    application.run()