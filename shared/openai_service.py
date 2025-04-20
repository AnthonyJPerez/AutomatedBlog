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
        
        # Set default models
        self.draft_model = "gpt-3.5-turbo"
        self.polish_model = "gpt-4o"  # Latest model as of April 2025
        self.chat_model = "gpt-4o"    # Default chat model
        
        # Create client attribute (will be set if not using Azure)
        self.client = None
        self.use_azure = False
        
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
            
            # If still no API key, check global config.json
            if not api_key:
                try:
                    if os.path.exists("data/global_config.json"):
                        with open("data/global_config.json", 'r') as f:
                            global_config = json.load(f)
                            if "credentials" in global_config and "openai_api_key" in global_config["credentials"]:
                                api_key = global_config["credentials"]["openai_api_key"]
                except Exception as e:
                    self.logger.error(f"Error reading global config file: {str(e)}")
        
        # Store the API key
        self.api_key = api_key
        
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
    
    def set_api_key(self, api_key):
        """
        Set or update the OpenAI API key.
        
        Args:
            api_key (str): The API key to use
            
        Returns:
            bool: True if successful, False otherwise
        """
        if not api_key:
            self.logger.warning("Empty API key provided, ignoring update")
            return False
            
        try:
            # Update the stored key
            self.api_key = api_key
            
            # Update the openai library with the new key
            if self.use_azure:
                openai.api_key = api_key
            else:
                openai.api_key = api_key
                
            return True
        except Exception as e:
            self.logger.error(f"Error updating API key: {str(e)}")
            return False
    
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
    
    def generate_outline(self, topic, theme, tone="professional", target_audience="general", theme_info=None):
        """
        Generate a content outline for a given topic.
        
        Args:
            topic (str): The topic to create an outline for
            theme (str): The blog theme for context
            tone (str): The desired tone of content
            target_audience (str): The target audience
            theme_info (dict, optional): Enhanced theme information from theme.json
            
        Returns:
            dict: An outline structure with sections
        """
        # Base prompt
        theme_guidance = f"Theme/context: {theme}"
        tone_info = tone
        audience_info = target_audience
        content_types = ""
        
        # Enhance with detailed theme information if available
        if theme_info:
            if "theme_prompt" in theme_info:
                theme_guidance = f"Theme guidance: {theme_info['theme_prompt']}"
            
            if "tone" in theme_info:
                tone_info = theme_info["tone"]
                
            if "target_audience" in theme_info:
                if isinstance(theme_info["target_audience"], list):
                    audience_info = ", ".join(theme_info["target_audience"])
                else:
                    audience_info = theme_info["target_audience"]
                    
            # Include content types if available
            if "content_types" in theme_info and theme_info["content_types"]:
                content_types = "Preferred content types: " + ", ".join(theme_info["content_types"])
        
        prompt = f"""
        Create a detailed outline for a blog post about "{topic}".
        {theme_guidance}
        Tone: {tone_info}
        Target audience: {audience_info}
        {content_types}
        
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
    
    def generate_content(self, prompt, outline=None, theme=None, tone="professional", target_audience="general", content_type="article", theme_info=None):
        """
        Generate content based on a prompt or outline.
        
        Args:
            prompt (str): The prompt or topic for content generation
            outline (dict, optional): The outline structure to follow
            theme (str, optional): The blog theme for context
            tone (str): The desired tone of content
            target_audience (str): The target audience
            content_type (str): Type of content to generate (article, draft, polish)
            theme_info (dict, optional): Enhanced theme information from theme.json
            
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
        
        # Base prompt elements
        theme_context = f"\nTheme/context: {theme}" if theme else ""
        tone_info = tone
        audience_info = target_audience
        style_guide = """
        Format the article in Markdown with proper headings (#, ##, ###),
        and include:
        - Engaging introduction that hooks the reader
        - Well-structured content with clear sections
        - SEO-optimized headings and subheadings
        - Conclusion with key takeaways
        - Proper transitions between sections
        """
        keywords_text = ""
        
        # Enhance with detailed theme information if available
        if theme_info:
            if "theme_prompt" in theme_info:
                theme_context = f"\nTheme guidance: {theme_info['theme_prompt']}"
            
            if "tone" in theme_info:
                tone_info = theme_info["tone"]
                
            if "target_audience" in theme_info:
                if isinstance(theme_info["target_audience"], list):
                    audience_info = ", ".join(theme_info["target_audience"])
                else:
                    audience_info = theme_info["target_audience"]
            
            # Include style guide if available
            if "style_guide" in theme_info and isinstance(theme_info["style_guide"], dict):
                sg = theme_info["style_guide"]
                style_guide = "Style guide:\n"
                
                if "paragraph_length" in sg:
                    style_guide += f"- Paragraph length: {sg['paragraph_length']}\n"
                if "heading_style" in sg:
                    style_guide += f"- Heading style: {sg['heading_style']}\n"
                if "bullet_points" in sg:
                    style_guide += f"- Bullet points: {sg['bullet_points']}\n"
                if "language_complexity" in sg:
                    style_guide += f"- Language complexity: {sg['language_complexity']}\n"
                if "visual_elements" in sg:
                    style_guide += f"- Visual elements: {sg['visual_elements']}\n"
                if "citations" in sg:
                    style_guide += f"- Citations: {sg['citations']}\n"
                
                style_guide += """
                Format the article in Markdown with proper headings (#, ##, ###),
                and include:
                - Engaging introduction that hooks the reader
                - Well-structured content with clear sections
                - SEO-optimized headings and subheadings
                - Conclusion with key takeaways
                - Proper transitions between sections
                """
            
            # Include keywords if available
            if "keywords" in theme_info and theme_info["keywords"]:
                if isinstance(theme_info["keywords"], list):
                    keywords_text = "\nKeywords to incorporate: " + ", ".join(theme_info["keywords"])
        
        # Create the full prompt
        full_prompt = f"""
        {prompt}
        {theme_context}
        Tone: {tone_info}
        Target audience: {audience_info}
        {outline_text}
        {keywords_text}
        
        {polish_guidance}
        
        {style_guide}
        
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
    
    def generate_image(self, prompt, size="1024x1024", style="natural", quality="standard", theme_info=None):
        """
        Generate an image using DALL-E 3.
        
        Args:
            prompt (str): The text prompt to generate an image from
            size (str): Image size (1024x1024, 1792x1024, or 1024x1792)
            style (str): Image style (natural, vivid, illustration, 3d-render, painting, minimalist)
            quality (str): Image quality (standard or hd)
            theme_info (dict, optional): Enhanced theme information from theme.json
            
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
            
            # Base style prompt
            style_prompt = ""
            if style == "illustration":
                style_prompt = "Create an illustration in a clean, modern style. "
            elif style == "3d-render":
                style_prompt = "Create a 3D rendered image with realistic lighting and textures. "
            elif style == "painting":
                style_prompt = "Create an artistic painting with visible brushstrokes and rich colors. "
            elif style == "minimalist":
                style_prompt = "Create a minimalist image with clean lines, limited colors, and simple composition. "
            
            # Default image requirements
            image_requirements = """
            The image should be visually appealing, relevant to the topic, and suitable for a professional blog.
            Do not include any text in the image unless specifically requested.
            """
            
            # Enhance with theme information if available
            theme_context = ""
            visual_style = ""
            brand_elements = ""
            color_palette = ""
            
            if theme_info:
                # Add theme context for better relevance
                if "theme_prompt" in theme_info:
                    theme_context = f"Theme context: {theme_info['theme_prompt']}\n"
                
                # Add visual style guidance
                if "visual_style" in theme_info:
                    if isinstance(theme_info["visual_style"], dict):
                        vs = theme_info["visual_style"]
                        visual_style = "Visual style guidelines:\n"
                        
                        if "mood" in vs:
                            visual_style += f"- Mood: {vs['mood']}\n"
                        if "aesthetic" in vs:
                            visual_style += f"- Aesthetic: {vs['aesthetic']}\n"
                        if "imagery_type" in vs:
                            visual_style += f"- Imagery type: {vs['imagery_type']}\n"
                    elif isinstance(theme_info["visual_style"], str):
                        visual_style = f"Visual style: {theme_info['visual_style']}\n"
                
                # Add brand elements if specified
                if "brand_elements" in theme_info:
                    if isinstance(theme_info["brand_elements"], dict):
                        be = theme_info["brand_elements"]
                        brand_elements = "Brand elements to incorporate:\n"
                        
                        if "logo_elements" in be:
                            brand_elements += f"- Logo elements: {be['logo_elements']}\n"
                        if "colors" in be:
                            brand_elements += f"- Brand colors: {be['colors']}\n"
                        if "fonts" in be:
                            brand_elements += f"- Typography inspired by: {be['fonts']}\n"
                    elif isinstance(theme_info["brand_elements"], list):
                        brand_elements = "Brand elements to incorporate: " + ", ".join(theme_info["brand_elements"]) + "\n"
                
                # Add color palette
                if "color_palette" in theme_info:
                    if isinstance(theme_info["color_palette"], list):
                        color_palette = "Color palette: " + ", ".join(theme_info["color_palette"]) + "\n"
                    elif isinstance(theme_info["color_palette"], str):
                        color_palette = f"Color palette: {theme_info['color_palette']}\n"
            
            enhanced_prompt = f"""
            {style_prompt}Create a high-quality, professional image for a blog post with the following description:
            
            {prompt}
            
            {theme_context}
            {visual_style}
            {brand_elements}
            {color_palette}
            
            {image_requirements}
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
            
    def chat_completion(self, system_message, user_message, temperature=0.7, max_tokens=None):
        """
        Get a chat completion from the OpenAI API
        
        Args:
            system_message: The system message to guide the AI
            user_message: The user message or question
            temperature: Control randomness (0.0-1.0)
            max_tokens: Maximum tokens to generate, or None for model default
            
        Returns:
            str: The generated response text
        """
        try:
            messages = [
                {"role": "system", "content": system_message},
                {"role": "user", "content": user_message}
            ]
            
            # Set up API call params
            params = {
                "model": self.chat_model,
                "messages": messages,
                "temperature": temperature
            }
            
            # Add max_tokens if specified
            if max_tokens is not None:
                params["max_tokens"] = max_tokens
            
            # Check if we're using Azure OpenAI
            if self.use_azure:
                response = openai.ChatCompletion.create(**params)
                return response.choices[0].message.content
            else:
                response = self.client.chat.completions.create(**params)
                return response.choices[0].message.content
        except Exception as e:
            self.logger.error(f"Error in chat completion: {str(e)}")
            return f"Error generating response: {str(e)}"