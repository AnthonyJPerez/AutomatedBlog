import os
import json
import logging
import uuid
import datetime
from flask import Flask, render_template, request, jsonify, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from src.shared.models import BlogConfig, BlogTask, BlogContent, PublishResult
from src.shared.storage_service import StorageService
from src.shared.config_service import ConfigService
from src.shared.research_service import ResearchService
from src.shared.openai_service import OpenAIService

# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET", "dev-secret-key")

# Initialize services
storage_service = StorageService()
config_service = ConfigService()
research_service = ResearchService()
openai_service = OpenAIService()

# Ensure required containers exist
storage_service.ensure_containers_exist()

@app.route('/')
def index():
    """Main dashboard page"""
    # Get all blog configurations
    blogs = config_service.get_all_blog_configs()
    
    # Convert to dict for easier template rendering
    blog_list = [blog.to_dict() if hasattr(blog, 'to_dict') else blog for blog in blogs]
    
    return render_template('index.html', blogs=blog_list)

@app.route('/setup', methods=['GET', 'POST'])
def setup():
    """Setup page for creating new blog configurations"""
    if request.method == 'POST':
        # Extract form data
        blog_name = request.form.get('blog_name')
        theme = request.form.get('theme')
        wordpress_url = request.form.get('wordpress_url')
        wordpress_username = request.form.get('wordpress_username')
        wordpress_app_password = request.form.get('wordpress_app_password')
        tone = request.form.get('tone', 'professional')
        target_audience = request.form.get('target_audience', 'general')
        publishing_frequency = request.form.get('publishing_frequency', 'weekly')
        region = request.form.get('region', 'US')
        needs_domain = request.form.get('needs_domain', 'false') == 'true'
        
        # Content types handling
        content_types = request.form.getlist('content_types')
        if not content_types:
            content_types = ['article']
        
        # AdSense handling
        adsense_publisher_id = request.form.get('adsense_publisher_id', '')
        adsense_ad_slots = []
        
        if request.form.get('adsense_ad_slot_1'):
            adsense_ad_slots.append(request.form.get('adsense_ad_slot_1'))
        if request.form.get('adsense_ad_slot_2'):
            adsense_ad_slots.append(request.form.get('adsense_ad_slot_2'))
        
        # Validate required fields
        if not all([blog_name, theme, wordpress_url, wordpress_username, wordpress_app_password]):
            flash('Please fill in all required fields', 'danger')
            return render_template('setup.html')
        
        try:
            # Create new blog config
            blog_config = config_service.create_default_blog_config(
                blog_name=blog_name,
                theme=theme,
                wordpress_url=wordpress_url,
                wordpress_username=wordpress_username,
                wordpress_app_password=wordpress_app_password
            )
            
            # Update with additional fields
            if blog_config:
                blog_config.tone = tone
                blog_config.target_audience = target_audience
                blog_config.publishing_frequency = publishing_frequency
                blog_config.content_types = content_types
                blog_config.region = region
                blog_config.needs_domain = needs_domain
                blog_config.adsense_publisher_id = adsense_publisher_id
                blog_config.adsense_ad_slots = adsense_ad_slots
                
                # Save updated config
                config_service.update_blog_config(blog_config)
                
                flash(f'Blog "{blog_name}" successfully created!', 'success')
                return redirect(url_for('index'))
            else:
                flash('Error creating blog configuration', 'danger')
                return render_template('setup.html')
        except Exception as e:
            logger.error(f"Error creating blog: {str(e)}", exc_info=True)
            flash(f'Error: {str(e)}', 'danger')
            return render_template('setup.html')
    
    # GET request
    return render_template('setup.html')

@app.route('/blog/<blog_id>')
def blog_detail(blog_id):
    """Blog detail page"""
    # Get blog configuration
    blog = config_service.get_blog_config(blog_id)
    
    if not blog:
        flash('Blog not found', 'danger')
        return redirect(url_for('index'))
    
    # Get recent tasks
    task_blobs = storage_service.list_blobs("blog-data", f"task_{blog_id}")
    tasks = []
    
    for blob_name in task_blobs:
        task_data = storage_service.get_blob("blog-data", blob_name)
        if task_data:
            try:
                task = json.loads(task_data)
                tasks.append(task)
            except:
                logger.error(f"Error parsing task data: {blob_name}")
    
    # Get recent publish results
    result_blobs = storage_service.list_blobs("results", f"publish_{blog_id}")
    results = []
    
    for blob_name in result_blobs:
        result_data = storage_service.get_blob("results", blob_name)
        if result_data:
            try:
                result = json.loads(result_data)
                results.append(result)
            except:
                logger.error(f"Error parsing result data: {blob_name}")
    
    return render_template(
        'blog_detail.html', 
        blog=blog.to_dict() if hasattr(blog, 'to_dict') else blog,
        tasks=tasks,
        results=results
    )

@app.route('/blog/<blog_id>/generate', methods=['POST'])
def generate_content(blog_id):
    """Manually trigger content generation for a blog"""
    # Get blog configuration
    blog = config_service.get_blog_config(blog_id)
    
    if not blog:
        flash('Blog not found', 'danger')
        return redirect(url_for('index'))
    
    try:
        # Create a new task
        task_id = str(uuid.uuid4())
        now = datetime.datetime.utcnow().isoformat()
        
        task = BlogTask(
            id=task_id,
            blog_id=blog.blog_id,
            blog_name=blog.blog_name,
            status="pending",
            created_at=now,
            updated_at=now,
            theme=blog.theme,
            tone=blog.tone,
            target_audience=blog.target_audience,
            content_types=blog.content_types,
            wordpress_url=blog.wordpress_url,
            wordpress_username=blog.wordpress_username
        )
        
        # Save the task
        storage_service.save_blog_task(task)
        
        # In a real production environment, this would trigger the Azure Function
        # For this web interface, we'll simulate the process
        flash('Content generation task created successfully', 'success')
        return redirect(url_for('blog_detail', blog_id=blog_id))
    except Exception as e:
        logger.error(f"Error generating content: {str(e)}", exc_info=True)
        flash(f'Error: {str(e)}', 'danger')
        return redirect(url_for('blog_detail', blog_id=blog_id))

@app.route('/api/blogs', methods=['GET'])
def get_blogs():
    """API endpoint to get all blogs"""
    blogs = config_service.get_all_blog_configs()
    blog_list = [blog.to_dict() if hasattr(blog, 'to_dict') else blog for blog in blogs]
    return jsonify(blog_list)

@app.route('/api/research', methods=['POST'])
def research_topics():
    """API endpoint to research trending topics"""
    data = request.json
    
    theme = data.get('theme')
    target_audience = data.get('target_audience', 'general')
    region = data.get('region', 'US')
    
    if not theme:
        return jsonify({"error": "Theme is required"}), 400
    
    try:
        research_results = research_service.research_topics(theme, target_audience, region)
        return jsonify(research_results)
    except Exception as e:
        logger.error(f"Error researching topics: {str(e)}", exc_info=True)
        return jsonify({"error": str(e)}), 500

@app.route('/api/generate-outline', methods=['POST'])
def generate_outline():
    """API endpoint to generate a content outline"""
    data = request.json
    
    topic = data.get('topic')
    theme = data.get('theme')
    tone = data.get('tone', 'professional')
    target_audience = data.get('target_audience', 'general')
    
    if not all([topic, theme]):
        return jsonify({"error": "Topic and theme are required"}), 400
    
    try:
        outline = openai_service.generate_outline(topic, theme, tone, target_audience)
        return jsonify(outline)
    except Exception as e:
        logger.error(f"Error generating outline: {str(e)}", exc_info=True)
        return jsonify({"error": str(e)}), 500

# Custom error handlers
@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404

@app.errorhandler(500)
def server_error(e):
    return render_template('500.html'), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)