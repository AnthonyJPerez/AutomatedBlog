import os
import json
import logging
import time
from openai import OpenAI

class OpenAIService:
    """
    Service for generating content using OpenAI.
    Handles content generation, outline creation, and SEO metadata generation.
    """
    
    def __init__(self):
        self.logger = logging.getLogger('openai_service')
        
        # Get OpenAI API key from environment variables
        api_key = os.environ.get("OPENAI_API_KEY")
        
        if not api_key:
            self.logger.error("OpenAI API key not found in environment variables")
        
        # Initialize OpenAI client
        self.client = OpenAI(api_key=api_key)
        
        # the newest OpenAI model is "gpt-4o" which was released May 13, 2024.
        # do not change this unless explicitly requested by the user
        self.model = "gpt-4o"
    
    def generate_outline(self, topic, theme, tone, target_audience):
        """
        Generate an outline for a blog post based on the given topic and parameters.
        
        Args:
            topic (str): The topic to generate an outline for
            theme (str): The thematic focus of the blog
            tone (str): The desired tone of the content
            target_audience (str): The intended audience for the content
            
        Returns:
            list: A structured outline for the blog post
        """
        # Define the system message for the outline generation
        system_message = (
            "You are a professional content outline generator. "
            "Create a detailed, well-structured outline for a blog post. "
            "The outline should include an introduction, 3-5 main sections with subsections, and a conclusion. "
            "Return the outline as a JSON object with this structure: "
            "{'sections': [{'title': 'section title', 'subsections': ['subsection 1', 'subsection 2']}]}"
        )
        
        # Define the user message with all the parameters
        user_message = (
            f"Generate a detailed outline for a blog post about '{topic}'. "
            f"The blog's theme is '{theme}' and should be written in a '{tone}' tone. "
            f"The target audience is '{target_audience}'. "
            f"Make the outline engaging and comprehensive, covering all important aspects of the topic."
        )
        
        # Make the API call with retries
        max_retries = 3
        for attempt in range(max_retries):
            try:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": system_message},
                        {"role": "user", "content": user_message}
                    ],
                    response_format={"type": "json_object"},
                    temperature=0.7
                )
                
                # Parse the response
                outline = json.loads(response.choices[0].message.content)
                return outline
                
            except Exception as e:
                self.logger.error(f"Error generating outline (attempt {attempt+1}/{max_retries}): {str(e)}")
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)  # Exponential backoff
                else:
                    raise
    
    def generate_content(self, topic, outline, theme, tone, target_audience, content_type="article"):
        """
        Generate full blog content based on the outline and parameters.
        
        Args:
            topic (str): The main topic of the content
            outline (dict): The outline structure to follow
            theme (str): The thematic focus of the blog
            tone (str): The desired tone of the content
            target_audience (str): The intended audience for the content
            content_type (str): The type of content to generate (article, listicle, etc.)
            
        Returns:
            str: The generated blog content in HTML format
        """
        # Convert outline to a string representation
        outline_str = json.dumps(outline, indent=2)
        
        # Define the system message for content generation
        system_message = (
            "You are a professional blog content writer. "
            "Create high-quality, engaging blog content following the provided outline. "
            "The content should be well-structured, include HTML formatting, and be optimized for web reading. "
            "Use appropriate headings (h1, h2, h3), paragraphs, lists, and other HTML elements. "
            "Do not include placeholders for images or other media. "
            "Write complete, informative content that provides value to the reader."
        )
        
        # Define the user message with all the parameters
        user_message = (
            f"Write a complete {content_type} about '{topic}' following this outline:\n\n"
            f"{outline_str}\n\n"
            f"The blog's theme is '{theme}' and should be written in a '{tone}' tone. "
            f"The target audience is '{target_audience}'. "
            f"Make the content comprehensive, engaging, and valuable to the reader. "
            f"Include proper HTML formatting with headings, paragraphs, and lists. "
            f"The content should be ready to publish on a WordPress blog."
        )
        
        # Make the API call with retries
        max_retries = 3
        for attempt in range(max_retries):
            try:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": system_message},
                        {"role": "user", "content": user_message}
                    ],
                    temperature=0.7,
                    max_tokens=3000
                )
                
                # Get the generated content
                content = response.choices[0].message.content
                return content
                
            except Exception as e:
                self.logger.error(f"Error generating content (attempt {attempt+1}/{max_retries}): {str(e)}")
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)  # Exponential backoff
                else:
                    raise
    
    def generate_seo_metadata(self, title, content):
        """
        Generate SEO metadata for the blog post.
        
        Args:
            title (str): The title of the blog post
            content (str): The content of the blog post
            
        Returns:
            dict: SEO metadata including meta description, keywords, and social media descriptions
        """
        # Define the system message for SEO metadata generation
        system_message = (
            "You are an SEO expert. Generate comprehensive SEO metadata for a blog post. "
            "Return the metadata as a JSON object with the following structure: "
            "{"
            "'meta_description': 'A compelling 150-160 character description for search engines', "
            "'keywords': ['keyword1', 'keyword2', ...], "
            "'social_title': 'An engaging title for social media sharing', "
            "'social_description': 'A compelling description for social media sharing', "
            "'slug': 'url-friendly-slug-for-the-post'"
            "}"
        )
        
        # Define the user message with the title and a summary of the content
        content_summary = content[:2000] + "..." if len(content) > 2000 else content
        user_message = (
            f"Generate SEO metadata for a blog post with the title: '{title}'. "
            f"Here's a summary of the content:\n\n{content_summary}\n\n"
            f"Provide a meta description (150-160 characters), relevant keywords, "
            f"social media title and description, and a URL-friendly slug."
        )
        
        # Make the API call with retries
        max_retries = 3
        for attempt in range(max_retries):
            try:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": system_message},
                        {"role": "user", "content": user_message}
                    ],
                    response_format={"type": "json_object"},
                    temperature=0.5
                )
                
                # Parse the response
                seo_metadata = json.loads(response.choices[0].message.content)
                return seo_metadata
                
            except Exception as e:
                self.logger.error(f"Error generating SEO metadata (attempt {attempt+1}/{max_retries}): {str(e)}")
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)  # Exponential backoff
                else:
                    raise
