import os
import json
import logging
import datetime
import shutil
import glob
import traceback
from flask import Flask, render_template, request, redirect, url_for, jsonify, flash
from src.shared.storage_service import StorageService
from src.shared.research_service import ResearchService
from src.shared.openai_service import OpenAIService
from src.shared.openai_service_optimizer import OptimizedOpenAIService
from src.shared.billing_service import BillingService
from src.shared.ai_optimization_controller import ai_optimization_bp, init_controller

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

# Initialize the optimized OpenAI service with caching enabled
# Use environment variables to configure caching and budget
cache_ttl = int(os.environ.get("OPENAI_CACHE_TTL_SECONDS", "3600"))  # Default 1 hour
enable_caching = os.environ.get("OPENAI_ENABLE_CACHING", "True").lower() == "true"
optimized_openai_service = OptimizedOpenAIService(
    cache_ttl_seconds=cache_ttl,
    enable_caching=enable_caching
)
billing_service = BillingService()

# Initialize and register the AI optimization controller
init_controller(optimized_openai_service)
app.register_blueprint(ai_optimization_bp, url_prefix='/api/ai-optimization')

# Initialize analytics service
try:
    from src.shared.analytics_service import AnalyticsService
    analytics_service = AnalyticsService(storage_service=storage_service)
    logger.info("Analytics service initialized")
except Exception as e:
    logger.warning(f"Failed to initialize Analytics service: {str(e)}")
    analytics_service = None

# Initialize social media service
try:
    from src.shared.social_media_service import SocialMediaService
    social_media_service = SocialMediaService()
    logger.info("Social Media service initialized")
except Exception as e:
    logger.warning(f"Failed to initialize Social Media service: {str(e)}")
    social_media_service = None

# Initialize web scraper services
try:
    from src.shared.web_scraper_service import web_scraper_service
    from src.shared.web_scraper import WebScraper
    logger.info("Web Scraper services initialized")
except Exception as e:
    logger.warning(f"Failed to initialize Web Scraper services: {str(e)}")
    web_scraper_service = None

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
                        'description': blog_config.get('description', f"A blog about {blog_config.get('theme', 'various topics')}"),
                        'created_at': blog_config.get('created_at', 'Unknown'),
                        'is_active': blog_config.get('is_active', True),
                        'frequency': blog_config.get('frequency', 'weekly'),
                        'wordpress': blog_config.get('wordpress', {}),
                        'wordpress_connected': 'wordpress' in blog_config and blog_config['wordpress'].get('connected', False),
                        'wordpress_url': blog_config.get('wordpress', {}).get('url', '')
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
                    
                    # Check if content is available for the run
                    content_available = os.path.exists(os.path.join(run_path, "content.md"))
                    
                    runs.append({
                        'id': run_id,
                        'blog_id': blog_id,
                        'blog_name': blog['name'],
                        'status': status,
                        'timestamp': timestamp,
                        'timestamp_str': timestamp.strftime('%Y-%m-%d %H:%M:%S') if timestamp else run_id,
                        'content_available': content_available
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
            blog_description = request.form.get('blog_description', '').strip()
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
            
            # Image generation settings
            image_generation_count = int(request.form.get('image_generation_count', '1'))
            use_gpt4o_descriptions = request.form.get('use_gpt4o_descriptions') == '1'
            image_generation_style = request.form.get('image_generation_style', 'natural')
            enable_section_images = request.form.get('enable_section_images') == '1'
            
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
                "description": blog_description if blog_description else f"A blog about {theme}",
                "created_at": datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                "is_active": True,
                "frequency": frequency,
                "content_settings": {
                    "length": content_length,
                    "style": content_style
                },
                "image_generation": {
                    "enabled": include_featured_image,
                    "count": image_generation_count if include_featured_image else 0,
                    "use_gpt4o_descriptions": use_gpt4o_descriptions,
                    "style": image_generation_style,
                    "quality": "standard",  # Default to standard quality
                    "size": "1024x1024",    # Default to 1024x1024 size
                    "section_images": enable_section_images
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
            
            # Add social media promotion configuration if enabled
            enable_social_promotion = request.form.get('enable_social_promotion') == '1'
            social_platforms = request.form.getlist('social_platforms')
            
            config["social_media"] = {
                "enabled": enable_social_promotion,
                "platforms": social_platforms
            }
            
            # Handle blog-specific API keys and credentials
            # Initialize integrations section for custom credentials
            integrations = {}
            
            # OpenAI API key
            openai_api_key = request.form.get('openai_api_key', '').strip()
            if openai_api_key:
                integrations['openai_api_key'] = openai_api_key
            
            # Social media API keys (if social promotion is enabled)
            if enable_social_promotion:
                # Twitter API key
                twitter_api_key = request.form.get('twitter_api_key', '').strip()
                if twitter_api_key:
                    integrations['twitter_api_key'] = twitter_api_key
                
                # LinkedIn API key
                linkedin_api_key = request.form.get('linkedin_api_key', '').strip()
                if linkedin_api_key:
                    integrations['linkedin_api_key'] = linkedin_api_key
                
                # Facebook API key
                facebook_api_key = request.form.get('facebook_api_key', '').strip()
                if facebook_api_key:
                    integrations['facebook_api_key'] = facebook_api_key
            
            # Only add integrations section if there are any custom credentials
            if integrations:
                config["integrations"] = integrations
            
            # Write the main config file
            with open(os.path.join(blog_path, "config.json"), 'w') as f:
                json.dump(config, f, indent=2)
            
            # Create the individual configuration files that will be used by the Azure Functions
            
            # Create topics.json
            topics_json = json.dumps(topics_list, indent=2)
            with open(os.path.join(config_path, "topics.json"), 'w') as f:
                f.write(topics_json)
            
            # Create theme.json with blog description
            theme_json = json.dumps({
                "name": theme,
                "description": blog_description if blog_description else f"A blog about {theme}",
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
            
            # Create bootstrap.json with blog description
            bootstrap_data = {
                "blog_name": blog_name,
                "theme": theme,
                "description": blog_description if blog_description else f"A blog about {theme}",
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
            'description': config.get('description', f"A blog about {config.get('theme', 'various topics')}"),
            'created_at': config.get('created_at', 'Unknown'),
            'is_active': config.get('is_active', True),
            'frequency': config.get('frequency', 'unknown'),
        }
        
        # Add WordPress information if available
        if 'wordpress' in config:
            blog['wordpress_url'] = config['wordpress'].get('url')
            blog['wordpress_username'] = config['wordpress'].get('username')
            blog['wordpress_connected'] = config['wordpress'].get('connected', False)
        
        # Add image generation settings if available
        if 'image_generation' in config:
            blog['image_generation'] = config['image_generation']
        
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

@app.route('/edit_blog_config/<blog_id>', methods=['GET', 'POST'])
def edit_blog_config(blog_id):
    """Edit blog configuration page"""
    try:
        # Get blog configuration
        blog_path = os.path.join("data/blogs", blog_id)
        config_path = os.path.join(blog_path, "config.json")
        
        if not os.path.exists(config_path):
            flash(f"Blog configuration not found for ID: {blog_id}", "danger")
            return redirect(url_for('index'))
        
        with open(config_path, 'r') as f:
            config = json.load(f)
        
        if request.method == 'POST':
            # Update blog configuration
            blog_name = request.form.get('blog_name', '').strip()
            theme = request.form.get('theme', '').strip()
            blog_description = request.form.get('blog_description', '').strip()
            topic_keywords = request.form.get('topic_keywords', '').strip()
            frequency = request.form.get('frequency', 'weekly').strip()
            is_active = request.form.get('is_active') == '1'
            wordpress_url = request.form.get('wordpress_url', '').strip()
            
            # Validate required fields
            if not blog_name or not theme:
                flash("Blog name and theme are required fields.", "danger")
                return redirect(url_for('edit_blog_config', blog_id=blog_id))
            
            # Update base config
            config['name'] = blog_name
            config['theme'] = theme
            config['description'] = blog_description if blog_description else f"A blog about {theme}"
            config['is_active'] = is_active
            config['frequency'] = frequency
            
            # Update WordPress configuration if provided
            if wordpress_url:
                if 'wordpress' not in config:
                    config['wordpress'] = {}
                config['wordpress']['url'] = wordpress_url
            
            # Update topics
            topics_list = [kw.strip() for kw in topic_keywords.split(',') if kw.strip()]
            config['topics'] = topics_list
            
            # Save config.json
            with open(config_path, 'w') as f:
                json.dump(config, f, indent=2)
            
            # Update theme.json
            config_dir = os.path.join(blog_path, "config")
            theme_json_path = os.path.join(config_dir, "theme.json")
            
            if os.path.exists(theme_json_path):
                with open(theme_json_path, 'r') as f:
                    theme_json = json.load(f)
                
                theme_json['name'] = theme
                theme_json['description'] = blog_description if blog_description else f"A blog about {theme}"
                
                with open(theme_json_path, 'w') as f:
                    json.dump(theme_json, f, indent=2)
            
            # Update topics.json
            topics_json_path = os.path.join(config_dir, "topics.json")
            with open(topics_json_path, 'w') as f:
                json.dump(topics_list, f, indent=2)
            
            flash(f"Blog '{blog_name}' has been updated successfully!", "success")
            return redirect(url_for('blog_detail', blog_id=blog_id))
        
        # For GET requests, display the form with current values
        topics_str = ", ".join(config.get('topics', []))
        wordpress_url = config.get('wordpress', {}).get('url', '')
        
        return render_template('edit_blog_config.html', 
                              blog_id=blog_id, 
                              blog_name=config.get('name', ''),
                              theme=config.get('theme', ''),
                              description=config.get('description', ''),
                              topics=topics_str,
                              frequency=config.get('frequency', 'weekly'),
                              is_active=config.get('is_active', True),
                              wordpress_url=wordpress_url)
        
    except Exception as e:
        logger.error(f"Error editing blog configuration for {blog_id}: {str(e)}")
        flash(f"Error editing blog configuration: {str(e)}", "danger")
        return redirect(url_for('blog_detail', blog_id=blog_id))

@app.route('/generate/<blog_id>', methods=['GET', 'POST'])
def generate_content(blog_id):
    """Manually trigger content generation for a blog"""
    try:
        # Get blog configuration
        blog_path = os.path.join("data/blogs", blog_id)
        config_path = os.path.join(blog_path, "config.json")
        
        if not os.path.exists(config_path):
            flash(f"Blog configuration not found for ID: {blog_id}", "danger")
            return redirect(url_for('index'))
        
        with open(config_path, 'r') as f:
            config = json.load(f)
        
        # Create a new run ID
        run_id = storage_service.get_run_id()
        run_path = os.path.join(blog_path, "runs", run_id)
        storage_service.ensure_local_directory(run_path)
        
        # Step 1: Research trending topics related to the blog theme
        theme = config.get('theme', '')
        topics = config.get('topics', [])
        
        # Research trending topics related to the blog theme and focus topics
        research_results = {
            "theme": theme,
            "timestamp": datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            "trending_topics": []
        }
        
        try:
            trending_topics = research_service.research_topics(theme)
            research_results["trending_topics"] = trending_topics[:5]  # Get top 5 trending topics
            
            # Add blog-specific topics
            if topics:
                research_results["blog_topics"] = topics
        except Exception as e:
            logger.warning(f"Error researching trending topics: {str(e)}. Using backup topics.")
            # Fallback - use the blog's predefined topics
            if topics:
                research_results["trending_topics"] = [{"title": topic, "query": topic} for topic in topics[:5]]
            else:
                research_results["trending_topics"] = [
                    {"title": f"{theme} news", "query": f"{theme} news"},
                    {"title": f"{theme} trends", "query": f"{theme} trends"},
                    {"title": f"{theme} guide", "query": f"{theme} guide"},
                    {"title": f"{theme} tips", "query": f"{theme} tips"},
                    {"title": f"{theme} examples", "query": f"{theme} examples"}
                ]
        
        # Save research.json
        with open(os.path.join(run_path, "research.json"), 'w') as f:
            json.dump(research_results, f, indent=2)
        
        # Step 2: Generate content based on research
        # Select a topic from research results
        selected_topic = None
        if research_results["trending_topics"]:
            selected_topic = research_results["trending_topics"][0]["title"]
        elif "blog_topics" in research_results and research_results["blog_topics"]:
            selected_topic = research_results["blog_topics"][0]
        else:
            selected_topic = f"{theme} guide"
        
        # Generate content using OpenAI
        try:
            content_settings = config.get('content_settings', {})
            content_length = content_settings.get('length', 1000)
            content_style = content_settings.get('style', 'informative')
            
            # Get image generation settings
            image_settings = config.get('image_generation', {})
            image_enabled = image_settings.get('enabled', False)
            image_count = image_settings.get('count', 0) if image_enabled else 0
            use_gpt4o_descriptions = image_settings.get('use_gpt4o_descriptions', False)
            image_style = image_settings.get('style', 'natural')
            enable_section_images = image_settings.get('section_images', False)
            
            prompt = f"""
            Create a comprehensive blog post about "{selected_topic}" in the context of "{theme}".
            
            The blog post should be approximately {content_length} words long and written in a {content_style} style.
            
            Include the following sections:
            1. An engaging introduction that hooks the reader
            2. Main content with 3-5 key points or sections
            3. A conclusion that summarizes the main points
            
            Format the post using Markdown with appropriate headers, lists, and emphasis.
            Start with a # Title heading that's catchy and SEO-friendly.
            """
            
            # Generate content
            # Use the optimized service for cost savings
            content = optimized_openai_service.generate_content(prompt)
            
            # Generate featured image if enabled
            featured_image_path = None
            if image_enabled and image_count > 0:
                try:
                    # Extract title from content
                    title = None
                    lines = content.strip().split('\n')
                    if lines and lines[0].startswith('# '):
                        title = lines[0][2:].strip()
                    else:
                        title = selected_topic
                    
                    logger.info(f"Generating {image_count} images for content with title: {title}")
                    
                    # Generate image prompt
                    image_prompt = None
                    if use_gpt4o_descriptions:
                        # Use GPT-4o to create a detailed image prompt
                        gpt4o_prompt = f"""
                        Create a detailed, vivid description for a high-quality featured image for an article titled:
                        "{title}"
                        
                        The article is about {selected_topic} in the context of {theme}.
                        The image should be in {image_style} style.
                        
                        Provide only the image description, make it detailed but concise (max 100 words).
                        Do not include any explanation or commentary, just the image description.
                        """
                        
                        image_prompt = optimized_openai_service.generate_content(gpt4o_prompt, content_type="polish").strip()
                        logger.info(f"Generated GPT-4o image prompt: {image_prompt[:100]}...")
                    else:
                        # Use a simple prompt
                        image_prompt = f"A high-quality {image_style} style image representing {title} in the context of {theme}, professional, detailed"
                    
                    # Generate featured image
                    image_result = openai_service.generate_image(image_prompt)
                    if image_result and "url" in image_result:
                        # Add image URL to frontmatter
                        featured_image_path = image_result["url"]
                        
                        # Create frontmatter and prepend to content
                        frontmatter = f"""---
title: "{title}"
featured_image: "{featured_image_path}"
date: "{datetime.datetime.now().strftime('%Y-%m-%d')}"
topic: "{selected_topic}"
theme: "{theme}"
---

"""
                        content = frontmatter + content
                        
                        logger.info(f"Added featured image to content: {featured_image_path[:50]}...")
                except Exception as e:
                    logger.error(f"Error generating featured image: {str(e)}")
            
            # Save content.md
            with open(os.path.join(run_path, "content.md"), 'w') as f:
                f.write(content)
            
            # Generate SEO recommendations
            seo_prompt = f"""
            Based on the blog post about "{selected_topic}" in the context of "{theme}", 
            provide SEO recommendations in JSON format with the following structure:
            
            {{
                "meta_title": "Suggested meta title, maximum 60 characters",
                "meta_description": "Suggested meta description, maximum 160 characters",
                "keywords": ["keyword1", "keyword2", "keyword3", ...],
                "suggestions": [
                    "Suggestion 1 to improve SEO",
                    "Suggestion 2 to improve SEO",
                    ...
                ]
            }}
            
            Ensure the meta title and description are compelling and include the main keyword.
            """
            
            # Use optimized service for cost-effective SEO generation
            seo_recommendations = optimized_openai_service.generate_seo_metadata(selected_topic, content)
            
            # Save recommendations.json
            # Ensure we're writing JSON format to the file
            with open(os.path.join(run_path, "recommendations.json"), 'w') as f:
                if isinstance(seo_recommendations, dict):
                    json.dump(seo_recommendations, f, indent=2)
                else:
                    f.write(seo_recommendations)
            
            # If WordPress integration is enabled, create a publish.json stub
            if "wordpress" in config and config["wordpress"].get("url"):
                publish_data = {
                    "status": "pending",
                    "wordpress_url": config["wordpress"].get("url"),
                    "scheduled_time": datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                }
                
                # Save publish.json
                with open(os.path.join(run_path, "publish.json"), 'w') as f:
                    json.dump(publish_data, f, indent=2)
            
            # Create results.json with overall status
            results_data = {
                "status": "completed",
                "timestamp": datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                "topic": selected_topic,
                "theme": theme,
                "content_length": len(content.split()),
                "has_seo_recommendations": True,
                "wordpress_publishing": "pending" if "wordpress" in config else "disabled",
                "image_generation": {
                    "enabled": image_enabled,
                    "count": image_count,
                    "style": image_style,
                    "used_gpt4o_descriptions": use_gpt4o_descriptions,
                    "featured_image": featured_image_path is not None,
                    "section_images": enable_section_images
                }
            }
            
            # Save results.json
            with open(os.path.join(run_path, "results.json"), 'w') as f:
                json.dump(results_data, f, indent=2)
            
            flash(f"Content for '{selected_topic}' has been successfully generated!", "success")
            
        except Exception as e:
            logger.error(f"Error generating content: {str(e)}")
            flash(f"Error generating content: {str(e)}", "danger")
        
    except Exception as e:
        logger.error(f"Error in content generation process: {str(e)}")
        flash(f"Error in content generation process: {str(e)}", "danger")
    
    return redirect(url_for('blog_detail', blog_id=blog_id))

@app.route('/api/blogs')
def get_blogs():
    """API endpoint to get all blogs"""
    blogs = []
    try:
        # Get blogs from data/blogs folder
        blogs_path = os.path.join("data", "blogs")
        if os.path.exists(blogs_path):
            blog_folders = [f for f in os.listdir(blogs_path) if os.path.isdir(os.path.join(blogs_path, f))]
            
            for blog_id in blog_folders:
                config_path = os.path.join(blogs_path, blog_id, "config.json")
                
                if os.path.exists(config_path):
                    with open(config_path, 'r') as f:
                        config = json.load(f)
                    
                    # Count content items
                    content_count = 0
                    runs_path = os.path.join(blogs_path, blog_id, "runs")
                    if os.path.exists(runs_path):
                        run_folders = [f for f in os.listdir(runs_path) if os.path.isdir(os.path.join(runs_path, f))]
                        
                        for run_id in run_folders:
                            content_path = os.path.join(runs_path, run_id, "content.md")
                            if os.path.exists(content_path):
                                content_count += 1
                    
                    # Add blog to the list
                    blogs.append({
                        'id': blog_id,
                        'name': config.get('name', 'Unnamed Blog'),
                        'theme': config.get('theme', 'No theme'),
                        'created_at': config.get('created_at', 'Unknown'),
                        'is_active': config.get('is_active', True),
                        'frequency': config.get('frequency', 'unknown'),
                        'content_count': content_count,
                        'wordpress_connected': 'wordpress' in config and config['wordpress'].get('connected', False)
                    })
    except Exception as e:
        logger.error(f"Error getting blog data: {str(e)}")
    
    return jsonify(blogs)

@app.route('/api/blogs/<blog_id>')
def get_blog_details(blog_id):
    """API endpoint to get details for a specific blog"""
    try:
        logger.info(f"Fetching details for blog ID: {blog_id}")
        
        # Use the existing get_blog_by_id helper function
        blog = get_blog_by_id(blog_id)
        
        if not blog:
            logger.warning(f"Blog with ID {blog_id} not found")
            return jsonify({"error": "Blog not found"}), 404
        
        # Get additional details like content count
        content_count = 0
        runs_path = os.path.join("data", "blogs", blog_id, "runs")
        if os.path.exists(runs_path):
            run_folders = [f for f in os.listdir(runs_path) if os.path.isdir(os.path.join(runs_path, f))]
            for run_id in run_folders:
                content_path = os.path.join(runs_path, run_id, "content.md")
                if os.path.exists(content_path):
                    content_count += 1
        
        # Add content count to the response
        blog['content_count'] = content_count
        
        logger.info(f"Successfully retrieved blog: {blog.get('name', 'Unknown')}")
        return jsonify(blog)
        
    except Exception as e:
        logger.error(f"Error getting blog details for {blog_id}: {str(e)}")
        return jsonify({"error": f"Failed to get blog details: {str(e)}"}), 500

@app.route('/content_research')
def content_research():
    """Content research tools page for scraping and analysis"""
    return render_template('research_tools.html')

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

@app.route('/api/scrape-url', methods=['POST'])
def scrape_url():
    """API endpoint to scrape content from a URL"""
    if not web_scraper_service:
        return jsonify({
            "success": False,
            "message": "Web scraper service is not available"
        }), 500
    
    # Get URL, scraping method, and blog_id from request
    data = request.json
    url = data.get('url')
    method = data.get('method', 'general')
    blog_id = data.get('blog_id')
    
    if not url:
        return jsonify({
            "success": False,
            "message": "URL is required"
        }), 400
    
    try:
        # Get blog context if specified
        blog_context = None
        if blog_id:
            try:
                blog_data = get_blog_by_id(blog_id)
                if blog_data:
                    blog_context = {
                        'name': blog_data.get('name', ''),
                        'theme': blog_data.get('theme', ''),
                        'topics': blog_data.get('topics', []),
                        'audience': blog_data.get('audience', ''),
                        'tone': blog_data.get('tone', 'informative')
                    }
                    logger.info(f"Using blog context for URL scraping: {blog_context['name']}")
            except Exception as e:
                logger.warning(f"Could not get blog context for ID {blog_id}: {str(e)}")
                # Continue without context
        
        # Get content from URL based on method and blog context
        logger.info(f"Scraping URL: {url} using method: {method}")
        
        if method == 'article':
            # Use newspaper3k for article extraction (with or without context)
            if blog_context:
                content = web_scraper_service.extract_with_newspaper_and_context(url, blog_context)
                logger.info(f"Extracted article with blog context: {blog_context['name']}")
            else:
                content = web_scraper_service.extract_with_newspaper(url)
        else:
            # Use trafilatura for general content extraction (with or without context)
            if blog_context:
                content = web_scraper_service.extract_content_from_url_with_context(url, blog_context)
                logger.info(f"Extracted content with blog context: {blog_context['name']}")
            else:
                content = web_scraper_service.extract_content_from_url(url)
        
        # Add extraction timestamp
        if content:
            content['extracted_at'] = datetime.datetime.now().isoformat()
        
        return jsonify({
            "success": True,
            "data": content,
            "used_context_aware_method": blog_context is not None,
            "blog_name": blog_context.get("name") if blog_context else None
        })
        
    except Exception as e:
        logger.error(f"Error scraping URL {url}: {str(e)}")
        return jsonify({
            "success": False,
            "message": f"Failed to scrape URL: {str(e)}"
        }), 500

@app.route('/api/research-topic', methods=['POST'])
def research_topic_api():
    """API endpoint to research a topic using the web scraper service"""
    if not web_scraper_service:
        return jsonify({
            "success": False,
            "message": "Web scraper service is not available"
        }), 500
    
    # Get topic and number of sources from request
    data = request.json
    topic = data.get('topic')
    num_sources = data.get('num_sources', 3)
    blog_id = data.get('blog_id')
    
    if not topic:
        return jsonify({
            "success": False,
            "message": "Topic is required"
        }), 400
    
    try:
        # If blog context is provided, get the blog info
        blog_context = None
        if blog_id:
            try:
                # Get blog data to provide context
                blog = get_blog_by_id(blog_id)
                if blog:
                    # Create a context dictionary with relevant blog information
                    blog_context = {
                        "name": blog.get("name", ""),
                        "theme": blog.get("theme"),
                        "topics": blog.get("topics", []),
                        "description": blog.get("description", ""),
                        "tone": blog.get("tone", "informative"),
                        "audience": blog.get("audience", "general")
                    }
                    logger.info(f"Researching topic '{topic}' within blog context: {blog.get('name')}")
            except Exception as e:
                logger.warning(f"Error getting blog context for ID {blog_id}: {str(e)}")
                # Continue without context if blog info can't be loaded
        
        # Research the topic with optional blog context
        logger.info(f"Researching topic: {topic} with {num_sources} sources")
        research_data = web_scraper_service.research_topic(
            topic, 
            num_sources=num_sources,
            context=blog_context
        )
        
        # Add research timestamp
        research_data['research_date'] = datetime.datetime.now().isoformat()
        
        # Try to generate a wordcloud if possible
        try:
            if web_scraper_service.can_generate_wordcloud() and research_data.get('articles'):
                wordcloud_path = web_scraper_service.generate_wordcloud(
                    [a.get('content', '') for a in research_data.get('articles', []) if a.get('content')]
                )
                if wordcloud_path:
                    research_data['wordcloud_path'] = wordcloud_path
        except Exception as wc_error:
            logger.warning(f"Error generating wordcloud: {str(wc_error)}")
        
        return jsonify({
            "success": True,
            "data": research_data,
            "used_context_aware_method": blog_context is not None,
            "blog_name": blog_context.get("name") if blog_context else None
        })
        
    except Exception as e:
        logger.error(f"Error researching topic {topic}: {str(e)}")
        return jsonify({
            "success": False,
            "message": f"Failed to research topic: {str(e)}"
        }), 500

@app.route('/api/trending-topics-new', methods=['GET'])
def trending_topics_api_new():
    """Updated API endpoint to get trending topics"""
    if not web_scraper_service:
        return jsonify({
            "success": False,
            "message": "Web scraper service is not available"
        }), 500
    
    # Get category, limit and blog_id from request
    category = request.args.get('category')
    limit = request.args.get('limit', 10, type=int)
    blog_id = request.args.get('blog_id')
    
    try:
        # If blog context is provided, get the blog info
        blog_context = None
        if blog_id:
            try:
                # Get blog data to provide context
                blog = get_blog_by_id(blog_id)
                if blog:
                    # Create a context dictionary with relevant blog information
                    blog_context = {
                        "name": blog.get("name", ""),
                        "theme": blog.get("theme"),
                        "topics": blog.get("topics", []),
                        "description": blog.get("description", ""),
                        "tone": blog.get("tone", "informative"),
                        "audience": blog.get("audience", "general")
                    }
                    logger.info(f"Getting trending topics within blog context: {blog.get('name')}")
            except Exception as e:
                logger.warning(f"Error getting blog context for ID {blog_id}: {str(e)}")
                # Continue without context if blog info can't be loaded
        
        # Get trending topics with optional blog context - use the context-aware method when a blog is selected
        logger.info(f"Getting trending topics for category: {category} with limit: {limit}")
        if blog_context:
            logger.info(f"Using context-aware trending topics method for blog: {blog_context.get('name')}")
            topics = web_scraper_service.get_trending_topics_with_context(
                category=category, 
                limit=limit,
                blog_context=blog_context
            )
        else:
            topics = web_scraper_service.get_trending_topics(
                category=category, 
                limit=limit
            )
        
        return jsonify({
            "success": True,
            "data": topics,
            "used_context_aware_method": blog_context is not None,
            "blog_name": blog_context.get("name") if blog_context else None
        })
        
    except Exception as e:
        logger.error(f"Error getting trending topics: {str(e)}")
        return jsonify({
            "success": False,
            "message": f"Failed to get trending topics: {str(e)}"
        }), 500

@app.route('/api/rss-feed', methods=['POST']) 
def rss_feed_api():
    """API endpoint to fetch and parse an RSS feed"""
    if not web_scraper_service:
        return jsonify({
            "success": False,
            "message": "Web scraper service is not available"
        }), 500
    
    # Get feed URL, limit, and blog_id from request
    data = request.json
    feed_url = data.get('feed_url')
    limit = data.get('limit', 10)
    blog_id = data.get('blog_id')
    
    if not feed_url:
        return jsonify({
            "success": False,
            "message": "Feed URL is required"
        }), 400
    
    try:
        # Get blog context if specified
        blog_context = None
        if blog_id:
            try:
                blog_data = get_blog_by_id(blog_id)
                if blog_data:
                    blog_context = {
                        'name': blog_data.get('name', ''),
                        'theme': blog_data.get('theme', ''),
                        'topics': blog_data.get('topics', []),
                        'audience': blog_data.get('audience', ''),
                        'tone': blog_data.get('tone', 'informative')
                    }
                    logger.info(f"Using blog context for RSS feed parsing: {blog_context['name']}")
            except Exception as e:
                logger.warning(f"Could not get blog context for ID {blog_id}: {str(e)}")
        
        # Parse the RSS feed with or without context
        logger.info(f"Parsing RSS feed: {feed_url} with limit: {limit}")
        if blog_context:
            entries = web_scraper_service.fetch_rss_feed_with_context(feed_url, limit, blog_context)
            logger.info(f"Parsed RSS feed with blog context filtering")
        else:
            entries = web_scraper_service.fetch_rss_feed(feed_url, limit)
        
        return jsonify({
            "success": True,
            "data": entries,
            "used_context_aware_method": blog_context is not None,
            "blog_name": blog_context.get("name") if blog_context else None
        })
        
    except Exception as e:
        logger.error(f"Error parsing RSS feed {feed_url}: {str(e)}")
        return jsonify({
            "success": False,
            "message": f"Failed to parse RSS feed: {str(e)}"
        }), 500

@app.route('/api/generate_outline', methods=['POST'])
def generate_outline():
    """API endpoint to generate a content outline"""
    data = request.json
    topic = data.get('topic', '')
    theme = data.get('theme', '')
    
    if not topic or not theme:
        return jsonify({"error": "Topic and theme are required"}), 400
    
    try:
        # Use optimized service for cost-effective outline generation
        outline = optimized_openai_service.generate_outline(topic, theme)
        return jsonify(outline)
    except Exception as e:
        logger.error(f"Error generating outline: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route('/blog/<blog_id>/content/<run_id>')
def view_content(blog_id, run_id):
    """View content for a specific run"""
    try:
        # Make sure we're using the correct blog_id and run_id
        # Get blog configuration
        blog_path = os.path.join("data/blogs", blog_id)
        config_path = os.path.join(blog_path, "config.json")
        
        logger.debug(f"Viewing content for blog_id: {blog_id}, run_id: {run_id}")
        logger.debug(f"Config path: {config_path}")
        
        if not os.path.exists(config_path):
            flash(f"Blog configuration not found for ID: {blog_id}", "danger")
            return redirect(url_for('index'))
        
        with open(config_path, 'r') as f:
            config = json.load(f)
        
        # Get run data
        run_path = os.path.join(blog_path, "runs", run_id)
        content_path = os.path.join(run_path, "content.md")
        
        if not os.path.exists(content_path):
            flash(f"Content not found for run ID: {run_id}", "danger")
            return redirect(url_for('blog_detail', blog_id=blog_id))
        
        # Read content file
        with open(content_path, 'r') as f:
            content = f.read()
        
        # Extract metadata from frontmatter if present
        featured_image = None
        title = run_id
        
        # Check if content has frontmatter (starts with ---)
        if content.startswith('---'):
            try:
                # Find the end of frontmatter
                end_frontmatter_pos = content.find('---', 3)
                if end_frontmatter_pos > 0:
                    # Extract frontmatter content
                    frontmatter = content[3:end_frontmatter_pos].strip()
                    frontmatter_lines = frontmatter.split('\n')
                    
                    # Parse frontmatter lines
                    for line in frontmatter_lines:
                        if ':' in line:
                            key, value = line.split(':', 1)
                            key = key.strip()
                            value = value.strip().strip('"\'')
                            
                            if key == 'title':
                                title = value
                            elif key == 'featured_image':
                                featured_image = value
            except Exception as e:
                logger.warning(f"Error parsing frontmatter: {str(e)}")
        
        # If no title found in frontmatter, extract from content (assuming first line is a markdown heading)
        if title == run_id:
            lines = content.strip().split('\n')
            title = lines[0].strip('# ') if lines and lines[0].startswith('# ') else run_id
        
        # Calculate word count and reading time
        word_count = len(content.split())
        reading_time = max(1, round(word_count / 200))  # Assuming 200 words per minute reading speed
        
        # Parse date from run_id (assuming format YYYYMMDD_HHMMSS_XXX)
        date_str = None
        if '_' in run_id:
            try:
                date_part = run_id.split('_')[0]
                date_str = f"{date_part[:4]}-{date_part[4:6]}-{date_part[6:8]}"
            except:
                date_str = "Unknown Date"
        
        # Try to load research.json if exists
        research = None
        research_path = os.path.join(run_path, "research.json")
        if os.path.exists(research_path):
            with open(research_path, 'r') as f:
                research = json.load(f)
        
        # Try to load recommendations.json if exists
        recommendations = None
        recommendations_path = os.path.join(run_path, "recommendations.json")
        if os.path.exists(recommendations_path):
            with open(recommendations_path, 'r') as f:
                recommendations = json.load(f)
        
        # Try to load publish.json if exists
        publish = None
        publish_path = os.path.join(run_path, "publish.json")
        post_url = None
        status = 'generated'
        if os.path.exists(publish_path):
            with open(publish_path, 'r') as f:
                publish = json.load(f)
            status = publish.get('status', 'pending')
            post_url = publish.get('url')
        
        # Try to load results.json if exists
        results = None
        results_path = os.path.join(run_path, "results.json")
        if os.path.exists(results_path):
            with open(results_path, 'r') as f:
                results = json.load(f)
            status = 'completed'
        
        # Try to load promote.json if exists (social media promotion data)
        promote = None
        promote_path = os.path.join(run_path, "promote.json")
        if os.path.exists(promote_path):
            try:
                with open(promote_path, 'r') as f:
                    promote = json.load(f)
                logger.debug(f"Loaded social media promotion data for {blog_id}/{run_id}")
            except Exception as e:
                logger.warning(f"Error loading promote.json: {str(e)}")
        
        # Convert markdown to HTML for preview
        try:
            import markdown
            content_html = markdown.markdown(content, extensions=['extra', 'codehilite'])
        except ImportError:
            # If markdown package is not available, use a simple conversion
            content_html = content.replace('\n', '<br>').replace('# ', '<h1>').replace('## ', '<h2>').replace('### ', '<h3>')
        
        return render_template('content_view.html',
                              blog_id=blog_id,
                              blog_name=config.get('name', 'Unnamed Blog'),
                              run_id=run_id,
                              title=title,
                              content=content,
                              content_html=content_html,
                              theme=config.get('theme', ''),
                              date=date_str or "Unknown Date",
                              word_count=word_count,
                              reading_time=reading_time,
                              research=research,
                              recommendations=recommendations,
                              publish=publish,
                              results=results,
                              promote=promote,
                              status=status,
                              post_url=post_url,
                              featured_image=featured_image)
    
    except Exception as e:
        logger.error(f"Error loading content for {blog_id}/{run_id}: {str(e)}")
        flash(f"Error loading content: {str(e)}", "danger")
        return redirect(url_for('blog_detail', blog_id=blog_id))

@app.route('/blog/<blog_id>/content/<run_id>/edit', methods=['POST'])
def edit_content(blog_id, run_id):
    """Edit content for a specific run"""
    try:
        # Get blog configuration
        blog_path = os.path.join("data/blogs", blog_id)
        config_path = os.path.join(blog_path, "config.json")
        
        if not os.path.exists(config_path):
            flash(f"Blog configuration not found for ID: {blog_id}", "danger")
            return redirect(url_for('index'))
        
        # Get run data path
        run_path = os.path.join(blog_path, "runs", run_id)
        content_path = os.path.join(run_path, "content.md")
        
        if not os.path.exists(content_path):
            flash(f"Content not found for run ID: {run_id}", "danger")
            return redirect(url_for('blog_detail', blog_id=blog_id))
        
        # Get edited content from form
        new_content = request.form.get('content', '')
        republish = request.form.get('republish') == 'on'
        
        # Create a backup of the original content
        backup_path = os.path.join(run_path, "content.md.bak")
        if not os.path.exists(backup_path):
            shutil.copy2(content_path, backup_path)
            logger.info(f"Created backup of original content at {backup_path}")
        
        # Save the edited content
        with open(content_path, 'w') as f:
            f.write(new_content)
        
        logger.info(f"Content updated for {blog_id}/{run_id}")
        
        # If republish is requested, update the publish.json file 
        # and call the publishing function (if it exists)
        if republish:
            publish_path = os.path.join(run_path, "publish.json")
            if os.path.exists(publish_path):
                # Get the existing publish data
                with open(publish_path, 'r') as f:
                    publish_data = json.load(f)
                
                # Update the publish timestamp
                publish_data['updated_at'] = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                publish_data['status'] = 'updated'
                
                # Save the updated publish data
                with open(publish_path, 'w') as f:
                    json.dump(publish_data, f, indent=2)
                
                # In a real scenario, here we would call the actual republish function,
                # but for demo purposes, we'll just update the publish.json file
                
                # Create a new promote.json file to trigger social media promotion
                promote_path = os.path.join(run_path, "promote.json")
                
                # Check for social media promotion if republishing
                try:
                    # Get blog config to check if social promotion is enabled
                    with open(config_path, 'r') as f:
                        blog_config = json.load(f)
                    
                    social_enabled = blog_config.get('social_media', {}).get('enabled', False)
                    
                    # If social promotion is enabled, promote the content
                    if social_enabled and social_media_service:
                        # Extract content data
                        content_data = {}
                        # Try to get title from content
                        with open(content_path, 'r') as f:
                            content_text = f.read()
                            lines = content_text.strip().split('\n')
                            if lines and lines[0].startswith('# '):
                                content_data['title'] = lines[0][2:].strip()
                            
                            # Create a short excerpt
                            paragraphs = [line for line in lines if line.strip() and not line.startswith('#')]
                            if paragraphs:
                                content_data['excerpt'] = paragraphs[0][:300]
                        
                        # Promote the content
                        promote_result = social_media_service.promote_content(blog_id, run_id, content_data, publish_data)
                        
                        # Save the promotion result
                        with open(promote_path, 'w') as f:
                            json.dump(promote_result, f, indent=2)
                        
                        logger.info(f"Content auto-promoted on social media: {blog_id}/{run_id}")
                        flash("Content has been updated, republished, and promoted on social media", "success")
                    else:
                        reason = "Social media promotion is disabled for this blog" if not social_enabled else "Social media service is not available"
                        logger.info(f"Content marked for republishing ({reason}): {blog_id}/{run_id}")
                        
                        # Create a skipped promote.json file
                        if not social_enabled:
                            promote_result = {
                                "status": "skipped",
                                "timestamp": datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                                "reason": reason
                            }
                            with open(promote_path, 'w') as f:
                                json.dump(promote_result, f, indent=2)
                        
                        flash("Content has been updated and marked for republishing", "success")
                except Exception as e:
                    logger.warning(f"Error promoting content on social media: {str(e)}")
                    
                    # Create an error promote.json file
                    promote_result = {
                        "status": "error",
                        "timestamp": datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                        "error": str(e),
                        "reason": "Error occurred during social media promotion"
                    }
                    with open(promote_path, 'w') as f:
                        json.dump(promote_result, f, indent=2)
                    
                    flash("Content has been updated and marked for republishing (social promotion failed)", "success")
            else:
                # Create a new publish.json file
                publish_data = {
                    "status": "pending",
                    "created_at": datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                }
                
                with open(publish_path, 'w') as f:
                    json.dump(publish_data, f, indent=2)
                
                logger.info(f"New publish request created: {blog_id}/{run_id}")
                flash("Content has been updated and scheduled for publishing", "success")
        else:
            flash("Content has been updated successfully", "success")
        
        return redirect(url_for('view_content', blog_id=blog_id, run_id=run_id))
    
    except Exception as e:
        logger.error(f"Error updating content for {blog_id}/{run_id}: {str(e)}")
        flash(f"Error updating content: {str(e)}", "danger")
        return redirect(url_for('view_content', blog_id=blog_id, run_id=run_id))

@app.route('/analytics')
def analytics_dashboard():
    """
    Display analytics dashboard for traffic, engagement, and ad clicks
    """
    try:
        # Get all blogs from the config service
        blogs = []
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
                        'name': blog_config.get('name', 'Unnamed Blog')
                    })
            except Exception as e:
                logger.error(f"Error loading blog config for {blog_id}: {str(e)}")
        
        # Prepare custom data sources
        google_analytics_enabled = os.environ.get("GOOGLE_ANALYTICS_API_KEY") is not None
        adsense_enabled = os.environ.get("GOOGLE_ADSENSE_API_KEY") is not None
        search_console_enabled = os.environ.get("GOOGLE_SEARCH_CONSOLE_API_KEY") is not None
        wordpress_analytics_enabled = os.environ.get("WORDPRESS_ANALYTICS_ENABLED", "").lower() == "true"
        
        return render_template('analytics_dashboard.html', 
                              blogs=blogs,
                              google_analytics_enabled=google_analytics_enabled,
                              adsense_enabled=adsense_enabled,
                              search_console_enabled=search_console_enabled,
                              wordpress_analytics_enabled=wordpress_analytics_enabled)
    except Exception as e:
        logger.error(f"Error loading analytics dashboard: {str(e)}")
        flash(f"Error loading analytics dashboard: {str(e)}", "danger")
        return redirect(url_for('index'))

@app.route('/usage')
def usage_dashboard():
    """
    Display usage and billing information for all services
    """
    # Get global service status
    global_status = billing_service.get_all_services_status()
    
    # Get blog-specific service status
    blogs = []
    blog_data_path = "data/blogs"
    storage_service.ensure_local_directory(blog_data_path)
    
    try:
        local_blog_folders = [f for f in os.listdir(blog_data_path) if os.path.isdir(os.path.join(blog_data_path, f))]
        
        for blog_id in local_blog_folders:
            try:
                blog_config_path = os.path.join(blog_data_path, blog_id, "config.json")
                if os.path.exists(blog_config_path):
                    with open(blog_config_path, 'r') as f:
                        blog_config = json.load(f)
                    
                    # Check for blog-specific credentials
                    has_custom_credentials = False
                    if 'integrations' in blog_config:
                        has_custom_credentials = any([
                            'openai_api_key' in blog_config['integrations'],
                            'wordpress_app_password' in blog_config['integrations'],
                            'twitter_api_key' in blog_config['integrations'],
                            'linkedin_api_key' in blog_config['integrations'],
                            'facebook_api_key' in blog_config['integrations']
                        ])
                    
                    blogs.append({
                        'id': blog_id,
                        'name': blog_config.get('name', 'Unnamed Blog'),
                        'has_custom_credentials': has_custom_credentials,
                        'config': blog_config
                    })
            except Exception as e:
                logger.error(f"Error loading blog config for {blog_id}: {str(e)}")
    except Exception as e:
        logger.error(f"Error listing blog configurations: {str(e)}")
    
    return render_template('usage_dashboard.html', 
                          global_status=global_status, 
                          blogs=blogs)

@app.route('/api/usage/global')
@app.route('/api/global/usage')
def api_global_usage():
    """API endpoint to get global usage and billing information"""
    try:
        # Get global usage data from billing service
        global_status = billing_service.get_all_services_status()
        
        # Get all blogs and their usage
        blog_data_path = "data/blogs"
        blogs_info = []
        
        if os.path.exists(blog_data_path):
            # List all blog folders
            local_blog_folders = [f for f in os.listdir(blog_data_path) 
                                 if os.path.isdir(os.path.join(blog_data_path, f))]
            
            for blog_id in local_blog_folders:
                try:
                    blog_config_path = os.path.join(blog_data_path, blog_id, "config.json")
                    usage_path = os.path.join(blog_data_path, blog_id, "usage.json")
                    
                    blog_info = {
                        "id": blog_id,
                        "name": "Unnamed Blog",
                        "theme": "Unknown",
                        "content_count": 0,
                        "images_count": 0,
                        "published_count": 0,
                        "last_generated": None,
                        "total_cost": 0.0
                    }
                    
                    # Load blog config if exists
                    if os.path.exists(blog_config_path):
                        with open(blog_config_path, 'r') as f:
                            blog_config = json.load(f)
                            blog_info["name"] = blog_config.get("name", "Unnamed Blog")
                            blog_info["theme"] = blog_config.get("theme", {}).get("name", "Unknown")
                    
                    # Load usage data if exists
                    if os.path.exists(usage_path):
                        with open(usage_path, 'r') as f:
                            usage_data = json.load(f)
                            blog_info["content_count"] = usage_data.get("content_count", 0)
                            blog_info["images_count"] = usage_data.get("images_count", 0)
                            blog_info["published_count"] = usage_data.get("published_count", 0)
                            blog_info["last_generated"] = usage_data.get("last_generated", None)
                            blog_info["total_cost"] = usage_data.get("total_cost", 0.0)
                    
                    blogs_info.append(blog_info)
                    
                except Exception as e:
                    logger.error(f"Error loading blog data for {blog_id}: {str(e)}")
        
        # Add blogs to the response
        global_status["blogs"] = blogs_info
        
        # Add total counts
        global_status["total_blogs"] = len(blogs_info)
        global_status["total_content"] = sum(blog.get("content_count", 0) for blog in blogs_info)
        global_status["total_images"] = sum(blog.get("images_count", 0) for blog in blogs_info)
        global_status["total_published"] = sum(blog.get("published_count", 0) for blog in blogs_info)
        
        return jsonify(global_status)
    except Exception as e:
        logger.error(f"Error retrieving global usage data: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/usage/blog/<blog_id>')
def api_blog_usage(blog_id):
    """API endpoint to get blog-specific usage and billing information"""
    try:
        blog_config_path = os.path.join("data/blogs", blog_id, "config.json")
        if not os.path.exists(blog_config_path):
            return jsonify({"error": f"Blog {blog_id} not found"}), 404
        
        with open(blog_config_path, 'r') as f:
            blog_config = json.load(f)
        
        blog_status = billing_service.get_all_services_status(blog_config)
        return jsonify(blog_status)
    except Exception as e:
        logger.error(f"Error retrieving usage data for blog {blog_id}: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/blog/<blog_id>/credentials', methods=['POST'])
def update_blog_credentials(blog_id):
    """API endpoint to update blog-specific integration credentials"""
    try:
        blog_config_path = os.path.join("data/blogs", blog_id, "config.json")
        if not os.path.exists(blog_config_path):
            return jsonify({"error": f"Blog {blog_id} not found"}), 404
        
        # Load the current config
        with open(blog_config_path, 'r') as f:
            blog_config = json.load(f)
        
        # Get credential data from request
        data = request.json
        if not data:
            return jsonify({"error": "No data provided"}), 400
        
        # Initialize integrations section if it doesn't exist
        if 'integrations' not in blog_config:
            blog_config['integrations'] = {}
        
        # Update credentials
        for key, value in data.items():
            if value:  # Only update if a value is provided
                blog_config['integrations'][key] = value
            elif key in blog_config['integrations']:
                # Remove the key if value is empty
                del blog_config['integrations'][key]
        
        # Save the updated config
        with open(blog_config_path, 'w') as f:
            json.dump(blog_config, f, indent=2)
        
        return jsonify({"status": "success", "message": "Credentials updated successfully"})
    except Exception as e:
        logger.error(f"Error updating credentials for blog {blog_id}: {str(e)}")
        return jsonify({"error": str(e)}), 500
        
# Analytics API Endpoints
@app.route('/api/analytics/summary')
def api_analytics_summary():
    """API endpoint to get analytics summary for a blog or all blogs"""
    try:
        blog_id = request.args.get('blog_id', 'all')
        period = request.args.get('period', 'month')
        
        if blog_id == 'all':
            # Get analytics for all blogs
            blogs_summary = {}
            blog_ids = analytics_service._get_all_blog_ids()
            
            for bid in blog_ids:
                blogs_summary[bid] = analytics_service.get_analytics_summary(bid, period)
            
            # Aggregate the data
            total_views = sum(data.get('total_views', 0) for data in blogs_summary.values())
            total_engagements = sum(data.get('total_engagements', 0) for data in blogs_summary.values())
            total_ad_clicks = sum(data.get('total_ad_clicks', 0) for data in blogs_summary.values())
            estimated_revenue = sum(data.get('estimated_revenue', 0.0) for data in blogs_summary.values())
            
            # Combine top posts
            all_top_posts = []
            for bid, data in blogs_summary.items():
                for post in data.get('top_posts', []):
                    post['blog_id'] = bid
                    all_top_posts.append(post)
            
            # Sort by views (descending)
            all_top_posts.sort(key=lambda x: x.get('views', 0), reverse=True)
            
            # Combine top referrers
            all_referrers = {}
            for data in blogs_summary.values():
                for referrer in data.get('top_referrers', []):
                    ref = referrer.get('referrer', 'unknown')
                    count = referrer.get('count', 0)
                    if ref in all_referrers:
                        all_referrers[ref] += count
                    else:
                        all_referrers[ref] = count
            
            top_referrers = [{"referrer": ref, "count": count} for ref, count in all_referrers.items()]
            top_referrers.sort(key=lambda x: x['count'], reverse=True)
            
            # Combine traffic by country and device
            traffic_by_country = {}
            traffic_by_device = {}
            
            for data in blogs_summary.values():
                # Combine country data
                for country, count in data.get('traffic_by_country', {}).items():
                    if country in traffic_by_country:
                        traffic_by_country[country] += count
                    else:
                        traffic_by_country[country] = count
                
                # Combine device data
                for device, count in data.get('traffic_by_device', {}).items():
                    if device in traffic_by_device:
                        traffic_by_device[device] += count
                    else:
                        traffic_by_device[device] = count
            
            return jsonify({
                'total_views': total_views,
                'total_engagements': total_engagements,
                'total_ad_clicks': total_ad_clicks,
                'estimated_revenue': estimated_revenue,
                'top_posts': all_top_posts[:10],  # Top 10 posts
                'top_referrers': top_referrers[:10],  # Top 10 referrers
                'traffic_by_country': traffic_by_country,
                'traffic_by_device': traffic_by_device,
                'period': period
            })
        else:
            # Get analytics for a specific blog
            summary = analytics_service.get_analytics_summary(blog_id, period)
            return jsonify(summary)
        
    except Exception as e:
        logger.error(f"Error getting analytics summary: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/analytics/google_analytics')
def api_google_analytics():
    """API endpoint to get Google Analytics data for a blog"""
    try:
        blog_id = request.args.get('blog_id')
        period = request.args.get('period', 'month')
        
        if not blog_id or blog_id == 'all':
            # Get data for all blogs (example)
            return jsonify({
                "enabled": os.environ.get("GOOGLE_ANALYTICS_API_KEY") is not None,
                "error": "Please select a specific blog for Google Analytics data"
            })
        
        # Get Google Analytics data for the specific blog
        ga_data = analytics_service.get_google_analytics_data(blog_id, period)
        return jsonify(ga_data)
        
    except Exception as e:
        logger.error(f"Error getting Google Analytics data: {str(e)}")
        return jsonify({"error": str(e), "enabled": False}), 500

@app.route('/api/analytics/adsense')
def api_adsense():
    """API endpoint to get AdSense data for a blog"""
    try:
        blog_id = request.args.get('blog_id')
        period = request.args.get('period', 'month')
        
        if not blog_id or blog_id == 'all':
            # Get data for all blogs (example)
            return jsonify({
                "enabled": os.environ.get("GOOGLE_ADSENSE_API_KEY") is not None,
                "error": "Please select a specific blog for AdSense data"
            })
        
        # Get AdSense data for the specific blog
        adsense_data = analytics_service.get_adsense_data(blog_id, period)
        return jsonify(adsense_data)
        
    except Exception as e:
        logger.error(f"Error getting AdSense data: {str(e)}")
        return jsonify({"error": str(e), "enabled": False}), 500

@app.route('/api/analytics/search_console')
def api_search_console():
    """API endpoint to get Search Console data for a blog"""
    try:
        blog_id = request.args.get('blog_id')
        period = request.args.get('period', 'month')
        
        if not blog_id or blog_id == 'all':
            # Get data for all blogs (example)
            return jsonify({
                "enabled": os.environ.get("GOOGLE_SEARCH_CONSOLE_API_KEY") is not None,
                "error": "Please select a specific blog for Search Console data"
            })
        
        # Get Search Console data for the specific blog
        search_console_data = analytics_service.get_search_console_data(blog_id, period)
        return jsonify(search_console_data)
        
    except Exception as e:
        logger.error(f"Error getting Search Console data: {str(e)}")
        return jsonify({"error": str(e), "enabled": False}), 500

@app.route('/api/analytics/wordpress')
def api_wordpress_analytics():
    """API endpoint to get WordPress analytics data for a blog"""
    try:
        blog_id = request.args.get('blog_id')
        
        if not blog_id or blog_id == 'all':
            # Get data for all blogs (example)
            return jsonify({
                "enabled": os.environ.get("WORDPRESS_ANALYTICS_ENABLED", "").lower() == "true",
                "error": "Please select a specific blog for WordPress analytics data"
            })
        
        # Get WordPress analytics data for the specific blog
        wordpress_data = analytics_service.get_wordpress_analytics(blog_id)
        return jsonify(wordpress_data)
        
    except Exception as e:
        logger.error(f"Error getting WordPress analytics data: {str(e)}")
        return jsonify({"error": str(e), "enabled": False}), 500

@app.route('/api/analytics/topic_performance')
def api_topic_performance():
    """API endpoint to get topic performance across blogs"""
    try:
        blog_id = request.args.get('blog_id', 'all')
        
        if blog_id == 'all':
            # Get performance for all topics across all blogs
            topic_performance = analytics_service.get_topic_performance()
        else:
            # Get performance for all topics in a specific blog
            topic_performance = analytics_service.get_topic_performance(blog_id)
        
        return jsonify(topic_performance)
        
    except Exception as e:
        logger.error(f"Error getting topic performance: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/analytics/seo_insights')
def api_seo_insights():
    """API endpoint to get SEO insights for content optimization"""
    try:
        blog_id = request.args.get('blog_id', 'all')
        
        if blog_id == 'all':
            # Get SEO insights across all blogs
            seo_insights = analytics_service.get_seo_insights()
        else:
            # Get SEO insights for a specific blog
            seo_insights = analytics_service.get_seo_insights(blog_id)
        
        return jsonify(seo_insights)
        
    except Exception as e:
        logger.error(f"Error getting SEO insights: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/analytics/configure_google_analytics', methods=['POST'])
def api_configure_google_analytics():
    """API endpoint to configure Google Analytics for a blog"""
    try:
        data = request.json
        blog_id = data.get('blog_id')
        property_id = data.get('property_id')
        measurement_id = data.get('measurement_id')
        
        if not property_id:
            return jsonify({"success": False, "error": "Property ID is required"}), 400
        
        if blog_id and blog_id != 'all':
            # Configure Google Analytics for a specific blog
            success = analytics_service.configure_google_analytics(blog_id, property_id, measurement_id)
        else:
            # Configure Google Analytics for all blogs (not implemented)
            return jsonify({"success": False, "error": "Configuration for all blogs not supported"}), 400
        
        return jsonify({"success": success})
        
    except Exception as e:
        logger.error(f"Error configuring Google Analytics: {str(e)}")
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/analytics/configure_adsense', methods=['POST'])
def api_configure_adsense():
    """API endpoint to configure AdSense for a blog"""
    try:
        data = request.json
        blog_id = data.get('blog_id')
        client_id = data.get('client_id')
        ad_units = data.get('ad_units', [])
        
        if not client_id:
            return jsonify({"success": False, "error": "Client ID is required"}), 400
        
        if blog_id and blog_id != 'all':
            # Configure AdSense for a specific blog
            success = analytics_service.configure_adsense(blog_id, client_id, ad_units)
        else:
            # Configure AdSense for all blogs (not implemented)
            return jsonify({"success": False, "error": "Configuration for all blogs not supported"}), 400
        
        return jsonify({"success": success})
        
    except Exception as e:
        logger.error(f"Error configuring AdSense: {str(e)}")
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/analytics/configure_search_console', methods=['POST'])
def api_configure_search_console():
    """API endpoint to configure Search Console for a blog"""
    try:
        data = request.json
        blog_id = data.get('blog_id')
        site_url = data.get('site_url')
        
        if not site_url:
            return jsonify({"success": False, "error": "Site URL is required"}), 400
        
        if blog_id and blog_id != 'all':
            # Configure Search Console for a specific blog
            success = analytics_service.configure_search_console(blog_id, site_url)
        else:
            # Configure Search Console for all blogs (not implemented)
            return jsonify({"success": False, "error": "Configuration for all blogs not supported"}), 400
        
        return jsonify({"success": success})
        
    except Exception as e:
        logger.error(f"Error configuring Search Console: {str(e)}")
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/analytics/page_view', methods=['POST'])
def api_record_page_view():
    """API endpoint to record a page view"""
    try:
        data = request.json
        blog_id = data.get('blog_id')
        post_id = data.get('post_id')
        view_data = data.get('data', {})
        
        if not blog_id or not post_id:
            return jsonify({"success": False, "error": "Blog ID and Post ID are required"}), 400
        
        success = analytics_service.record_page_view(blog_id, post_id, view_data)
        return jsonify({"success": success})
        
    except Exception as e:
        logger.error(f"Error recording page view: {str(e)}")
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/analytics/engagement', methods=['POST'])
def api_record_engagement():
    """API endpoint to record an engagement event"""
    try:
        data = request.json
        blog_id = data.get('blog_id')
        post_id = data.get('post_id')
        engagement_type = data.get('type')
        engagement_data = data.get('data', {})
        
        if not blog_id or not post_id or not engagement_type:
            return jsonify({"success": False, "error": "Blog ID, Post ID, and engagement type are required"}), 400
        
        success = analytics_service.record_engagement(blog_id, post_id, engagement_type, engagement_data)
        return jsonify({"success": success})
        
    except Exception as e:
        logger.error(f"Error recording engagement: {str(e)}")
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/analytics/ad_click', methods=['POST'])
def api_record_ad_click():
    """API endpoint to record an ad click"""
    try:
        data = request.json
        blog_id = data.get('blog_id')
        post_id = data.get('post_id')
        ad_data = data.get('data', {})
        
        if not blog_id or not post_id:
            return jsonify({"success": False, "error": "Blog ID and Post ID are required"}), 400
        
        success = analytics_service.record_ad_click(blog_id, post_id, ad_data)
        return jsonify({"success": success})
        
    except Exception as e:
        logger.error(f"Error recording ad click: {str(e)}")
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/blog/<blog_id>/social-media', methods=['POST'])
def update_blog_social_media(blog_id):
    """API endpoint to update blog-specific social media settings"""
    try:
        blog_config_path = os.path.join("data/blogs", blog_id, "config.json")
        if not os.path.exists(blog_config_path):
            return jsonify({"success": False, "message": f"Blog {blog_id} not found"}), 404
        
        # Load the current config
        with open(blog_config_path, 'r') as f:
            blog_config = json.load(f)
        
        # Get social media data from request
        data = request.json
        if not data or 'social_media' not in data:
            return jsonify({"success": False, "message": "No social media data provided"}), 400
        
        # Update social media settings
        blog_config['social_media'] = data['social_media']
        
        # Save the updated config
        with open(blog_config_path, 'w') as f:
            json.dump(blog_config, f, indent=2)
        
        return jsonify({
            "success": True, 
            "message": "Social media settings updated successfully",
            "data": blog_config['social_media']
        })
    except Exception as e:
        logger.error(f"Error updating social media settings for blog {blog_id}: {str(e)}")
        return jsonify({"success": False, "message": f"Error: {str(e)}"}), 500

@app.route('/api/global/credentials', methods=['POST'])
def update_global_credentials():
    """API endpoint to update global credentials"""
    try:
        data = request.json
        
        # Load global config file
        global_config_path = "data/global_config.json"
        
        # Create the config file if it doesn't exist
        if not os.path.exists(global_config_path):
            # Make sure the directory exists
            os.makedirs(os.path.dirname(global_config_path), exist_ok=True)
            
            # Initialize with empty configuration
            global_config = {
                "credentials": {}
            }
        else:
            # Load existing configuration
            with open(global_config_path, 'r') as f:
                global_config = json.load(f)
                
            # Initialize credentials section if it doesn't exist
            if "credentials" not in global_config:
                global_config["credentials"] = {}
        
        # Update credentials
        if "openai_api_key" in data and data["openai_api_key"]:
            global_config["credentials"]["openai_api_key"] = data["openai_api_key"]
        
        # Save the updated config
        with open(global_config_path, 'w') as f:
            json.dump(global_config, f, indent=2)
        
        # Reinitialize services with new credentials
        if "openai_api_key" in data and data["openai_api_key"]:
            # Update OpenAI service
            openai_service.set_api_key(data["openai_api_key"])
        
        return jsonify({"success": True, "message": "Global credentials updated successfully"})
    except Exception as e:
        logger.error(f"Error updating global credentials: {str(e)}")
        return jsonify({"success": False, "message": f"Error: {str(e)}"}), 500

@app.route('/api/global/social-media-credentials', methods=['POST'])
def update_social_media_credentials():
    """API endpoint to update global social media credentials"""
    try:
        data = request.json
        
        # Load global config file
        global_config_path = "data/global_config.json"
        
        # Create the config file if it doesn't exist
        if not os.path.exists(global_config_path):
            # Make sure the directory exists
            os.makedirs(os.path.dirname(global_config_path), exist_ok=True)
            
            # Initialize with empty configuration
            global_config = {
                "credentials": {}
            }
        else:
            # Load existing configuration
            with open(global_config_path, 'r') as f:
                global_config = json.load(f)
                
            # Initialize credentials section if it doesn't exist
            if "credentials" not in global_config:
                global_config["credentials"] = {}
        
        # Update social media credentials
        social_media_updated = False
        
        # Twitter
        if "twitter_api_key" in data and data["twitter_api_key"]:
            global_config["credentials"]["twitter_api_key"] = data["twitter_api_key"]
            social_media_updated = True
        
        # LinkedIn
        if "linkedin_api_key" in data and data["linkedin_api_key"]:
            global_config["credentials"]["linkedin_api_key"] = data["linkedin_api_key"]
            social_media_updated = True
        
        # Facebook
        if "facebook_api_key" in data and data["facebook_api_key"]:
            global_config["credentials"]["facebook_api_key"] = data["facebook_api_key"]
            social_media_updated = True
            
        # Reddit credentials
        if "reddit_client_id" in data and data["reddit_client_id"]:
            global_config["credentials"]["reddit_client_id"] = data["reddit_client_id"]
            social_media_updated = True
        if "reddit_client_secret" in data and data["reddit_client_secret"]:
            global_config["credentials"]["reddit_client_secret"] = data["reddit_client_secret"]
            social_media_updated = True
        if "reddit_username" in data and data["reddit_username"]:
            global_config["credentials"]["reddit_username"] = data["reddit_username"]
            social_media_updated = True
        if "reddit_password" in data and data["reddit_password"]:
            global_config["credentials"]["reddit_password"] = data["reddit_password"]
            social_media_updated = True
            
        # Medium credentials
        if "medium_integration_token" in data and data["medium_integration_token"]:
            global_config["credentials"]["medium_integration_token"] = data["medium_integration_token"]
            social_media_updated = True
        if "medium_author_id" in data and data["medium_author_id"]:
            global_config["credentials"]["medium_author_id"] = data["medium_author_id"]
            social_media_updated = True
        
        # Save the updated config
        with open(global_config_path, 'w') as f:
            json.dump(global_config, f, indent=2)
        
        # Reinitialize social media service if credentials were updated
        if social_media_updated:
            social_media_service.reload_credentials()
        
        return jsonify({"success": True, "message": "Social media credentials updated successfully"})
    except Exception as e:
        logger.error(f"Error updating social media credentials: {str(e)}")
        return jsonify({"success": False, "message": f"Error: {str(e)}"}), 500

@app.route('/api/scrape-url-legacy', methods=['POST'])
def scrape_url_legacy():
    """Legacy API endpoint to scrape content from a URL"""
    try:
        data = request.json
        if not data or 'url' not in data:
            return jsonify({"success": False, "message": "URL is required"}), 400
        
        url = data['url']
        logger.info(f"Scraping content from URL: {url}")
        
        # Check if web scraper service is available
        if not web_scraper_service:
            return jsonify({
                "success": False, 
                "message": "Web scraper service is not available"
            }), 500
        
        # Choose extraction method based on the type of content
        if data.get('method') == 'article':
            # Use newspaper3k for article extraction (better for news articles and blogs)
            content = web_scraper_service.extract_with_newspaper(url)
        else:
            # Use trafilatura for general content extraction (better for general websites)
            content = web_scraper_service.extract_content_from_url(url)
        
        if not content:
            return jsonify({
                "success": False, 
                "message": "Failed to extract content from the provided URL"
            }), 400
        
        return jsonify({
            "success": True, 
            "data": content
        })
    except Exception as e:
        logger.error(f"Error scraping URL: {str(e)}")
        return jsonify({"success": False, "message": f"Error: {str(e)}"}), 500

@app.route('/api/research-topic-legacy', methods=['POST'])
def research_topic_api_legacy():
    """Legacy API endpoint to research a topic using the web scraper service"""
    try:
        data = request.json
        if not data or 'topic' not in data:
            return jsonify({"success": False, "message": "Topic is required"}), 400
        
        topic = data['topic']
        num_sources = int(data.get('num_sources', 5))
        logger.info(f"Researching topic: {topic} with {num_sources} sources")
        
        # Check if web scraper service is available
        if not web_scraper_service:
            return jsonify({
                "success": False, 
                "message": "Web scraper service is not available"
            }), 500
        
        # Research the topic
        research_data = web_scraper_service.research_topic(topic, num_sources)
        
        if not research_data:
            return jsonify({
                "success": False, 
                "message": "Failed to research the provided topic"
            }), 400
        
        return jsonify({
            "success": True, 
            "data": research_data
        })
    except Exception as e:
        logger.error(f"Error researching topic: {str(e)}")
        return jsonify({"success": False, "message": f"Error: {str(e)}"}), 500

@app.route('/api/trending-topics', methods=['GET'])
def trending_topics_api():
    """API endpoint to get trending topics"""
    try:
        category = request.args.get('category')
        limit = int(request.args.get('limit', 10))
        
        # Check if web scraper service is available
        if not web_scraper_service:
            return jsonify({
                "success": False, 
                "message": "Web scraper service is not available"
            }), 500
        
        # Get trending topics
        topics = web_scraper_service.get_trending_topics(category, limit)
        
        return jsonify({
            "success": True, 
            "data": topics
        })
    except Exception as e:
        logger.error(f"Error getting trending topics: {str(e)}")
        return jsonify({"success": False, "message": f"Error: {str(e)}"}), 500

@app.route('/content-research', methods=['GET'])
def content_research_dash():
    """Content research tools page (dash version)"""
    # Get list of blogs for the blog context selector
    try:
        blogs_data = get_blogs()
        blogs = json.loads(blogs_data.data)
    except Exception as e:
        logger.error(f"Error getting blogs for research tools: {str(e)}")
        blogs = []
    
    return render_template('content_research.html', blogs=blogs)

@app.route('/scrape-url', methods=['POST'])
def scrape_url_page():
    """Handle form submission for URL scraping and display results"""
    try:
        url = request.form.get('url')
        method = request.form.get('method')
        blog_id = request.form.get('blog_id')  # Get the blog_id from the form
        
        if not url:
            flash("URL is required", "danger")
            return redirect(url_for('content_research'))
        
        logger.info(f"Scraping content from URL: {url} using method: {method}, blog_id: {blog_id}")
        
        # Check if web scraper service is available
        if not web_scraper_service:
            flash("Web scraper service is not available", "danger")
            return redirect(url_for('content_research'))
        
        # Get blog context if specified
        blog_context = None
        if blog_id:
            try:
                blog_data = get_blog_by_id(blog_id)
                if blog_data:
                    blog_context = {
                        'name': blog_data.get('name', ''),
                        'theme': blog_data.get('theme', ''),
                        'topics': blog_data.get('topics', []),
                        'audience': blog_data.get('audience', '')
                    }
                    logger.info(f"Using blog context for URL scraping: {blog_context['name']}")
            except Exception as e:
                logger.warning(f"Could not get blog context for ID {blog_id}: {str(e)}")
        
        # Choose extraction method based on the form input and apply blog context if available
        if method == 'newspaper':
            # Use newspaper3k for article extraction
            if blog_context:
                content_data = web_scraper_service.extract_with_newspaper_and_context(url, blog_context)
            else:
                content_data = web_scraper_service.extract_with_newspaper(url)
        else:
            # Use trafilatura for general content extraction
            if blog_context:
                content_data = web_scraper_service.extract_content_from_url_with_context(url, blog_context)
            else:
                content_data = web_scraper_service.extract_content_from_url(url)
        
        if not content_data:
            flash("Failed to extract content from the provided URL", "danger")
            return redirect(url_for('content_research'))
        
        # Process the extracted content for display
        text = ""
        title = ""
        summary = ""
        keywords = []
        sentiment = None
        image = None
        
        if method == 'newspaper':
            text = content_data.get('text', '')
            title = content_data.get('title', 'Untitled Article')
            summary = content_data.get('summary', '')
            keywords = content_data.get('keywords', [])
            image = content_data.get('top_image')
            
            # Perform sentiment analysis if not already done
            if 'sentiment' not in content_data and text:
                from textblob import TextBlob
                analysis = TextBlob(text)
                sentiment = {
                    'polarity': analysis.sentiment.polarity,
                    'subjectivity': analysis.sentiment.subjectivity
                }
            else:
                sentiment = content_data.get('sentiment')
        else:
            # For trafilatura extraction
            text = content_data.get('content', '')
            if not text and 'text' in content_data:
                text = content_data.get('text', '')
                
            title = content_data.get('title', 'Untitled Page')
            
            # Extract summary and keywords if available
            if 'analysis' in content_data:
                analysis = content_data.get('analysis', {})
                summary = analysis.get('summary', '')
                keywords = analysis.get('keywords', [])
                sentiment = analysis.get('sentiment')
        
        # Generate visualizations if possible
        wordcloud = None
        sentiment_chart = None
        try:
            from src.shared.content_visualizer import ContentVisualizer
            visualizer = ContentVisualizer()
            
            if text:
                wordcloud = visualizer.generate_wordcloud(text)
            
            if sentiment:
                sentiment_chart = visualizer.visualize_sentiment_analysis(sentiment)
        except Exception as viz_error:
            logger.warning(f"Failed to generate visualizations: {str(viz_error)}")
        
        # Prepare the results object
        results = {
            'type': 'scraped_content',
            'url': url,
            'title': title,
            'text': text,
            'summary': summary,
            'keywords': keywords,
            'sentiment': sentiment,
            'image': image,
            'wordcloud': wordcloud,
            'sentiment_chart': sentiment_chart,
            'raw_data': content_data,
            'blog_context': blog_context.get('name') if blog_context else None
        }
        
        return render_template('content_research.html', results=results)
        
    except Exception as e:
        logger.error(f"Error scraping URL: {str(e)}")
        flash(f"Error: {str(e)}", "danger")
        return redirect(url_for('content_research'))

@app.route('/get-trending-topics', methods=['POST'])
def get_trending_topics():
    """Handle form submission for trending topics and display results"""
    try:
        category = request.form.get('category')
        limit = int(request.form.get('limit', 10))
        blog_id = request.form.get('blog_id')
        
        logger.info(f"Getting trending topics for category: {category} with limit: {limit}, blog_id: {blog_id}")
        
        # Check if web scraper service is available
        if not web_scraper_service:
            flash("Web scraper service is not available", "danger")
            return redirect(url_for('content_research'))
        
        # Get blog context if specified
        blog_context = None
        if blog_id:
            try:
                blog_data = get_blog_by_id(blog_id)
                if blog_data:
                    blog_context = {
                        'name': blog_data.get('name', ''),
                        'theme': blog_data.get('theme', ''),
                        'topics': blog_data.get('topics', []),
                        'audience': blog_data.get('audience', '')
                    }
                    logger.info(f"Using blog context for trending topics: {blog_context['name']}")
            except Exception as e:
                logger.warning(f"Could not get blog context for ID {blog_id}: {str(e)}")
        
        # Get trending topics with optional blog context
        if blog_context:
            topics = web_scraper_service.get_trending_topics_with_context(category, limit, blog_context)
        else:
            topics = web_scraper_service.get_trending_topics(category, limit)
        
        if not topics:
            flash("No trending topics found", "warning")
            return redirect(url_for('content_research'))
        
        # Prepare the results object
        results = {
            'type': 'trending_topics',
            'category': category,
            'topics': topics,
            'blog_context': blog_context.get('name') if blog_context else None
        }
        
        return render_template('content_research.html', results=results)
        
    except Exception as e:
        logger.error(f"Error getting trending topics: {str(e)}")
        flash(f"Error: {str(e)}", "danger")
        return redirect(url_for('content_research'))

@app.route('/parse-rss-feed', methods=['POST'])
def parse_rss_feed():
    """Handle form submission for RSS feed parsing and display results"""
    try:
        feed_url = request.form.get('feed_url')
        limit = int(request.form.get('limit', 10))
        blog_id = request.form.get('blog_id')
        
        if not feed_url:
            flash("Feed URL is required", "danger")
            return redirect(url_for('content_research'))
        
        logger.info(f"Parsing RSS feed: {feed_url} with limit: {limit}, blog_id: {blog_id}")
        
        # Check if web scraper service is available
        if not web_scraper_service:
            flash("Web scraper service is not available", "danger")
            return redirect(url_for('content_research'))
        
        # Get blog context if specified
        blog_context = None
        if blog_id:
            try:
                blog_data = get_blog_by_id(blog_id)
                if blog_data:
                    blog_context = {
                        'name': blog_data.get('name', ''),
                        'theme': blog_data.get('theme', ''),
                        'topics': blog_data.get('topics', []),
                        'audience': blog_data.get('audience', '')
                    }
                    logger.info(f"Using blog context for RSS feed parsing: {blog_context['name']}")
            except Exception as e:
                logger.warning(f"Could not get blog context for ID {blog_id}: {str(e)}")
        
        # Fetch RSS feed with optional blog context
        if blog_context:
            feed_entries = web_scraper_service.fetch_rss_feed_with_context(feed_url, limit, blog_context)
        else:
            feed_entries = web_scraper_service.fetch_rss_feed(feed_url, limit)
        
        if not feed_entries or len(feed_entries) == 0:
            flash("No entries found in the RSS feed", "warning")
            return redirect(url_for('content_research'))
        
        # Prepare the results object
        results = {
            'type': 'rss_feed',
            'feed_url': feed_url,
            'entries': feed_entries,
            'blog_context': blog_context.get('name') if blog_context else None
        }
        
        return render_template('content_research.html', results=results)
        
    except Exception as e:
        logger.error(f"Error parsing RSS feed: {str(e)}")
        flash(f"Error: {str(e)}", "danger")
        return redirect(url_for('content_research'))

@app.route('/api/rss-feed-v2', methods=['POST'])
def rss_feed_api_v2():
    """Updated API endpoint to fetch and parse an RSS feed"""
    try:
        data = request.json
        if not data or 'feed_url' not in data:
            return jsonify({"success": False, "message": "Feed URL is required"}), 400
        
        feed_url = data['feed_url']
        limit = int(data.get('limit', 10))
        blog_id = data.get('blog_id')
        logger.info(f"Fetching RSS feed: {feed_url} with limit {limit}, blog_id: {blog_id}")
        
        # Check if web scraper service is available
        if not web_scraper_service:
            return jsonify({
                "success": False, 
                "message": "Web scraper service is not available"
            }), 500
        
        # Get blog context if specified
        blog_context = None
        if blog_id:
            try:
                blog_data = get_blog_by_id(blog_id)
                if blog_data:
                    blog_context = {
                        'name': blog_data.get('name', ''),
                        'theme': blog_data.get('theme', ''),
                        'topics': blog_data.get('topics', []),
                        'audience': blog_data.get('audience', ''),
                        'tone': blog_data.get('tone', 'informative')
                    }
                    logger.info(f"Using blog context for RSS feed parsing API: {blog_context['name']}")
            except Exception as e:
                logger.warning(f"Could not get blog context for ID {blog_id}: {str(e)}")
        
        # Fetch RSS feed with optional blog context
        if blog_context:
            feed_entries = web_scraper_service.fetch_rss_feed_with_context(feed_url, limit, blog_context)
        else:
            feed_entries = web_scraper_service.fetch_rss_feed(feed_url, limit)
        
        if feed_entries is None:
            return jsonify({
                "success": False, 
                "message": "Failed to fetch the RSS feed"
            }), 400
        
        return jsonify({
            "success": True, 
            "data": feed_entries,
            "used_context_aware_method": blog_context is not None,
            "blog_name": blog_context.get('name') if blog_context else None
        })
    except Exception as e:
        logger.error(f"Error fetching RSS feed: {str(e)}")
        return jsonify({"success": False, "message": f"Error: {str(e)}"}), 500

@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404

@app.errorhandler(500)
def server_error(e):
    return render_template('500.html'), 500

@app.route('/test/wordpress-connection')
def test_wordpress_connection():
    """Test endpoint for WordPress connection with Key Vault integration"""
    try:
        # Import the WordPressService
        from src.shared.wordpress_service import WordPressService
        
        # Initialize the service
        wordpress_service = WordPressService()
        
        # Check if we have credentials loaded from Key Vault
        connection_info = {
            "status": "checking",
            "message": "Checking WordPress connection status...",
            "url_from_keyvault": None,
            "username_from_keyvault": None,
            "has_password": False,
            "is_multisite": wordpress_service.is_multisite,
            "multisite_config": wordpress_service.multisite_config,
            "network_id": wordpress_service.network_id
        }
        
        # Get site list if multisite is enabled
        if wordpress_service.is_multisite:
            try:
                site_list = wordpress_service.get_site_list()
                connection_info["site_list"] = site_list
                connection_info["multisite_message"] = f"WordPress Multisite enabled with {len(site_list)} sites"
            except Exception as e:
                connection_info["site_list_error"] = str(e)
                connection_info["multisite_message"] = f"Error retrieving site list: {str(e)}"
        
        # Check if we have WordPress URL from Key Vault
        if wordpress_service.default_wordpress_url:
            connection_info["url_from_keyvault"] = wordpress_service.default_wordpress_url
            connection_info["status"] = "url_found"
        
        # Check if we have WordPress username from Key Vault
        if wordpress_service.default_wordpress_username:
            connection_info["username_from_keyvault"] = wordpress_service.default_wordpress_username
            if connection_info["status"] == "url_found":
                connection_info["status"] = "username_found"
        
        # Check if we have WordPress password from Key Vault
        if wordpress_service.default_wordpress_password:
            connection_info["has_password"] = True
            if connection_info["status"] == "username_found":
                connection_info["status"] = "credentials_found"
                connection_info["message"] = "WordPress credentials found in Key Vault."
        
        # If we have all credentials, try to test the connection
        if connection_info["status"] == "credentials_found":
            try:
                # Create a test post title with timestamp to avoid duplication
                test_title = f"Test Post from Key Vault Connection - {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                test_content = "<p>This is a test post created to verify the WordPress connection using credentials from Key Vault.</p>"
                
                # Try to publish a test post
                publish_result = wordpress_service.publish_to_default_wordpress(
                    title=test_title,
                    content=test_content,
                    seo_metadata={
                        "slug": "",
                        "meta_description": "Test post for Key Vault WordPress connection",
                        "keywords": ["test", "key-vault", "wordpress"]
                    }
                )
                
                # If we get here, the connection was successful
                connection_info["status"] = "connected"
                connection_info["message"] = "Successfully connected to WordPress and published a test post."
                connection_info["post_id"] = publish_result.get("post_id")
                connection_info["post_url"] = publish_result.get("post_url")
                
            except Exception as e:
                connection_info["status"] = "error"
                connection_info["message"] = f"Error connecting to WordPress: {str(e)}"
        
        return render_template('wordpress_test.html', connection_info=connection_info)
        
    except Exception as e:
        logger.error(f"Error in test_wordpress_connection endpoint: {str(e)}")
        return jsonify({"status": "error", "message": f"WordPress connection test failed: {str(e)}"})

@app.route('/test/wordpress-multisite')
def test_wordpress_multisite():
    """Test endpoint for WordPress Multisite configuration"""
    try:
        # Import the WordPressService
        from src.shared.wordpress_service import WordPressService
        
        # Initialize the service
        wordpress_service = WordPressService()
        
        # Check if WordPress is configured as Multisite
        if not wordpress_service.is_multisite:
            return render_template('error.html', error_message="WordPress is not configured as Multisite. Please enable Multisite in your WordPress configuration.")
        
        # Get multisite information
        multisite_info = {
            "is_multisite": wordpress_service.is_multisite,
            "multisite_config": wordpress_service.multisite_config,
            "network_id": wordpress_service.network_id,
            "wordpress_url": wordpress_service.default_wordpress_url,
            "status": "multisite_enabled"
        }
        
        # Get site list
        try:
            site_list = wordpress_service.get_site_list()
            multisite_info["site_list"] = site_list
            multisite_info["site_count"] = len(site_list)
        except Exception as e:
            multisite_info["site_list_error"] = str(e)
        
        # For each site, try to get mapped domains
        if multisite_info.get("site_list"):
            for site in multisite_info["site_list"]:
                try:
                    site["mapped_domains"] = wordpress_service.get_mapped_domains(site["id"])
                except Exception as e:
                    site["domain_error"] = str(e)
        
        return render_template('wordpress_multisite.html', multisite_info=multisite_info)
        
    except Exception as e:
        logger.error(f"Error in test_wordpress_multisite endpoint: {str(e)}")
        return render_template('error.html', error_message=f"WordPress Multisite test failed: {str(e)}")

@app.route('/wordpress-domain-mapping', methods=['GET', 'POST'])
def wordpress_domain_mapping():
    """Page to manage WordPress Multisite domain mapping"""
    try:
        # Import the WordPressService
        from src.shared.wordpress_service import WordPressService
        
        # Initialize the service
        wordpress_service = WordPressService()
        error_message = None
        success_message = None
        
        # Check if WordPress is configured as Multisite
        if not wordpress_service.is_multisite:
            return render_template('error.html', error_message="WordPress is not configured as Multisite. Domain mapping is only available for Multisite installations.")
        
        # Get site list
        site_list = wordpress_service.get_site_list()
        
        # Handle domain mapping form submission
        if request.method == 'POST':
            action = request.form.get('action', 'add')
            
            if action == 'delete':
                # Handle domain deletion
                domain_id = request.form.get('domain_id')
                site_id = request.form.get('site_id')
                if not domain_id or not site_id:
                    error_message = "Domain ID and site ID are required for deletion"
                else:
                    try:
                        result = wordpress_service.delete_domain_mapping(int(site_id), int(domain_id))
                        success_message = f"Successfully removed domain mapping (ID: {domain_id}) from site {site_id}"
                    except Exception as e:
                        error_message = f"Error removing domain mapping: {str(e)}"
            else:
                # Handle domain addition
                site_id = request.form.get('site_id')
                domain = request.form.get('domain')
                
                if not site_id or not domain:
                    error_message = "Site ID and domain are required"
                else:
                    try:
                        result = wordpress_service.map_domain(int(site_id), domain)
                        success_message = f"Successfully mapped domain {domain} to site {site_id}"
                    except Exception as e:
                        error_message = f"Error mapping domain: {str(e)}"
        
        # Get mapped domains for each site
        for site in site_list:
            try:
                site['mapped_domains'] = wordpress_service.get_mapped_domains(site['id'])
            except Exception as e:
                site['domain_error'] = str(e)
        
        return render_template(
            'wordpress_domain_mapping.html', 
            site_list=site_list, 
            error_message=error_message,
            success_message=success_message
        )
    except Exception as e:
        logger.error(f"Error in wordpress_domain_mapping endpoint: {str(e)}")
        return render_template('error.html', error_message=f"Error accessing WordPress Multisite information: {str(e)}")
        
@app.route('/ai-optimization')
def ai_optimization_dashboard():
    """
    Display AI optimization settings and statistics
    """
    return render_template('ai_optimization.html')

@app.route('/api/ai-optimization/stats')
def api_ai_optimization_stats():
    """API endpoint to get AI optimization statistics"""
    try:
        stats = optimized_openai_service.get_usage_statistics()
        return jsonify(stats)
    except Exception as e:
        logger.error(f"Error getting AI optimization stats: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/ai-optimization/settings', methods=['POST'])
def api_ai_optimization_settings():
    """API endpoint to update AI optimization settings"""
    try:
        data = request.json
        
        # Update settings based on what's provided
        if 'daily_budget' in data:
            # Update daily budget
            optimized_openai_service.set_daily_budget(float(data['daily_budget']))
            
        if 'caching_enabled' in data:
            # Update caching settings
            optimized_openai_service.set_caching_enabled(bool(data['caching_enabled']))
            
        if 'cache_ttl_seconds' in data:
            # Update cache TTL
            optimized_openai_service.set_cache_ttl(int(data['cache_ttl_seconds']))
            
        if 'models' in data:
            # Update model settings
            models = data['models']
            optimized_openai_service.set_model_preferences(
                draft_model=models.get('draft'),
                polish_model=models.get('polish')
            )
            
        return jsonify({"success": True})
    except Exception as e:
        logger.error(f"Error updating AI optimization settings: {str(e)}")
        return jsonify({"success": False, "message": str(e)}), 500

@app.route('/api/ai-optimization/clear-cache', methods=['POST'])
def api_ai_optimization_clear_cache():
    """API endpoint to clear the AI response cache"""
    try:
        optimized_openai_service.clear_cache()
        return jsonify({"success": True})
    except Exception as e:
        logger.error(f"Error clearing AI cache: {str(e)}")
        return jsonify({"success": False, "message": str(e)}), 500

@app.route('/api/ai-optimization/validate-prompt', methods=['POST'])
def api_ai_optimization_validate_prompt():
    """API endpoint to validate and analyze a prompt"""
    try:
        data = request.json
        prompt = data.get('prompt', '')
        
        if not prompt:
            return jsonify({"success": False, "message": "Prompt is required"}), 400
            
        # Analyze the prompt
        analysis = optimized_openai_service.analyze_prompt(prompt)
        return jsonify({"success": True, **analysis})
    except Exception as e:
        logger.error(f"Error validating prompt: {str(e)}")
        return jsonify({"success": False, "message": str(e)}), 500

@app.route('/api/ai-optimization/optimize-prompt', methods=['POST'])
def api_ai_optimization_optimize_prompt():
    """API endpoint to optimize a prompt for token efficiency"""
    try:
        data = request.json
        prompt = data.get('prompt', '')
        
        if not prompt:
            return jsonify({"success": False, "message": "Prompt is required"}), 400
            
        # Optimize the prompt
        optimized_prompt = optimized_openai_service.optimize_prompt(prompt)
        return jsonify({
            "success": True,
            "optimized_prompt": optimized_prompt
        })
    except Exception as e:
        logger.error(f"Error optimizing prompt: {str(e)}")
        return jsonify({"success": False, "message": str(e)}), 500

# Helper function to get blog by ID
def get_blog_by_id(blog_id):
    """
    Retrieves blog information by its ID
    
    Args:
        blog_id (str): The ID of the blog to retrieve
        
    Returns:
        dict: The blog configuration, or None if not found
    """
    try:
        logger.info(f"Retrieving blog with ID: {blog_id}")
        blog_config_path = os.path.join("data/blogs", blog_id, "config.json")
        
        # Check if file exists
        if not os.path.exists(blog_config_path):
            logger.warning(f"Blog configuration not found for ID: {blog_id}")
            return None
        
        # Read the configuration file
        with open(blog_config_path, 'r') as f:
            blog_config = json.load(f)
        
        # Add the blog ID to the config
        blog_config['id'] = blog_id
        
        # Ensure required fields exist with defaults if missing
        if 'topics' not in blog_config:
            logger.info(f"Adding default topics field to blog {blog_id}")
            blog_config['topics'] = []
            
        if 'audience' not in blog_config:
            logger.info(f"Adding default audience field to blog {blog_id}")
            blog_config['audience'] = 'general'
            
        if 'tone' not in blog_config:
            logger.info(f"Adding default tone field to blog {blog_id}")
            blog_config['tone'] = 'informative'
        
        logger.info(f"Successfully retrieved blog with ID: {blog_id}")
        return blog_config
    except Exception as e:
        logger.error(f"Error getting blog by ID {blog_id}: {str(e)}, traceback: {traceback.format_exc()}")
        return None

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=True)