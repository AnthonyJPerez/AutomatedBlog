import json
import logging
import os
from datetime import datetime

import azure.functions as func
from ..shared.social_media_service import SocialMediaService

def main(inputBlob: func.InputStream, outputBlob: func.Out[str]) -> None:
    """
    Blob trigger that promotes published content on social media.
    This function is triggered when a new publish result is created.
    It posts content to configured social media platforms.
    
    Parameters:
        inputBlob: The input blob that triggered this function (publish.json)
        outputBlob: Output binding for the promotion results (promote.json)
    """
    logging.info(f"SocialMediaPromoter triggered by: {inputBlob.name}")
    
    try:
        # Read the published content data
        publish_data = json.loads(inputBlob.read())
        
        # Check if the content was published successfully
        if publish_data.get("status") != "published":
            logging.warning(f"Content not published, skipping social promotion: {publish_data.get('status')}")
            
            # Write an empty result
            result = {
                "timestamp": datetime.now().isoformat(),
                "status": "skipped",
                "reason": f"Content not published: {publish_data.get('status')}"
            }
            outputBlob.set(json.dumps(result, indent=2))
            return
        
        # Extract blog_id and run_id from the blob path
        # Expected path format: .../blogs/{blog_id}/runs/{run_id}/publish.json
        path_parts = inputBlob.name.split('/')
        blog_id = None
        run_id = None
        
        for i in range(len(path_parts)):
            if path_parts[i] == "blogs" and i + 1 < len(path_parts):
                blog_id = path_parts[i + 1]
            if path_parts[i] == "runs" and i + 1 < len(path_parts):
                run_id = path_parts[i + 1]
        
        if not blog_id or not run_id:
            logging.error(f"Could not extract blog_id and run_id from path: {inputBlob.name}")
            
            result = {
                "timestamp": datetime.now().isoformat(),
                "status": "error",
                "error": f"Invalid path format: {inputBlob.name}"
            }
            outputBlob.set(json.dumps(result, indent=2))
            return
        
        # Get the content path
        content_path = f"blogs/{blog_id}/runs/{run_id}/content.md"
        content_json_path = f"blogs/{blog_id}/runs/{run_id}/content.json"
        
        # Get content metadata if available
        content_data = {}
        
        # Check for content.json which would have metadata
        try:
            from ..shared.storage_service import StorageService
            storage_service = StorageService()
            
            # First try the content.json file
            if storage_service.blob_exists("generated", content_json_path):
                content_json = storage_service.read_blob("generated", content_json_path)
                content_data = json.loads(content_json)
            else:
                # If no content.json, get the content.md and extract what we can
                if storage_service.blob_exists("generated", content_path):
                    content_md = storage_service.read_blob("generated", content_path)
                    
                    # Extract the title from the first heading
                    lines = content_md.split('\n')
                    title = None
                    excerpt = ""
                    tags = []
                    
                    # Store the full content for Medium
                    full_content = content_md
                    
                    for line in lines:
                        if not title and line.startswith('# '):
                            title = line[2:].strip()
                        elif title and not line.startswith('#') and len(excerpt) < 300:
                            excerpt += line + " "
                        
                        # Look for tags/categories if specified with a certain format
                        # For example: "Tags: tech, ai, blogging"
                        if line.lower().startswith("tags:") or line.lower().startswith("categories:"):
                            tag_text = line.split(":", 1)[1].strip()
                            # Split by comma and trim whitespace
                            tags = [tag.strip() for tag in tag_text.split(",") if tag.strip()]
                    
                    content_data = {
                        "title": title or "New Blog Post",
                        "excerpt": excerpt[:300].strip(),
                        "content": full_content,  # Store full content for Medium
                        "tags": tags
                    }
                    
                    # Look for an image reference
                    for line in lines:
                        if "![" in line and "](" in line:
                            img_start = line.find("](") + 2
                            img_end = line.find(")", img_start)
                            if img_start > 0 and img_end > 0:
                                image_path = line[img_start:img_end]
                                if "://" in image_path:  # It's a URL
                                    content_data["featured_image"] = image_path
                                    break
        except Exception as e:
            logging.warning(f"Could not get content data: {str(e)}")
        
        # Get blog configuration for social media settings
        config_path = f"blogs/{blog_id}/config.json"
        promote = True  # Default is to promote
        platforms = []  # Default is all enabled platforms
        
        try:
            if storage_service.blob_exists("data", config_path):
                config_json = storage_service.read_blob("data", config_path)
                config = json.loads(config_json)
                
                # Check if promotion is disabled for this blog
                if "social_media" in config:
                    promote = config["social_media"].get("enabled", True)
                    platforms = config["social_media"].get("platforms", [])
        except Exception as e:
            logging.warning(f"Could not get blog config: {str(e)}")
        
        if not promote:
            logging.info(f"Social media promotion disabled for blog: {blog_id}")
            
            result = {
                "timestamp": datetime.now().isoformat(),
                "status": "skipped",
                "reason": "Social media promotion disabled in blog configuration"
            }
            outputBlob.set(json.dumps(result, indent=2))
            return
        
        # Initialize social media service
        social_media_service = SocialMediaService()
        
        # Get available platforms
        available_platforms = social_media_service.get_enabled_platforms()
        
        if not available_platforms:
            logging.warning("No social media platforms are configured")
            
            result = {
                "timestamp": datetime.now().isoformat(),
                "status": "error",
                "error": "No social media platforms are configured"
            }
            outputBlob.set(json.dumps(result, indent=2))
            return
        
        # If specific platforms are configured in the blog, use those
        # Otherwise use all available platforms
        target_platforms = platforms if platforms else available_platforms
        logging.info(f"Will promote to platforms: {', '.join(target_platforms)}")
        
        # Promote the content
        promotion_result = social_media_service.promote_content(blog_id, run_id, content_data, publish_data)
        
        # Write the result
        result = {
            "timestamp": datetime.now().isoformat(),
            "status": "completed" if promotion_result.get("success", False) else "partial",
            "blog_id": blog_id,
            "run_id": run_id,
            "platforms": promotion_result.get("platforms", {})
        }
        
        outputBlob.set(json.dumps(result, indent=2))
        logging.info(f"Social media promotion completed for {blog_id}/{run_id}")
        
    except Exception as e:
        logging.error(f"Error in SocialMediaPromoter: {str(e)}")
        
        # Write error result
        result = {
            "timestamp": datetime.now().isoformat(),
            "status": "error",
            "error": str(e)
        }
        outputBlob.set(json.dumps(result, indent=2))