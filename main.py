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
    # Get all the generated runs
    runs = []
    try:
        run_folders = storage_service.list_blobs("generated", None)
        for folder in run_folders:
            if '/' in folder:  # Skip files in the root generated folder
                run_id = folder.split('/')[0]
                if run_id not in [run['id'] for run in runs]:
                    # Get run status
                    status = "unknown"
                    if storage_service.blob_exists("generated", f"{run_id}/results.json"):
                        status = "completed"
                    elif storage_service.blob_exists("generated", f"{run_id}/publish.json"):
                        status = "published"
                    elif storage_service.blob_exists("generated", f"{run_id}/content.md"):
                        status = "content-generated"
                    elif storage_service.blob_exists("generated", f"{run_id}/research.json"):
                        status = "researched"
                    elif storage_service.blob_exists("generated", f"{run_id}/.run"):
                        status = "started"
                    
                    # Parse timestamp from run_id
                    timestamp = None
                    if '_' in run_id:
                        try:
                            date_part = run_id.split('_')[0]
                            time_part = run_id.split('_')[1]
                            dt_str = f"{date_part[:4]}-{date_part[4:6]}-{date_part[6:8]} {time_part[:2]}:{time_part[2:4]}:{time_part[4:6]}"
                            timestamp = datetime.datetime.strptime(dt_str, '%Y-%m-%d %H:%M:%S')
                        except:
                            pass
                    
                    runs.append({
                        'id': run_id,
                        'status': status,
                        'timestamp': timestamp,
                        'timestamp_str': timestamp.strftime('%Y-%m-%d %H:%M:%S') if timestamp else run_id
                    })
        
        # Sort runs by timestamp (newest first)
        runs.sort(key=lambda x: x['timestamp'] if x['timestamp'] else datetime.datetime.min, reverse=True)
    except Exception as e:
        logger.error(f"Error getting run data: {str(e)}")
    
    # Check if configuration files exist
    config_files = {
        'topics.json': storage_service.blob_exists("", "topics.json"),
        'theme.json': storage_service.blob_exists("", "theme.json"),
        'frequency.json': storage_service.blob_exists("", "frequency.json"),
        'ready.json': storage_service.blob_exists("", "ready.json"),
        'bootstrap.json': storage_service.blob_exists("", "bootstrap.json"),
        'bootstrap.done.json': storage_service.blob_exists("", "bootstrap.done.json"),
        'DomainNames.json': storage_service.blob_exists("", "DomainNames.json")
    }
    
    return render_template('index.html', runs=runs, config_files=config_files)

@app.route('/setup', methods=['GET', 'POST'])
def setup():
    """Setup page for creating new blog configurations"""
    if request.method == 'POST':
        try:
            # Process topics
            topics = request.form.get('topics', '').strip()
            topics_list = [topic.strip() for topic in topics.split('\n') if topic.strip()]
            
            # Process theme
            theme_name = request.form.get('theme_name', '').strip()
            theme_description = request.form.get('theme_description', '').strip()
            target_audience = request.form.get('target_audience', '').strip()
            
            # Process frequency
            daily_frequency = request.form.get('daily_frequency', '1').strip()
            try:
                daily_frequency = int(daily_frequency)
            except:
                daily_frequency = 1
            
            # Create topics.json
            topics_json = json.dumps(topics_list, indent=2)
            storage_service.set_blob("", "topics.json", topics_json, "application/json")
            
            # Create theme.json
            theme_json = json.dumps({
                "name": theme_name,
                "description": theme_description,
                "target_audience": target_audience
            }, indent=2)
            storage_service.set_blob("", "theme.json", theme_json, "application/json")
            
            # Create frequency.json
            frequency_json = json.dumps({
                "daily": daily_frequency
            }, indent=2)
            storage_service.set_blob("", "frequency.json", frequency_json, "application/json")
            
            # Create ready.json (empty)
            storage_service.set_blob("", "ready.json", "{}", "application/json")
            
            # Create bootstrap.json (empty) - triggers bootstrap process
            storage_service.set_blob("", "bootstrap.json", "{}", "application/json")
            
            flash("Blog configuration created successfully", "success")
            return redirect(url_for('index'))
        
        except Exception as e:
            logger.error(f"Error setting up blog: {str(e)}")
            flash(f"Error setting up blog: {str(e)}", "error")
    
    return render_template('setup.html')

@app.route('/blog/<blog_id>')
def blog_detail(blog_id):
    """Blog detail page"""
    # Get content.md
    content = storage_service.get_blob("generated", f"{blog_id}/content.md")
    
    # Get research.json
    research_json = storage_service.get_blob("generated", f"{blog_id}/research.json")
    research = json.loads(research_json) if research_json else None
    
    # Get recommendations.json
    recommendations_json = storage_service.get_blob("generated", f"{blog_id}/recommendations.json")
    recommendations = json.loads(recommendations_json) if recommendations_json else None
    
    # Get publish.json
    publish_json = storage_service.get_blob("generated", f"{blog_id}/publish.json")
    publish = json.loads(publish_json) if publish_json else None
    
    # Get results.json
    results_json = storage_service.get_blob("generated", f"{blog_id}/results.json")
    results = json.loads(results_json) if results_json else None
    
    return render_template('blog_detail.html', 
                          blog_id=blog_id, 
                          content=content, 
                          research=research, 
                          recommendations=recommendations,
                          publish=publish,
                          results=results)

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