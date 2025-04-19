import logging
import json
import os
import time
import azure.functions as func
from ..shared.openai_service import OpenAIService
from ..shared.storage_service import StorageService

# Mock SurferSEO API service for now
class SurferSEOService:
    def optimize_content(self, content, keywords):
        # In a real implementation, this would call the SurferSEO API
        return {
            "optimizedContent": content,
            "score": 85,
            "recommendations": [
                {"keyword": kw, "occurrences": 2, "recommended": 3} for kw in keywords[:5]
            ]
        }

def main(inputBlob: func.InputStream, outputContent: func.Out[str], outputRecommendations: func.Out[str]) -> None:
    """
    Blob trigger that generates content based on research data.
    This function is triggered when a new research.json is created.
    It uses OpenAI to generate content and SurferSEO to optimize it.
    
    Parameters:
        inputBlob: The input blob that triggered this function (research.json)
        outputContent: Output binding for the generated content (content.md)
        outputRecommendations: Output binding for the SEO recommendations
    """
    # Set up logging
    logger = logging.getLogger('ContentGenerator')
    logger.info(f'ContentGenerator function triggered by blob: {inputBlob.name}')
    
    # Initialize services
    storage_service = StorageService()
    openai_service = OpenAIService()
    surferseo_service = SurferSEOService()
    
    # Extract runId from the blob name
    try:
        # Path format: generated/{runId}/research.json
        path_parts = inputBlob.name.split('/')
        run_id = path_parts[1]
        logger.info(f'Processing run ID: {run_id}')
    except Exception as e:
        logger.error(f'Error extracting run ID from blob name: {str(e)}')
        return
    
    # Check if content.md already exists (idempotency)
    content_path = f'generated/{run_id}/content.md'
    existing_content = storage_service.get_blob('', content_path)
    if existing_content:
        logger.info(f'Content already exists for run ID: {run_id}, skipping')
        return
    
    # Parse research data
    try:
        research_data = json.loads(inputBlob.read().decode('utf-8'))
    except Exception as e:
        logger.error(f'Error parsing research data: {str(e)}')
        return
    
    # Extract relevant information from research data
    topics = research_data.get('topics', [])
    theme = research_data.get('theme', '')
    blog_id = research_data.get('blog_id', '')
    research_results = research_data.get('research_results', [])
    
    # Load theme.json if blog_id is available
    theme_info = None
    if blog_id:
        try:
            theme_path = f'data/blogs/{blog_id}/config/theme.json'
            theme_info = storage_service.get_local_json(theme_path)
            if theme_info:
                logger.info(f'Loaded theme information for blog: {blog_id}')
        except Exception as e:
            logger.warning(f'Could not load theme.json for blog {blog_id}: {str(e)}')
    
    # Select the best topic based on research results
    selected_topic = None
    if research_results:
        # Sort by trend_score and select the top one
        try:
            sorted_results = sorted(research_results, key=lambda x: x.get('trend_score', 0), reverse=True)
            selected_topic = sorted_results[0]
        except Exception as e:
            logger.error(f'Error selecting topic: {str(e)}')
    
    if not selected_topic:
        logger.error('No valid topic found in research results')
        return
    
    # Extract topic information
    topic_keyword = selected_topic.get('keyword', '')
    topic_title = selected_topic.get('title', f'Article about {topic_keyword}')
    
    # Extract web research data if available
    web_research_data = None
    if selected_topic.get('web_research'):
        web_research_data = selected_topic['web_research']
        logger.info(f'Found web research data for topic: {topic_title}')
    
    # Generate outline using OpenAI
    try:
        logger.info(f'Generating outline for topic: {topic_title}')
        
        # Create a more comprehensive context if we have web research data
        context = {}
        if web_research_data:
            context = {
                'related_keywords': web_research_data.get('related_keywords', []),
                'topic_summary': web_research_data.get('summary', ''),
                'sources': web_research_data.get('sources', []),
                'sentiment': web_research_data.get('sentiment', {})
            }
        
        outline = openai_service.generate_outline(
            topic=topic_title,
            theme=theme,
            tone='professional',
            target_audience='general',
            context=context,
            theme_info=theme_info
        )
    except Exception as e:
        logger.error(f'Error generating outline: {str(e)}')
        outline = {"sections": [{"title": "Introduction"}, {"title": "Main Content"}, {"title": "Conclusion"}]}
    
    # Generate content draft using OpenAI (GPT-3.5 equivalent)
    try:
        logger.info(f'Generating content draft for topic: {topic_title}')
        
        # Use the same context for content generation if available
        content_context = {}
        if web_research_data:
            content_context = {
                'related_keywords': web_research_data.get('related_keywords', []),
                'topic_summary': web_research_data.get('summary', ''),
                'sources': web_research_data.get('sources', []),
                'sentiment': web_research_data.get('sentiment', {}),
                'related_trends': web_research_data.get('related_trends', [])
            }
            
            # Log source references being used for content
            source_urls = [s.get('url') for s in content_context.get('sources', []) if s.get('url')]
            if source_urls:
                logger.info(f'Using {len(source_urls)} reference sources for content generation')
        
        content_draft = openai_service.generate_content(
            topic=topic_title,
            outline=outline,
            theme=theme,
            tone='professional',
            target_audience='general',
            content_type='article',
            context=content_context
        )
    except Exception as e:
        logger.error(f'Error generating content draft: {str(e)}')
        content_draft = f"# {topic_title}\n\nContent generation failed. Please try again later."
    
    # Polish content using OpenAI (GPT-4 equivalent)
    try:
        logger.info('Polishing content with GPT-4')
        
        # Use the same context for polishing if available
        polish_context = {}
        if web_research_data:
            # For polishing, provide additional context that may help improve the content
            polish_context = {
                'content_draft': content_draft,
                'related_keywords': web_research_data.get('related_keywords', []),
                'source_references': web_research_data.get('sources', []),
                'sentiment_target': web_research_data.get('sentiment', {}).get('category', 'neutral'),
                'related_trends': web_research_data.get('related_trends', [])
            }
        
        polished_content = openai_service.generate_content(
            topic=topic_title,
            outline=outline,
            theme=theme,
            tone='professional',
            target_audience='general',
            content_type='polish',
            context=polish_context
        )
    except Exception as e:
        logger.error(f'Error polishing content: {str(e)}')
        polished_content = content_draft
    
    # Optimize content using SurferSEO
    try:
        logger.info('Optimizing content with SurferSEO')
        keywords = [topic_keyword] + [item.get('keyword', '') for item in research_results[:5] if 'keyword' in item]
        seo_result = surferseo_service.optimize_content(polished_content, keywords)
        optimized_content = seo_result.get('optimizedContent', polished_content)
        seo_score = seo_result.get('score', 0)
        recommendations = seo_result.get('recommendations', [])
    except Exception as e:
        logger.error(f'Error optimizing content: {str(e)}')
        optimized_content = polished_content
        seo_score = 0
        recommendations = []
    
    # Generate final metadata
    try:
        logger.info('Generating SEO metadata')
        seo_metadata = openai_service.generate_seo_metadata(topic_title, optimized_content)
    except Exception as e:
        logger.error(f'Error generating SEO metadata: {str(e)}')
        seo_metadata = {
            "meta_description": f"Learn about {topic_keyword} in this comprehensive article.",
            "keywords": [topic_keyword],
            "social_title": topic_title,
            "social_description": f"Read our comprehensive guide about {topic_keyword}.",
            "slug": topic_keyword.lower().replace(' ', '-')
        }
    
    # Generate a featured image for the content
    image_info = None
    try:
        logger.info(f'Generating featured image for topic: {topic_title}')
        # Create an image prompt based on the topic and theme
        image_prompt = f"Create a professional featured image for a blog post about '{topic_title}'."
        if theme:
            image_prompt += f" The blog's theme is '{theme}'."
        
        # Generate the image
        image_info = openai_service.generate_image(
            prompt=image_prompt,
            size="1024x1024",
            style="natural",
            quality="standard"
        )
        
        logger.info(f'Image generation result: {image_info.get("success", False)}')
    except Exception as e:
        logger.error(f'Error generating image: {str(e)}')
        image_info = {"success": False, "error": str(e)}
    
    # Prepare featured image metadata
    featured_image_path = None
    if image_info and image_info.get("success", False):
        # Store relative path to be used in the Markdown file
        featured_image_path = image_info.get("local_path", "")
        # Get just the filename part
        if featured_image_path:
            featured_image_path = featured_image_path.replace("\\", "/")  # Normalize path separators
            featured_image_filename = os.path.basename(featured_image_path)
            featured_image_path = f"/static/images/{featured_image_filename}"
    
    # Prepare final content with metadata and featured image
    image_section = ""
    if featured_image_path:
        image_section = f"""
![Featured image for {topic_title}]({featured_image_path})

"""
    
    final_content = f"""---
title: "{topic_title}"
description: "{seo_metadata.get('meta_description', '')}"
keywords: {', '.join(seo_metadata.get('keywords', [topic_keyword]))}
slug: {seo_metadata.get('slug', topic_keyword.lower().replace(' ', '-'))}
date: {time.strftime('%Y-%m-%d')}
featured_image: "{featured_image_path if featured_image_path else ""}"
---

{image_section}{optimized_content}
"""
    
    # Prepare recommendations JSON
    recommendations_data = {
        "runId": run_id,
        "topic": topic_title,
        "seo_score": seo_score,
        "recommendations": recommendations,
        "metadata": seo_metadata,
        "suggested_topics": [item.get('title', '') for item in research_results[1:6] if 'title' in item]
    }
    
    # Write to output bindings
    outputContent.set(final_content)
    outputRecommendations.set(json.dumps(recommendations_data, indent=2))
    
    logger.info(f'Content and recommendations for run ID: {run_id} successfully written')