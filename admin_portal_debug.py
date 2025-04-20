#!/usr/bin/env python
"""
Debug application for the Blog Automation Admin Portal
This helps troubleshoot deployment issues on Azure Web Apps

Run with:
python admin_portal_debug.py
"""
import os
import sys
import platform
import json
import logging
import importlib.util
from datetime import datetime
import subprocess

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def check_python_version():
    """Check Python version information"""
    logger.info(f"Python version: {platform.python_version()}")
    logger.info(f"Python implementation: {platform.python_implementation()}")
    logger.info(f"System: {platform.system()} {platform.release()}")
    logger.info(f"Python path: {sys.executable}")
    logger.info(f"Python path directories:")
    for path in sys.path:
        logger.info(f"  - {path}")

def check_environment_variables():
    """Check environment variables that affect the application"""
    critical_vars = [
        "WEBSITE_SITE_NAME", 
        "WEBSITE_HOSTNAME", 
        "WEBSITE_PORT", 
        "FLASK_APP", 
        "KEY_VAULT_NAME"
    ]
    
    logger.info("Environment variables:")
    for var in critical_vars:
        value = os.environ.get(var, "NOT SET")
        # Mask sensitive values
        if "KEY" in var or "SECRET" in var or "PASSWORD" in var:
            if value != "NOT SET":
                value = "********" 
        logger.info(f"  {var}: {value}")

def check_file_structure():
    """Check file structure and existence of critical files"""
    critical_files = [
        "main.py",
        "wsgi.py",
        "requirements.txt",
        "static/css/main.css",
        "templates/index.html"
    ]
    
    logger.info("Critical file check:")
    for file_path in critical_files:
        exists = os.path.exists(file_path)
        size = os.path.getsize(file_path) if exists else 0
        logger.info(f"  {file_path}: {'EXISTS' if exists else 'MISSING'} ({size} bytes)")
    
    # Check data directory
    data_dir = "data"
    if os.path.exists(data_dir) and os.path.isdir(data_dir):
        logger.info(f"Data directory exists with contents:")
        try:
            for item in os.listdir(data_dir):
                item_path = os.path.join(data_dir, item)
                if os.path.isdir(item_path):
                    logger.info(f"  - {item}/ (directory)")
                else:
                    logger.info(f"  - {item} (file, {os.path.getsize(item_path)} bytes)")
        except Exception as e:
            logger.error(f"Error listing data directory: {str(e)}")
    else:
        logger.warning("Data directory is missing")
        # Create data directory
        try:
            os.makedirs(data_dir)
            logger.info("Created data directory")
        except Exception as e:
            logger.error(f"Failed to create data directory: {str(e)}")

def check_installed_packages():
    """Check installed packages"""
    try:
        import pkg_resources
        logger.info("Installed packages:")
        for package in pkg_resources.working_set:
            logger.info(f"  {package.key} {package.version}")
    except Exception as e:
        logger.error(f"Error checking installed packages: {str(e)}")

def check_flask_app():
    """Check if the Flask app can be imported"""
    try:
        import traceback
        spec = importlib.util.spec_from_file_location("main", "main.py")
        if not spec:
            logger.error("Failed to find main.py module")
            return
        
        main_module = importlib.util.module_from_spec(spec)
        if spec.loader:
            spec.loader.exec_module(main_module)
            
            if hasattr(main_module, "app"):
                logger.info("Successfully imported Flask app from main.py")
                if hasattr(main_module.app, "url_map"):
                    logger.info("Routes defined in the Flask app:")
                    for rule in main_module.app.url_map.iter_rules():
                        logger.info(f"  {rule.endpoint}: {rule.rule} [{', '.join(rule.methods)}]")
            else:
                logger.error("No Flask app found in main.py")
        else:
            logger.error("No loader available for main.py")
    except Exception as e:
        logger.error(f"Error importing Flask app: {str(e)}")
        try:
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
        except:
            logger.error("Could not import traceback module")

def check_network_connectivity():
    """Check network connectivity by pinging Google DNS"""
    try:
        import socket
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(2)
        result = s.connect_ex(("8.8.8.8", 53))
        s.close()
        
        if result == 0:
            logger.info("Network connectivity: OK (can reach Google DNS)")
        else:
            logger.warning(f"Network connectivity: FAILED (Error code: {result})")
    except Exception as e:
        logger.error(f"Network connectivity check failed: {str(e)}")

def create_debug_html():
    """Create a debug HTML file with diagnostic information"""
    debug_info = {
        "timestamp": datetime.now().isoformat(),
        "python_version": platform.python_version(),
        "system": f"{platform.system()} {platform.release()}",
        "environment_variables": {k: v for k, v in os.environ.items() if not k.lower().startswith(("key", "secret", "password"))},
        "file_exists": {}
    }
    
    # Check for critical files
    for file_path in ["main.py", "wsgi.py", "requirements.txt", "static", "templates"]:
        debug_info["file_exists"][file_path] = os.path.exists(file_path)
    
    # Create debug HTML
    html_content = f"""<!DOCTYPE html>
<html>
<head>
    <title>Admin Portal Debug Info</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; }}
        h1 {{ color: #333; }}
        .section {{ margin-bottom: 20px; }}
        .info {{ background-color: #f8f9fa; padding: 10px; border: 1px solid #ddd; }}
        .missing {{ color: red; }}
        .exists {{ color: green; }}
    </style>
</head>
<body>
    <h1>Admin Portal Debug Information</h1>
    <div class="section">
        <h2>System Information</h2>
        <div class="info">
            <p><strong>Timestamp:</strong> {debug_info['timestamp']}</p>
            <p><strong>Python Version:</strong> {debug_info['python_version']}</p>
            <p><strong>System:</strong> {debug_info['system']}</p>
            <p><strong>Working Directory:</strong> {os.getcwd()}</p>
        </div>
    </div>
    
    <div class="section">
        <h2>Critical Files</h2>
        <div class="info">
            <ul>
"""
    
    for file_path, exists in debug_info["file_exists"].items():
        status_class = "exists" if exists else "missing"
        html_content += f'                <li class="{status_class}">{file_path}: {"EXISTS" if exists else "MISSING"}</li>\n'
    
    html_content += """            </ul>
        </div>
    </div>
    
    <div class="section">
        <h2>Environment Variables</h2>
        <div class="info">
            <ul>
"""
    
    for key, value in sorted(debug_info["environment_variables"].items()):
        html_content += f"                <li><strong>{key}:</strong> {value}</li>\n"
    
    html_content += """            </ul>
        </div>
    </div>
    
    <div class="section">
        <h2>Troubleshooting</h2>
        <div class="info">
            <p>If you're seeing this page, the admin portal is not functioning correctly.</p>
            <p>Common solutions:</p>
            <ul>
                <li>Check if all required files are present</li>
                <li>Verify Python version and installed packages</li>
                <li>Check environment variables configuration</li>
                <li>Review application logs in Azure Portal</li>
                <li>Validate startup command configuration</li>
            </ul>
        </div>
    </div>
</body>
</html>
"""
    
    # Write the debug HTML to a file
    with open("debug_info.html", "w") as f:
        f.write(html_content)
    
    logger.info("Created debug_info.html with diagnostic information")

def create_minimal_app():
    """Create a minimal Flask app file for testing"""
    minimal_app_content = """#!/usr/bin/env python
import os
from flask import Flask, render_template_string, jsonify

app = Flask(__name__)

@app.route('/')
def index():
    html = '''<!DOCTYPE html>
<html>
<head>
    <title>Admin Portal - Minimal Test</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; }
        h1 { color: #333; }
        .info { background-color: #f8f9fa; padding: 15px; border: 1px solid #ddd; }
    </style>
</head>
<body>
    <h1>Admin Portal - Minimal Test</h1>
    <div class="info">
        <p>If you can see this page, the minimal Flask app is working.</p>
        <p>Next steps:</p>
        <ul>
            <li>Check the <a href="/api/status">API Status</a> endpoint</li>
            <li>Review the full application logs</li>
            <li>Deploy the complete application once this test succeeds</li>
        </ul>
    </div>
</body>
</html>'''
    return render_template_string(html)

@app.route('/api/status')
def status():
    return jsonify({
        'status': 'ok',
        'python_version': os.environ.get('PYTHON_VERSION', 'Unknown'),
        'app_name': os.environ.get('WEBSITE_SITE_NAME', 'Unknown'),
        'timestamp': str(datetime.now())
    })

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
"""
    
    with open("minimal_app.py", "w") as f:
        f.write(minimal_app_content)
    
    logger.info("Created minimal_app.py for testing")

def create_debug_entry_point():
    """Create a debug entry point file"""
    debug_wsgi_content = """#!/usr/bin/env python
# debug_wsgi.py - Entry point for debug application
import os
import sys
from datetime import datetime

# Add the current directory to the path
sys.path.insert(0, os.path.dirname(__file__))

def application(environ, start_response):
    """WSGI application function for debugging"""
    path_info = environ.get('PATH_INFO', '/')
    
    if path_info == '/debug':
        # Return debug information as plain text
        status = '200 OK'
        headers = [('Content-Type', 'text/plain; charset=utf-8')]
        start_response(status, headers)
        
        debug_info = [
            "Admin Portal Debug Information",
            f"Timestamp: {datetime.now().isoformat()}",
            f"Python Version: {sys.version}",
            f"WSGI environ variables:",
        ]
        
        # Add environ variables
        for key, value in sorted(environ.items()):
            debug_info.append(f"  {key}: {value}")
        
        # Add system path information
        debug_info.append("Python sys.path:")
        for path in sys.path:
            debug_info.append(f"  {path}")
        
        return [line.encode('utf-8') + b'\\n' for line in debug_info]
    
    elif path_info == '/minimal':
        # Return a simple HTML page for minimal testing
        status = '200 OK'
        headers = [('Content-Type', 'text/html; charset=utf-8')]
        start_response(status, headers)
        
        html = f'''<!DOCTYPE html>
<html>
<head>
    <title>Minimal Debug Page</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; }}
        h1 {{ color: #333; }}
        .info {{ background-color: #f8f9fa; padding: 15px; border: 1px solid #ddd; }}
    </style>
</head>
<body>
    <h1>Minimal Debug Page</h1>
    <div class="info">
        <p>This is a minimal debug page to check if the WSGI application is working.</p>
        <p>Current time: {datetime.now().isoformat()}</p>
        <p>Python version: {sys.version}</p>
        <p>Testing URLs:</p>
        <ul>
            <li><a href="/debug">Debug Information</a></li>
            <li><a href="/minimal">This Minimal Page</a></li>
        </ul>
    </div>
</body>
</html>'''
        
        return [html.encode('utf-8')]
    
    else:
        # Try to import and use the main application
        try:
            # Try to import the Flask application
            from main import app as flask_app
            
            # Create a WSGI callable from the Flask app
            return flask_app.wsgi_app(environ, start_response)
        except Exception as e:
            # If that fails, return an error page
            status = '500 Internal Server Error'
            headers = [('Content-Type', 'text/html; charset=utf-8')]
            start_response(status, headers)
            
            error_html = f'''<!DOCTYPE html>
<html>
<head>
    <title>Admin Portal Error</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; color: #333; }}
        h1 {{ color: #d9534f; }}
        .error {{ background-color: #f8d7da; padding: 15px; border: 1px solid #f5c6cb; }}
        .info {{ background-color: #f8f9fa; padding: 15px; border: 1px solid #ddd; }}
    </style>
</head>
<body>
    <h1>Admin Portal Error</h1>
    <div class="error">
        <p>The main application could not be loaded due to an error:</p>
        <pre>{str(e)}</pre>
    </div>
    <div class="info">
        <p>Diagnostic URLs:</p>
        <ul>
            <li><a href="/debug">Debug Information</a></li>
            <li><a href="/minimal">Minimal Test Page</a></li>
        </ul>
    </div>
</body>
</html>'''
            
            return [error_html.encode('utf-8')]

# If run directly, not through WSGI
if __name__ == '__main__':
    # Import the Flask application if we can
    try:
        from main import app
        print("Successfully imported Flask app from main.py")
        
        # Run the app directly
        app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
    except Exception as e:
        # If we can't import the main app, run a simple HTTP server
        import http.server
        import socketserver
        
        PORT = int(os.environ.get('PORT', 5000))
        
        class DebugHandler(http.server.SimpleHTTPRequestHandler):
            def do_GET(self):
                if self.path == '/debug':
                    self.send_response(200)
                    self.send_header('Content-type', 'text/plain')
                    self.end_headers()
                    
                    debug_info = [
                        "Admin Portal Debug Information",
                        f"Timestamp: {datetime.now().isoformat()}",
                        f"Python Version: {sys.version}",
                        "Error importing main application:",
                        str(e),
                        "",
                        "Environment variables:"
                    ]
                    
                    for key, value in sorted(os.environ.items()):
                        if not key.lower().startswith(("key", "secret", "password")):
                            debug_info.append(f"  {key}: {value}")
                    
                    self.wfile.write("\\n".join(debug_info).encode('utf-8'))
                else:
                    # Serve an HTML error page
                    self.send_response(200)
                    self.send_header('Content-type', 'text/html')
                    self.end_headers()
                    
                    html = f'''<!DOCTYPE html>
<html>
<head>
    <title>Admin Portal Debug Server</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; }}
        h1 {{ color: #333; }}
        .error {{ background-color: #f8d7da; padding: 15px; border: 1px solid #f5c6cb; }}
        .info {{ background-color: #f8f9fa; padding: 15px; border: 1px solid #ddd; margin-top: 20px; }}
    </style>
</head>
<body>
    <h1>Admin Portal Debug Server</h1>
    <div class="error">
        <h2>Main Application Error</h2>
        <p>The main application could not be loaded due to an error:</p>
        <pre>{str(e)}</pre>
    </div>
    <div class="info">
        <p>This is a debug HTTP server running in place of the Flask application.</p>
        <p>Current time: {datetime.now().isoformat()}</p>
        <p>Python version: {sys.version}</p>
        <p><a href="/debug">View Debug Information</a></p>
    </div>
</body>
</html>'''
                    
                    self.wfile.write(html.encode('utf-8'))
        
        print(f"Starting debug HTTP server on port {PORT}")
        with socketserver.TCPServer(("", PORT), DebugHandler) as httpd:
            print(f"Debug server running at http://0.0.0.0:{PORT}/")
            print(f"View debug info at http://0.0.0.0:{PORT}/debug")
            httpd.serve_forever()
"""
    
    with open("debug_wsgi.py", "w") as f:
        f.write(debug_wsgi_content)
    
    logger.info("Created debug_wsgi.py for debugging")

def main():
    """Main function to run diagnostics"""
    logger.info("Starting admin portal debug diagnostics")
    logger.info(f"Current working directory: {os.getcwd()}")
    
    check_python_version()
    check_environment_variables()
    check_file_structure()
    check_installed_packages()
    check_network_connectivity()
    
    create_debug_html()
    create_minimal_app()
    create_debug_entry_point()
    
    logger.info("Diagnostic complete. Created debug files to assist troubleshooting.")
    
    print("\n" + "="*80)
    print("Debug diagnostics complete!")
    print("Files created to help troubleshooting:")
    print("  - debug_info.html - Web page with diagnostic information")
    print("  - minimal_app.py - Simple Flask app for testing")
    print("  - debug_wsgi.py - Debug WSGI application")
    print("\nTo test with the minimal app:")
    print("  python minimal_app.py")
    print("\nTo troubleshoot deployment issues in Azure App Service:")
    print("1. Set startup command to: gunicorn --bind=0.0.0.0:5000 debug_wsgi:application")
    print("2. Visit the /debug or /minimal paths on your site to access the debug pages")
    print("="*80)

if __name__ == "__main__":
    main()