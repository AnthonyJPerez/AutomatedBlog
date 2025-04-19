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
    
    # Log extracted research details
    logger.info(f'Processing content generation for blog: {blog_id} with theme: {theme}')
    logger.info(f'Found {len(research_results)} research results to process')
    
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
        
        prompt = f"Create a detailed outline for a blog post about '{topic_title}'"
        outline = openai_service.generate_outline(
            topic=topic_title,
            theme=theme,
            tone='professional',
            target_audience='general',
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
        
        # Create an enhanced prompt for content generation using theme.json information
        prompt = f"Write a comprehensive blog post about {topic_title}"
        
        # Add theme-specific information from theme.json if available
        if theme_info:
            # Extract content strategy information
            content_strategy = theme_info.get('content_strategy', {})
            if content_strategy:
                tone = content_strategy.get('tone', 'professional')
                style = content_strategy.get('style', '')
                content_types = content_strategy.get('content_types', [])
                length = content_strategy.get('preferred_length', '')
                
                if tone:
                    prompt += f" using a {tone} tone"
                if style:
                    prompt += f" and {style} style"
                if length:
                    prompt += f". The article should be {length}"
                
                # Add content type specific instructions
                if content_types and len(content_types) > 0:
                    content_type_desc = ', '.join(content_types[:3])
                    prompt += f". This content should follow formats common for: {content_type_desc}"
            
            # Add audience information
            audience = theme_info.get('target_audience', {})
            if audience and isinstance(audience, dict):
                demographics = audience.get('demographics', '')
                interests = audience.get('interests', [])
                expertise = audience.get('expertise_level', '')
                pain_points = audience.get('pain_points', [])
                
                if demographics:
                    prompt += f". Target audience demographics: {demographics}"
                if expertise:
                    prompt += f". The audience has a {expertise} level of expertise"
                if interests and len(interests) > 0:
                    interests_str = ', '.join(interests[:3])
                    prompt += f". They are interested in: {interests_str}"
                if pain_points and len(pain_points) > 0:
                    pain_points_str = ', '.join(pain_points[:3])
                    prompt += f". Address these pain points: {pain_points_str}"
            
            # Add SEO and keyword information
            seo = theme_info.get('seo_strategy', {})
            if seo and isinstance(seo, dict):
                key_terms = seo.get('key_terms', [])
                competitors = seo.get('competitors', [])
                
                if key_terms and len(key_terms) > 0:
                    key_terms_str = ', '.join(key_terms[:5])
                    prompt += f". Incorporate these key terms naturally: {key_terms_str}"
                
            # Add brand identity information
            brand = theme_info.get('brand_identity', {})
            if brand and isinstance(brand, dict):
                values = brand.get('values', [])
                voice = brand.get('voice', '')
                
                if voice:
                    prompt += f". Write with a {voice} brand voice"
                if values and len(values) > 0:
                    values_str = ', '.join(values[:3])
                    prompt += f" that reflects these values: {values_str}"
                    
        prompt += "."
        logger.info(f"Enhanced content prompt created using theme information")
        
        content_draft = openai_service.generate_content(
            prompt=prompt,
            outline=outline,
            theme=theme,
            tone='professional',
            target_audience='general',
            content_type='article',
            theme_info=theme_info
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
        
        # Create an enhanced prompt for polishing the content using theme.json details
        polish_prompt = f"Polish and improve the following blog post about {topic_title}."
        
        # Add theme-specific information from theme.json if available
        if theme_info:
            # Extract content strategy information
            content_strategy = theme_info.get('content_strategy', {})
            if content_strategy:
                tone = content_strategy.get('tone', 'professional')
                style = content_strategy.get('style', '')
                voice = content_strategy.get('voice', '')
                
                if tone:
                    polish_prompt += f" Ensure the tone is {tone}"
                if style:
                    polish_prompt += f" with a {style} style"
                if voice:
                    polish_prompt += f" and {voice} voice"
            
            # Add SEO and keyword information
            seo = theme_info.get('seo_strategy', {})
            if seo and isinstance(seo, dict):
                key_terms = seo.get('key_terms', [])
                seo_goals = seo.get('goals', [])
                
                if key_terms and len(key_terms) > 0:
                    key_terms_str = ', '.join(key_terms[:5])
                    polish_prompt += f". Ensure these key terms are well-integrated: {key_terms_str}"
                if seo_goals and len(seo_goals) > 0:
                    goals_str = ', '.join(seo_goals[:2])
                    polish_prompt += f". Keep in mind these SEO goals: {goals_str}"
            
            # Add brand identity information
            brand = theme_info.get('brand_identity', {})
            if brand and isinstance(brand, dict):
                values = brand.get('values', [])
                messaging = brand.get('key_messaging', [])
                
                if values and len(values) > 0:
                    values_str = ', '.join(values[:3])
                    polish_prompt += f". Reflect these brand values: {values_str}"
                if messaging and len(messaging) > 0:
                    messaging_str = ', '.join(messaging[:2])
                    polish_prompt += f". Incorporate this key messaging if relevant: {messaging_str}"
        
        # Add general quality requirements
        polish_prompt += ". Make sure the content is well-structured, engaging, factually accurate, and has a logical flow. Improve transitions between sections, enhance clarity, and ensure a strong opening and conclusion."
        
        # Add original draft to polish
        polish_prompt += f"\n\nHere's the draft content to polish:\n\n{content_draft}"
        
        logger.info(f"Enhanced polish prompt created using theme information")
        
        polished_content = openai_service.generate_content(
            prompt=polish_prompt,
            outline=outline,
            theme=theme,
            tone='professional',
            target_audience='general',
            content_type='polish',
            theme_info=theme_info
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
        # Create an enhanced image prompt based on the topic, theme, and theme.json details
        image_prompt = f"Create a professional featured image for a blog post about '{topic_title}'."
        if theme:
            image_prompt += f" The blog's theme is '{theme}'."
            
        # Add theme-specific styling from theme.json if available
        if theme_info:
            # Extract visual style information
            visual_style = theme_info.get('visual_style', {})
            if visual_style:
                style_description = visual_style.get('description', '')
                color_palette = visual_style.get('color_palette', [])
                imagery_style = visual_style.get('imagery_style', '')
                
                if style_description:
                    image_prompt += f" Visual style: {style_description}."
                if color_palette and len(color_palette) > 0:
                    colors_str = ', '.join(color_palette)
                    image_prompt += f" Use this color palette: {colors_str}."
                if imagery_style:
                    image_prompt += f" The imagery style should be {imagery_style}."
            
            # Add audience information if available to better target the image
            audience = theme_info.get('target_audience', {})
            if audience and isinstance(audience, dict):
                demographics = audience.get('demographics', '')
                interests = audience.get('interests', [])
                
                if demographics:
                    image_prompt += f" Target audience demographics: {demographics}."
                if interests and len(interests) > 0:
                    interests_str = ', '.join(interests[:3])  # Use top 3 interests
                    image_prompt += f" Incorporate elements relevant to these interests: {interests_str}."
            
            # Add brand identity information if available
            brand = theme_info.get('brand_identity', {})
            if brand and isinstance(brand, dict):
                brand_values = brand.get('values', [])
                brand_voice = brand.get('voice', '')
                
                if brand_values and len(brand_values) > 0:
                    values_str = ', '.join(brand_values[:3])  # Use top 3 values
                    image_prompt += f" Reflect these brand values: {values_str}."
                if brand_voice:
                    image_prompt += f" The brand voice is {brand_voice}."
                    
        logger.info(f"Enhanced image prompt created using theme information")
        
        # Generate the image with theme-specific styling
        image_info = openai_service.generate_image(
            prompt=image_prompt,
            size="1024x1024",
            style="natural",
            quality="standard",
            theme_info=theme_info
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