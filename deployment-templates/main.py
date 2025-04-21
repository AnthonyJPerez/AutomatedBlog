import os
from flask import Flask, render_template, jsonify

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "dev-key-replace-in-production")

@app.route('/')
def index():
    return render_template('index.html', title="Blog Automation Admin Portal")

@app.route('/health')
def health():
    return jsonify({
        "status": "healthy",
        "version": "1.0.0",
        "environment": os.environ.get("ENVIRONMENT", "production")
    })

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))