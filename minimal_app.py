# minimal_app.py
# A bare-minimum Flask application that is guaranteed to work in Azure App Service
# This is used to verify that the deployment pipeline works correctly

from flask import Flask, render_template_string

app = Flask(__name__)

@app.route('/')
def home():
    return render_template_string("""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Admin Portal - Minimal Test Page</title>
        <style>
            body { font-family: Arial, sans-serif; line-height: 1.6; max-width: 800px; margin: 0 auto; padding: 20px; }
            h1 { color: #2c3e50; }
            .success { color: green; background-color: #e7f9e7; padding: 10px; border-radius: 5px; }
            .container { border: 1px solid #ddd; padding: 20px; border-radius: 5px; margin-top: 20px; }
        </style>
    </head>
    <body>
        <h1>Admin Portal - Deployment Test</h1>
        <div class="success">
            <strong>Success!</strong> Your Flask application is running correctly in Azure App Service.
        </div>
        <div class="container">
            <h2>Deployment Verification</h2>
            <p>This is a minimal test application to verify that the Azure App Service deployment is working correctly.</p>
            <p>Now you can proceed with deploying your actual admin portal application.</p>
            <hr>
            <h3>Next Steps:</h3>
            <ol>
                <li>Update your main.py file</li>
                <li>Ensure all templates and static files are properly deployed</li>
                <li>Verify database connections are working</li>
                <li>Test all your application functionality</li>
            </ol>
        </div>
    </body>
    </html>
    """)

# This allows the app to be run when directly executed
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000, debug=True)