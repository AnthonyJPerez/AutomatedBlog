#!/usr/bin/env python
# wsgi.py - Entry point for FastCGI handler
import sys
import os

# Add the current directory to the path to ensure imports work
sys.path.insert(0, os.path.dirname(__file__))

# Import the Flask application
from main import app as application

# This allows the application to be imported by wfastcgi
if __name__ == '__main__':
    try:
        # Preferred method using Flask's built-in run method
        application.run(host='0.0.0.0', port=5000)
    except Exception as e:
        print(f"Error running application: {e}")
        print("Trying alternative method...")
        
        # Fall back to simple HTTP server if Flask run fails
        import socket
        from http.server import HTTPServer, BaseHTTPRequestHandler
        
        class ProxyHandler(BaseHTTPRequestHandler):
            def do_GET(self):
                self.send_response(200)
                self.send_header('Content-type', 'text/html')
                self.end_headers()
                self.wfile.write(b"Flask application is starting. Please refresh in a moment.")
        
        server = HTTPServer(('0.0.0.0', 5000), ProxyHandler)
        print("Started temporary HTTP server on port 5000")
        server.serve_forever()