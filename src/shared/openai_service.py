import os
import json
import logging
import openai
import base64
import requests
import datetime
from io import BytesIO
from azure.identity import DefaultAzureCredential
from azure.keyvault.secrets import SecretClient

class OpenAIService:
    """
    Service for generating content using OpenAI's models.
    Supports both direct OpenAI API and Azure OpenAI Service.
    Provides methods for generating blog content, SEO recommendations, and outlines.
    """
    
    def __init__(self):
        """Initialize the OpenAI service with API credentials."""
        # Configure logger
        self.logger = logging.getLogger('OpenAIService')
        
        # Try to get API key from environment variable first
        api_key = os.environ.get("OPENAI_API_KEY")
        
        # If not in environment, try to get from Key Vault
        if not api_key:
            key_vault_name = os.environ.get("KEY_VAULT_NAME")
            if key_vault_name:
                try:
                    # Use managed identity to access Key Vault
                    credential = DefaultAzureCredential()
                    key_vault_uri = f"https://{key_vault_name}.vault.azure.net/"
                    secret_client = SecretClient(vault_url=key_vault_uri, credential=credential)
                    
                    # Get OpenAI API key from Key Vault
                    api_key = secret_client.get_secret("OpenAIApiKey").value
                except Exception as e:
                    self.logger.error(f"Error retrieving OpenAI API key from Key Vault: {str(e)}")
        
        # Check if using Azure OpenAI or direct OpenAI
        self.use_azure = os.environ.get("OPENAI_API_TYPE") == "azure"
        
        if self.use_azure:
            # Azure OpenAI setup
            openai.api_type = "azure"
            openai.api_base = os.environ.get("OPENAI_API_BASE")
            openai.api_version = os.environ.get("OPENAI_API_VERSION", "2023-03-15-preview")
            openai.api_key = api_key
        else:
            # Direct OpenAI setup
            openai.api_key = api_key
        
        # Default models
        self.draft_model = os.environ.get("OPENAI_DRAFT_MODEL", "gpt-3.5-turbo")
        self.polish_model = os.environ.get("OPENAI_POLISH_MODEL", "gpt-4o")  # Using the newest model by default
        
        self.logger.info(f"OpenAI service initialized. Using Azure: {self.use_azure}")
    
    def _get_completion(self, prompt, model, max_tokens=2000, temperature=0.7):
        """
        Get completion from OpenAI API.
        
        Args:
            prompt (str): The text prompt to generate from
            model (str): The model to use
            max_tokens (int): Maximum number of tokens to generate
            temperature (float): Creativity parameter (0.0-1.0)
            
        Returns:
            str: The generated text
        """
        try:
            if self.use_azure:
                # Azure OpenAI requires deployment name as model
                response = openai.ChatCompletion.create(
                    engine=model,  # Azure deployment name
                    messages=[{
                        "role": "system",
                        "content": "You are a professional content writer with expertise in SEO and blog writing."
                    }, {
                        "role": "user",
                        "content": prompt
                    }],
                    max_tokens=max_tokens,
                    temperature=temperature
                )
            else:
                # Direct OpenAI
                response = openai.ChatCompletion.create(
                    model=model,
                    messages=[{
                        "role": "system",
                        "content": "You are a professional content writer with expertise in SEO and blog writing."
                    }, {
                        "role": "user",
                        "content": prompt
                    }],
                    max_tokens=max_tokens,
                    temperature=temperature
                )
            
            return response.choices[0].message.content.strip()
        
        except Exception as e:
            self.logger.error(f"Error in OpenAI API call: {str(e)}")
            raise
    
    def generate_outline(self, topic, theme, tone="professional", target_audience="general"):
        """
        Generate a content outline for a given topic.
        
        Args:
            topic (str): The topic to create an outline for
            theme (str): The blog theme for context
            tone (str): The desired tone of content
            target_audience (str): The target audience
            
        Returns:
            dict: An outline structure with sections
        """
        prompt = f"""
        Create a detailed outline for a blog post about "{topic}".
        Theme/context: {theme}
        Tone: {tone}
        Target audience: {target_audience}
        
        Return the outline in the following JSON structure:
        {{
            "title": "Engaging title for the blog post",
            "sections": [
                {{
                    "title": "Section title",
                    "points": ["Key point 1", "Key point 2", ...]
                }},
                ...
            ]
        }}
        
        Include at least 5 sections, with an introduction and conclusion.
        """
        
        try:
            # Use the draft model for outlines
            response = self._get_completion(prompt, self.draft_model, max_tokens=1000, temperature=0.7)
            
            # Parse the JSON response
            try:
                outline = json.loads(response)
                return outline
            except json.JSONDecodeError:
                # If the response isn't valid JSON, extract what we can
                self.logger.warning("OpenAI didn't return valid JSON for the outline. Attempting to parse manually.")
                
                # Create a basic outline structure
                outline = {
                    "title": topic,
                    "sections": [
                        {"title": "Introduction", "points": []},
                        {"title": "Main Content", "points": []},
                        {"title": "Conclusion", "points": []}
                    ]
                }
                
                return outline
                
        except Exception as e:
            self.logger.error(f"Error generating outline: {str(e)}")
            # Return a basic outline structure as fallback
            return {
                "title": topic,
                "sections": [
                    {"title": "Introduction", "points": []},
                    {"title": "Main Content", "points": []},
                    {"title": "Conclusion", "points": []}
                ]
            }
    
    def generate_content(self, prompt, outline=None, theme=None, tone="professional", target_audience="general", content_type="article"):
        """
        Generate content based on a prompt or outline.
        
        Args:
            prompt (str): The prompt or topic for content generation
            outline (dict, optional): The outline structure to follow
            theme (str, optional): The blog theme for context
            tone (str): The desired tone of content
            target_audience (str): The target audience
            content_type (str): Type of content to generate (article, draft, polish)
            
        Returns:
            str: The generated content
        """
        # Select the appropriate model based on content type
        if content_type == "polish":
            model = self.polish_model
            max_tokens = 4000
            temperature = 0.6
            polish_guidance = """
            Please polish and enhance the content to make it more engaging, 
            well-structured, and SEO-friendly. Add necessary transitions,
            improve language, and ensure it's high-quality content that 
            would rank well in search engines.
            """
        else:  # draft or article
            model = self.draft_model
            max_tokens = 3000
            temperature = 0.7
            polish_guidance = ""
        
        # Format the outline as text if provided
        outline_text = ""
        if outline:
            outline_text = f"\nPlease follow this outline:\n"
            
            if isinstance(outline, dict):
                outline_text += f"Title: {outline.get('title', 'Main Topic')}\n\n"
                
                for i, section in enumerate(outline.get('sections', [])):
                    outline_text += f"{i+1}. {section.get('title', 'Section')}\n"
                    
                    for point in section.get('points', []):
                        outline_text += f"   - {point}\n"
                    
                    outline_text += "\n"
            elif isinstance(outline, str):
                outline_text += outline
        
        # Create the full prompt
        theme_context = f"\nTheme/context: {theme}" if theme else ""
        
        full_prompt = f"""
        {prompt}
        {theme_context}
        Tone: {tone}
        Target audience: {target_audience}
        {outline_text}
        
        {polish_guidance}
        
        Format the article in Markdown with proper headings (#, ##, ###),
        and include:
        - Engaging introduction that hooks the reader
        - Well-structured content with clear sections
        - SEO-optimized headings and subheadings
        - Conclusion with key takeaways
        - Proper transitions between sections
        
        The content should be authoritative, factual, and valuable to the reader.
        """
        
        try:
            content = self._get_completion(full_prompt, model, max_tokens=max_tokens, temperature=temperature)
            return content
            
        except Exception as e:
            self.logger.error(f"Error generating content: {str(e)}")
            # Return a basic error message as content
            topic = prompt.strip()[:50]  # Use the beginning of the prompt as the topic
            theme_text = f"related to {theme}" if theme else ""
            
            return f"""
            # About {topic}
            
            *Content generation is temporarily unavailable. Please try again later.*
            
            ## About this topic
            
            {topic} is an important subject {theme_text}.
            
            *[This is a placeholder due to content generation error]*
            """
    
    def generate_seo_metadata(self, title, content):
        """
        Generate SEO metadata for a piece of content.
        
        Args:
            title (str): The content title
            content (str): The generated content
            
        Returns:
            dict: SEO metadata including meta description, keywords, etc.
        """
        prompt = f"""
        Generate SEO metadata for the following blog post.
        
        Title: {title}
        
        Content (first 500 characters):
        {content[:500]}...
        
        Return the metadata in the following JSON structure:
        {{
            "meta_description": "Compelling meta description under 160 characters",
            "keywords": ["keyword1", "keyword2", ...],
            "social_title": "Engaging social media title",
            "social_description": "Social media description under 100 characters",
            "slug": "url-friendly-slug"
        }}
        
        Ensure the meta description is compelling and under 160 characters.
        Include 5-7 relevant keywords.
        The slug should be URL-friendly (lowercase, hyphens instead of spaces).
        """
        
        try:
            # Use the draft model for metadata
            response = self._get_completion(prompt, self.draft_model, max_tokens=800, temperature=0.5)
            
            # Parse the JSON response
            try:
                metadata = json.loads(response)
                return metadata
            except json.JSONDecodeError:
                # If the response isn't valid JSON, extract what we can
                self.logger.warning("OpenAI didn't return valid JSON for metadata. Using defaults.")
                
                # Create basic metadata
                slug = title.lower().replace(' ', '-').replace('?', '').replace('!', '')
                for char in ',.;:@#$%^&*()+={}[]|\\<>/':
                    slug = slug.replace(char, '')
                
                metadata = {
                    "meta_description": f"Learn about {title} in this comprehensive guide.",
                    "keywords": [title],
                    "social_title": title,
                    "social_description": f"Read our guide about {title}.",
                    "slug": slug
                }
                
                return metadata
                
        except Exception as e:
            self.logger.error(f"Error generating SEO metadata: {str(e)}")
            
            # Create basic metadata as fallback
            slug = title.lower().replace(' ', '-').replace('?', '').replace('!', '')
            for char in ',.;:@#$%^&*()+={}[]|\\<>/':
                slug = slug.replace(char, '')
            
            return {
                "meta_description": f"Learn about {title} in this comprehensive guide.",
                "keywords": [title],
                "social_title": title,
                "social_description": f"Read our guide about {title}.",
                "slug": slug
            }
            
    def generate_json(self, prompt, model=None, max_tokens=2000, temperature=0.5):
        """
        Generate JSON content based on the prompt.
        
        Args:
            prompt (str): The prompt to generate JSON from
            model (str, optional): The model to use, uses self.draft_model if not specified
            max_tokens (int): Maximum tokens to generate
            temperature (float): Creativity parameter (0.0-1.0)
            
        Returns:
            str: JSON string response
        """
        if model is None:
            model = self.draft_model
            
        try:
            # Use structured output format (available in newer API versions)
            if self.use_azure:
                response = openai.chat.completions.create(
                    engine=model,  # Azure deployment name
                    messages=[{
                        "role": "system",
                        "content": "You are a structured data generator that produces valid JSON."
                    }, {
                        "role": "user",
                        "content": prompt
                    }],
                    max_tokens=max_tokens,
                    temperature=temperature,
                    response_format={"type": "json_object"}
                )
            else:
                # Direct OpenAI
                response = openai.chat.completions.create(
                    model=model,
                    messages=[{
                        "role": "system",
                        "content": "You are a structured data generator that produces valid JSON."
                    }, {
                        "role": "user",
                        "content": prompt
                    }],
                    max_tokens=max_tokens,
                    temperature=temperature,
                    response_format={"type": "json_object"}
                )
            
            return response.choices[0].message.content.strip()
            
        except Exception as e:
            self.logger.error(f"Error generating JSON: {str(e)}")
            # Return empty JSON as fallback
            return '{}'
    
    def generate_image(self, prompt, size="1024x1024", style="natural", quality="standard"):
        """
        Generate an image using DALL-E 3.
        
        Args:
            prompt (str): The text prompt to generate an image from
            size (str): Image size (1024x1024, 1792x1024, or 1024x1792)
            style (str): Image style (natural, vivid, illustration, 3d-render, painting, minimalist)
            quality (str): Image quality (standard or hd)
            
        Returns:
            dict: A dictionary containing image data:
                - 'success': Boolean indicating success
                - 'url': URL of the generated image (if available) 
                - 'b64_json': Base64 encoded image (if available)
                - 'error': Error message (if applicable)
        """
        try:
            # Validate parameters
            valid_sizes = ["1024x1024", "1792x1024", "1024x1792"]
            # Map custom styles to DALL-E compatible styles
            style_mapping = {
                "natural": "natural",
                "vivid": "vivid",
                "illustration": "vivid",  # Use vivid for illustration
                "3d-render": "vivid",     # Use vivid for 3D render 
                "painting": "vivid",      # Use vivid for painting
                "minimalist": "natural"   # Use natural for minimalist
            }
            valid_qualities = ["standard", "hd"]
            
            if size not in valid_sizes:
                size = "1024x1024"
                
            # Translate custom style to DALL-E style parameter
            dall_e_style = "natural"
            if style in style_mapping:
                dall_e_style = style_mapping[style]
            
            if quality not in valid_qualities:
                quality = "standard"
            
            # Enhance the prompt for better results based on style
            style_prompt = ""
            if style == "illustration":
                style_prompt = "Create an illustration in a clean, modern style. "
            elif style == "3d-render":
                style_prompt = "Create a 3D rendered image with realistic lighting and textures. "
            elif style == "painting":
                style_prompt = "Create an artistic painting with visible brushstrokes and rich colors. "
            elif style == "minimalist":
                style_prompt = "Create a minimalist image with clean lines, limited colors, and simple composition. "
            
            enhanced_prompt = f"""
            {style_prompt}Create a high-quality, professional image for a blog post with the following description:
            
            {prompt}
            
            The image should be visually appealing, relevant to the topic, and suitable for a professional blog.
            Do not include any text in the image unless specifically requested.
            """
            
            # Generate the image
            if self.use_azure:
                # For Azure OpenAI
                response = openai.Image.create(
                    prompt=enhanced_prompt,
                    n=1,
                    size=size,
                    quality=quality,
                    style=dall_e_style,
                    response_format="b64_json"
                )
                b64_data = response.data[0].b64_json
                
                # Save image locally
                image_path = self._save_base64_image(b64_data, "blog_image")
                
                return {
                    "success": True,
                    "b64_json": b64_data,
                    "local_path": image_path
                }
            else:
                # For direct OpenAI API
                response = openai.images.generate(
                    model="dall-e-3",
                    prompt=enhanced_prompt,
                    n=1,
                    size=size,
                    quality=quality,
                    style=style,
                    response_format="b64_json"
                )
                b64_data = response.data[0].b64_json
                
                # Save image locally
                image_path = self._save_base64_image(b64_data, "blog_image")
                
                return {
                    "success": True,
                    "b64_json": b64_data,
                    "local_path": image_path
                }
                
        except Exception as e:
            error_msg = f"Error generating image: {str(e)}"
            self.logger.error(error_msg)
            return {
                "success": False,
                "error": error_msg
            }
    
    def _save_base64_image(self, b64_data, prefix="image"):
        """
        Save a base64 encoded image to disk.
        
        Args:
            b64_data (str): Base64 encoded image data
            prefix (str): Prefix for the image filename
            
        Returns:
            str: Path to the saved image
        """
        try:
            # Create static/images directory if it doesn't exist
            images_dir = os.path.join("static", "images")
            os.makedirs(images_dir, exist_ok=True)
            
            # Generate a unique filename
            timestamp = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
            filename = f"{prefix}_{timestamp}.png"
            file_path = os.path.join(images_dir, filename)
            
            # Decode and save the image
            image_data = base64.b64decode(b64_data)
            with open(file_path, "wb") as f:
                f.write(image_data)
            
            return file_path
            
        except Exception as e:
            self.logger.error(f"Error saving base64 image: {str(e)}")
            return None