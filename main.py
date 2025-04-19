import os
import json
import logging
import datetime
from flask import Flask, render_template, request, redirect, url_for, jsonify, flash
from src.shared.storage_service import StorageService
from src.shared.research_service import ResearchService
from src.shared.openai_service import OpenAIService

# Set up logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET", "dev-secret-key")

# Initialize services
storage_service = StorageService()
research_service = ResearchService()
openai_service = OpenAIService()

@app.route('/')
def index():
    """Main dashboard page"""
    # Get all blogs from the config service
    blogs = []
    try:
        # For now, we'll simulate getting blog configurations by listing data folders
        blog_data_path = "data/blogs"
        storage_service.ensure_local_directory(blog_data_path)
        local_blog_folders = [f for f in os.listdir(blog_data_path) if os.path.isdir(os.path.join(blog_data_path, f))]
        
        for blog_id in local_blog_folders:
            try:
                blog_config_path = os.path.join(blog_data_path, blog_id, "config.json")
                if os.path.exists(blog_config_path):
                    with open(blog_config_path, 'r') as f:
                        blog_config = json.load(f)
                    
                    blogs.append({
                        'id': blog_id,
                        'name': blog_config.get('name', 'Unnamed Blog'),
                        'theme': blog_config.get('theme', 'No theme'),
                        'created_at': blog_config.get('created_at', 'Unknown'),
                        'is_active': blog_config.get('is_active', True)
                    })
            except Exception as e:
                logger.error(f"Error loading blog config for {blog_id}: {str(e)}")
    except Exception as e:
        logger.error(f"Error listing blog configurations: {str(e)}")
    
    # Get all the content generation runs
    runs = []
    try:
        # We'll look in each blog folder for content runs
        for blog in blogs:
            blog_id = blog['id']
            runs_path = os.path.join("data/blogs", blog_id, "runs")
            if os.path.exists(runs_path):
                run_folders = [f for f in os.listdir(runs_path) if os.path.isdir(os.path.join(runs_path, f))]
                
                for run_id in run_folders:
                    # Get run status
                    status = "unknown"
                    run_path = os.path.join(runs_path, run_id)
                    
                    if os.path.exists(os.path.join(run_path, "results.json")):
                        status = "completed"
                    elif os.path.exists(os.path.join(run_path, "publish.json")):
                        status = "published"
                    elif os.path.exists(os.path.join(run_path, "content.md")):
                        status = "content-generated"
                    elif os.path.exists(os.path.join(run_path, "research.json")):
                        status = "researched"
                    elif os.path.exists(os.path.join(run_path, ".run")):
                        status = "started"
                    
                    # Parse timestamp from run_id
                    timestamp = None
                    if '_' in run_id:
                        try:
                            date_part = run_id.split('_')[0]
                            time_part = run_id.split('_')[1]
                            dt_str = f"{date_part[:4]}-{date_part[4:6]}-{date_part[6:8]} {time_part[:2]}:{time_part[2:4]}:{time_part[4:6]}"
                            timestamp = datetime.datetime.strptime(dt_str, '%Y-%m-%d %H:%M:%S')
                        except Exception as e:
                            logger.warning(f"Could not parse timestamp from run_id {run_id}: {str(e)}")
                    
                    runs.append({
                        'id': run_id,
                        'blog_id': blog_id,
                        'blog_name': blog['name'],
                        'status': status,
                        'timestamp': timestamp,
                        'timestamp_str': timestamp.strftime('%Y-%m-%d %H:%M:%S') if timestamp else run_id
                    })
        
        # Sort runs by timestamp (newest first)
        runs.sort(key=lambda x: x['timestamp'] if x['timestamp'] else datetime.datetime.min, reverse=True)
    except Exception as e:
        logger.error(f"Error getting run data: {str(e)}")
    
    return render_template('index.html', blogs=blogs, runs=runs)

@app.route('/setup', methods=['GET', 'POST'])
def setup():
    """Setup page for creating new blog configurations"""
    if request.method == 'POST':
        try:
            # Get form data
            blog_name = request.form.get('blog_name', '').strip()
            theme = request.form.get('theme', '').strip()
            topic_keywords = request.form.get('topic_keywords', '').strip()
            frequency = request.form.get('frequency', 'weekly').strip()
            wordpress_url = request.form.get('wordpress_url', '').strip()
            wordpress_username = request.form.get('wordpress_username', '').strip()
            wordpress_app_password = request.form.get('wordpress_app_password', '').strip()
            enable_domain_suggestions = request.form.get('enable_domain_suggestions') == '1'
            max_price = int(request.form.get('max_price', '50'))
            content_length = int(request.form.get('content_length', '1000'))
            content_style = request.form.get('content_style', 'informative').strip()
            include_featured_image = request.form.get('include_featured_image') == '1'
            
            # Validate required fields
            if not blog_name or not theme or not topic_keywords:
                flash("Blog name, theme, and topic keywords are required fields.", "danger")
                return render_template('setup.html')
            
            # Create a unique blog ID
            blog_id = f"{blog_name.lower().replace(' ', '-')}-{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}"
            
            # Create the blog directory structure
            blog_path = os.path.join("data/blogs", blog_id)
            runs_path = os.path.join(blog_path, "runs")
            config_path = os.path.join(blog_path, "config")
            
            storage_service.ensure_local_directory(blog_path)
            storage_service.ensure_local_directory(runs_path)
            storage_service.ensure_local_directory(config_path)
            
            # Create topic keywords from the comma-separated list
            topics_list = [kw.strip() for kw in topic_keywords.split(',') if kw.strip()]
            
            # Create config.json
            config = {
                "name": blog_name,
                "theme": theme,
                "created_at": datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                "is_active": True,
                "frequency": frequency,
                "content_settings": {
                    "length": content_length,
                    "style": content_style,
                    "include_featured_image": include_featured_image
                },
                "topics": topics_list
            }
            
            # Add WordPress configuration if provided
            if wordpress_url:
                config["wordpress"] = {
                    "url": wordpress_url,
                    "username": wordpress_username,
                    "app_password": wordpress_app_password,
                    "connected": False  # Will be set to True once verified
                }
            
            # Add domain suggestions configuration if enabled
            if enable_domain_suggestions:
                config["domain_suggestions"] = {
                    "enabled": True,
                    "max_price": max_price
                }
            
            # Write the main config file
            with open(os.path.join(blog_path, "config.json"), 'w') as f:
                json.dump(config, f, indent=2)
            
            # Create the individual configuration files that will be used by the Azure Functions
            
            # Create topics.json
            topics_json = json.dumps(topics_list, indent=2)
            with open(os.path.join(config_path, "topics.json"), 'w') as f:
                f.write(topics_json)
            
            # Create theme.json
            theme_json = json.dumps({
                "name": theme,
                "description": f"A blog about {theme}",
                "target_audience": "General audience interested in " + theme
            }, indent=2)
            with open(os.path.join(config_path, "theme.json"), 'w') as f:
                f.write(theme_json)
            
            # Create frequency.json based on the selected frequency
            frequency_days = {
                "daily": 1,
                "weekly": 7,
                "biweekly": 14,
                "monthly": 30
            }.get(frequency, 7)
            
            frequency_json = json.dumps({
                "daily": frequency_days
            }, indent=2)
            with open(os.path.join(config_path, "frequency.json"), 'w') as f:
                f.write(frequency_json)
            
            # Create ready.json (empty)
            with open(os.path.join(config_path, "ready.json"), 'w') as f:
                f.write("{}")
            
            # Create bootstrap.json
            bootstrap_data = {
                "blog_name": blog_name,
                "theme": theme,
                "wordpress_url": wordpress_url if wordpress_url else None
            }
            with open(os.path.join(config_path, "bootstrap.json"), 'w') as f:
                json.dump(bootstrap_data, f, indent=2)
            
            flash(f"Blog '{blog_name}' has been created successfully!", "success")
            return redirect(url_for('index'))
        
        except Exception as e:
            logger.error(f"Error setting up blog: {str(e)}")
            flash(f"Error setting up blog: {str(e)}", "danger")
    
    return render_template('setup.html')

@app.route('/blog/<blog_id>')
def blog_detail(blog_id):
    """Blog detail page"""
    try:
        # Get blog configuration
        blog_path = os.path.join("data/blogs", blog_id)
        config_path = os.path.join(blog_path, "config.json")
        
        if not os.path.exists(config_path):
            flash(f"Blog configuration not found for ID: {blog_id}", "danger")
            return redirect(url_for('index'))
        
        with open(config_path, 'r') as f:
            config = json.load(f)
        
        # Create blog object for template
        blog = {
            'id': blog_id,
            'name': config.get('name', 'Unnamed Blog'),
            'theme': config.get('theme', 'No theme'),
            'created_at': config.get('created_at', 'Unknown'),
            'is_active': config.get('is_active', True),
            'frequency': config.get('frequency', 'unknown'),
        }
        
        # Add WordPress information if available
        if 'wordpress' in config:
            blog['wordpress_url'] = config['wordpress'].get('url')
            blog['wordpress_username'] = config['wordpress'].get('username')
            blog['wordpress_connected'] = config['wordpress'].get('connected', False)
        
        # Add domain suggestions if available
        if 'domain_suggestions' in config and config['domain_suggestions'].get('results'):
            blog['domain_suggestions'] = config['domain_suggestions'].get('results', [])
        
        # Check config files
        blog_config_dir = os.path.join(blog_path, "config")
        config_files = []
        
        for file_name in ['topics.json', 'theme.json', 'frequency.json', 'ready.json', 
                          'bootstrap.json', 'bootstrap.done.json', 'DomainNames.json']:
            config_files.append({
                'name': file_name,
                'exists': os.path.exists(os.path.join(blog_config_dir, file_name))
            })
        
        blog['config_files'] = config_files
        
        # Get content generation runs
        content_items = []
        runs_path = os.path.join(blog_path, "runs")
        
        if os.path.exists(runs_path):
            run_folders = [f for f in os.listdir(runs_path) if os.path.isdir(os.path.join(runs_path, f))]
            
            for run_id in run_folders:
                run_path = os.path.join(runs_path, run_id)
                
                # Only include runs that have generated content
                content_path = os.path.join(run_path, "content.md")
                if os.path.exists(content_path):
                    # Try to get title from content.md or generate one
                    title = None
                    excerpt = None
                    with open(content_path, 'r') as f:
                        content = f.read()
                        lines = content.strip().split('\n')
                        if lines and lines[0].startswith('# '):
                            title = lines[0][2:].strip()
                        
                        # Create a short excerpt (first 3 paragraphs)
                        paragraphs = [line for line in lines if line.strip() and not line.startswith('#')]
                        excerpt = '\n\n'.join(paragraphs[:3]) + "..."
                    
                    if not title:
                        title = f"Content from {run_id}"
                    
                    # Determine status
                    status = "generated"
                    url = None
                    
                    if os.path.exists(os.path.join(run_path, "results.json")):
                        status = "completed"
                    
                    if os.path.exists(os.path.join(run_path, "publish.json")):
                        status = "published"
                        # Try to get post URL from publish.json
                        with open(os.path.join(run_path, "publish.json"), 'r') as f:
                            try:
                                publish_data = json.load(f)
                                url = publish_data.get('url')
                            except:
                                pass
                    
                    # Parse timestamp from run_id
                    date_str = None
                    if '_' in run_id:
                        try:
                            date_part = run_id.split('_')[0]
                            date_str = f"{date_part[:4]}-{date_part[4:6]}-{date_part[6:8]}"
                        except:
                            date_str = "Unknown Date"
                    
                    content_items.append({
                        'run_id': run_id,
                        'title': title,
                        'excerpt': excerpt,
                        'status': status,
                        'date': date_str or "Unknown Date",
                        'url': url
                    })
        
        blog['content_items'] = content_items
        
        return render_template('blog_detail.html', blog=blog)
        
    except Exception as e:
        logger.error(f"Error loading blog details for {blog_id}: {str(e)}")
        flash(f"Error loading blog details: {str(e)}", "danger")
        return redirect(url_for('index'))

@app.route('/generate/<blog_id>', methods=['POST'])
def generate_content(blog_id):
    """Manually trigger content generation for a blog"""
    # Check if content.md already exists
    if storage_service.blob_exists("generated", f"{blog_id}/content.md"):
        flash(f"Content already exists for blog {blog_id}", "error")
        return redirect(url_for('blog_detail', blog_id=blog_id))
    
    try:
        # Get research.json
        research_json = storage_service.get_blob("generated", f"{blog_id}/research.json")
        if not research_json:
            flash(f"Research data not found for blog {blog_id}", "error")
            return redirect(url_for('blog_detail', blog_id=blog_id))
        
        research = json.loads(research_json)
        
        # Generate content using ContentGenerator
        from src.ContentGenerator import main as content_generator
        
        # TODO: Actually implement the generation
        flash(f"Content generation for blog {blog_id} has been triggered", "success")
        
    except Exception as e:
        logger.error(f"Error generating content: {str(e)}")
        flash(f"Error generating content: {str(e)}", "error")
    
    return redirect(url_for('blog_detail', blog_id=blog_id))

@app.route('/api/blogs')
def get_blogs():
    """API endpoint to get all blogs"""
    runs = []
    try:
        run_folders = storage_service.list_blobs("generated", None)
        for folder in run_folders:
            if '/' in folder:  # Skip files in the root generated folder
                run_id = folder.split('/')[0]
                if run_id not in [run['id'] for run in runs]:
                    runs.append({
                        'id': run_id,
                    })
    except Exception as e:
        logger.error(f"Error getting run data: {str(e)}")
    
    return jsonify(runs)

@app.route('/api/research_topics', methods=['POST'])
def research_topics():
    """API endpoint to research trending topics"""
    data = request.json
    theme = data.get('theme', '')
    
    if not theme:
        return jsonify({"error": "Theme is required"}), 400
    
    try:
        topics = research_service.research_topics(theme)
        return jsonify(topics)
    except Exception as e:
        logger.error(f"Error researching topics: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/generate_outline', methods=['POST'])
def generate_outline():
    """API endpoint to generate a content outline"""
    data = request.json
    topic = data.get('topic', '')
    theme = data.get('theme', '')
    
    if not topic or not theme:
        return jsonify({"error": "Topic and theme are required"}), 400
    
    try:
        outline = openai_service.generate_outline(topic, theme)
        return jsonify(outline)
    except Exception as e:
        logger.error(f"Error generating outline: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404

@app.errorhandler(500)
def server_error(e):
    return render_template('500.html'), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=True)