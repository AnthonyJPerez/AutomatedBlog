"""
Integration of OpenAIService with AIOptimizationService to reduce API costs.

This module wraps the existing OpenAIService with cost optimization features:
1. Response caching for frequently requested content
2. Token counting and budget management
3. Model selection based on content type
4. Prompt compression for long inputs
"""

import os
import json
import logging
import hashlib
import datetime
from typing import Dict, Any, Optional, List, Tuple, Union

from shared.openai_service import OpenAIService
from shared.prompt_optimization import AIOptimizationService

class OptimizedOpenAIService:
    """
    Enhanced OpenAI service with cost optimization features.
    Wraps the standard OpenAIService with AI cost optimization techniques.
    """
    
    def __init__(self, cache_ttl_seconds=3600, enable_caching=True):
        """
        Initialize the optimized OpenAI service.
        
        Args:
            cache_ttl_seconds (int): How long to keep cached responses (in seconds)
            enable_caching (bool): Whether to enable response caching
        """
        self.logger = logging.getLogger('optimized_openai_service')
        self.openai_service = OpenAIService()
        self.optimization_service = AIOptimizationService(
            cache_ttl_seconds=cache_ttl_seconds,
            enable_caching=enable_caching
        )
        
        # Budget controls
        self.daily_budget = float(os.environ.get("OPENAI_DAILY_BUDGET", "10.0"))  # Default $10/day
        self.monthly_budget = float(os.environ.get("OPENAI_MONTHLY_BUDGET", "300.0"))  # Default $300/month
        
        # Usage tracking
        self.usage = {
            "total_tokens": 0,
            "estimated_cost": 0.0,
            "requests": 0,
            "cached_requests": 0,
            "api_errors": 0
        }
        
        # Model costs per 1k tokens (input/output)
        self.model_costs = {
            "gpt-4o": (0.01, 0.03),        # $0.01 per 1K input tokens, $0.03 per 1K output tokens
            "gpt-4": (0.03, 0.06),         # $0.03 per 1K input tokens, $0.06 per 1K output tokens
            "gpt-3.5-turbo": (0.0015, 0.002)  # $0.0015 per 1K input tokens, $0.002 per 1K output tokens
        }
        
        self.logger.info(f"OptimizedOpenAIService initialized with daily budget ${self.daily_budget}")
    
    def _compute_cache_key(self, function_name: str, *args, **kwargs) -> str:
        """
        Compute a cache key for a specific function call.
        
        Args:
            function_name (str): The function being called
            *args, **kwargs: The arguments to the function
            
        Returns:
            str: A cache key
        """
        # Convert args and kwargs to a stable string representation
        args_str = json.dumps(args, sort_keys=True)
        kwargs_str = json.dumps(kwargs, sort_keys=True)
        
        # Create a hash that uniquely identifies this function call
        key_material = f"{function_name}|{args_str}|{kwargs_str}"
        return hashlib.md5(key_material.encode('utf-8')).hexdigest()
    
    def _estimate_cost(self, prompt_tokens: int, completion_tokens: int, model: str) -> float:
        """
        Estimate the cost of an API call.
        
        Args:
            prompt_tokens (int): Number of tokens in the prompt
            completion_tokens (int): Number of tokens in the completion
            model (str): The model used
            
        Returns:
            float: Estimated cost in USD
        """
        # Get cost rates for the model (default to gpt-3.5-turbo if unknown)
        input_cost, output_cost = self.model_costs.get(
            model, 
            self.model_costs["gpt-3.5-turbo"]
        )
        
        # Calculate costs for prompt and completion
        prompt_cost = (prompt_tokens / 1000) * input_cost
        completion_cost = (completion_tokens / 1000) * output_cost
        
        return prompt_cost + completion_cost
    
    def _check_budget(self, estimated_cost: float) -> bool:
        """
        Check if a request is within budget constraints.
        
        Args:
            estimated_cost (float): Estimated cost of the request
            
        Returns:
            bool: True if within budget, False otherwise
        """
        # Get today's date and current month
        today = datetime.datetime.utcnow().strftime("%Y-%m-%d")
        month = datetime.datetime.utcnow().strftime("%Y-%m")
        
        # Check if we're within daily budget
        today_usage = self.usage.get("daily", {}).get(today, 0.0)
        if today_usage + estimated_cost > self.daily_budget:
            self.logger.warning(f"Daily budget exceeded: ${today_usage} + ${estimated_cost} > ${self.daily_budget}")
            return False
            
        # Check if we're within monthly budget
        month_usage = self.usage.get("monthly", {}).get(month, 0.0)
        if month_usage + estimated_cost > self.monthly_budget:
            self.logger.warning(f"Monthly budget exceeded: ${month_usage} + ${estimated_cost} > ${self.monthly_budget}")
            return False
            
        return True
    
    def _track_usage(self, prompt_tokens: int, completion_tokens: int, model: str, is_cached: bool):
        """
        Track API usage and costs.
        
        Args:
            prompt_tokens (int): Number of tokens in the prompt
            completion_tokens (int): Number of tokens in the completion
            model (str): The model used
            is_cached (bool): Whether the response was from cache
        """
        # Calculate cost
        cost = self._estimate_cost(prompt_tokens, completion_tokens, model)
        
        # Update overall usage
        self.usage["total_tokens"] += prompt_tokens + completion_tokens
        self.usage["estimated_cost"] += cost
        self.usage["requests"] += 1
        
        if is_cached:
            self.usage["cached_requests"] += 1
            
        # Update daily usage
        today = datetime.datetime.utcnow().strftime("%Y-%m-%d")
        month = datetime.datetime.utcnow().strftime("%Y-%m")
        
        if "daily" not in self.usage:
            self.usage["daily"] = {}
            
        if today not in self.usage["daily"]:
            self.usage["daily"][today] = 0.0
            
        self.usage["daily"][today] += cost
        
        # Update monthly usage
        if "monthly" not in self.usage:
            self.usage["monthly"] = {}
            
        if month not in self.usage["monthly"]:
            self.usage["monthly"][month] = 0.0
            
        self.usage["monthly"][month] += cost
        
        # Log usage
        self.logger.info(
            f"API request: model={model}, tokens={prompt_tokens+completion_tokens}, "
            f"cost=${cost:.5f}, cached={is_cached}"
        )
    
    def generate_content(self, prompt, outline=None, theme=None, tone="professional", 
                        target_audience="general", content_type="article"):
        """
        Generate content with cost optimization.
        
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
        # Validate input
        if not prompt:
            self.logger.error("Empty prompt provided")
            return "Error: No content prompt provided"
        
        # Format outline as string for caching purposes
        outline_str = ""
        if outline:
            if isinstance(outline, dict):
                outline_str = json.dumps(outline, sort_keys=True)
            else:
                outline_str = str(outline)
        
        # Prepare cache key components
        cache_params = {
            "outline": outline_str,
            "theme": theme or "",
            "tone": tone,
            "target_audience": target_audience,
            "content_type": content_type
        }
        
        # Generate cache key
        cache_key = self._compute_cache_key("generate_content", prompt, **cache_params)
        
        # Check if we have a cached response
        cached_response = self.optimization_service.get_cached_response(cache_key)
        if cached_response:
            # Track cached usage (minimal token count since it's cached)
            self._track_usage(10, 10, self.openai_service.draft_model, True)
            return cached_response
        
        # Select the appropriate model based on content type (allow higher models to fallback)
        complexity = 3  # Default complexity level (1-5)
        model = self.optimization_service.select_appropriate_model(content_type, complexity)
        
        # Count tokens in the prompt to ensure we're within limits
        full_prompt = f"{prompt}\nTheme: {theme or ''}\nTone: {tone}\nAudience: {target_audience}\nOutline: {outline_str}"
        prompt_tokens = self.optimization_service.count_tokens(full_prompt, model)
        
        # Estimate max completion tokens
        max_completion_tokens = 4000 if content_type == "polish" else 3000
        
        # Estimate cost before making the API call
        estimated_cost = self._estimate_cost(prompt_tokens, max_completion_tokens, model)
        
        # Check if we're within budget
        if not self._check_budget(estimated_cost):
            self.logger.warning(f"Budget exceeded, using cheaper model for: {prompt[:50]}...")
            # Fall back to cheaper model
            model = "gpt-3.5-turbo"
            estimated_cost = self._estimate_cost(prompt_tokens, max_completion_tokens, model)
            
            # If still over budget, return error message
            if not self._check_budget(estimated_cost):
                return (
                    "# Budget Limit Reached\n\n"
                    "Content generation is temporarily unavailable due to budget constraints. "
                    "Please try again later or contact support to increase your budget allocation."
                )
        
        # Optimize the prompt if it's too long
        if prompt_tokens > 3000:
            self.logger.info(f"Optimizing long prompt: {prompt_tokens} tokens")
            full_prompt = self.optimization_service.optimize_prompt(full_prompt, 3000, model)
        
        try:
            # Make the actual API call using the standard service
            response = self.openai_service.generate_content(
                prompt=prompt,
                outline=outline,
                theme=theme,
                tone=tone,
                target_audience=target_audience,
                content_type=content_type
            )
            
            # Estimate completion tokens (in production, get this from the API response)
            completion_tokens = self.optimization_service.count_tokens(response, model)
            
            # Track usage
            self._track_usage(prompt_tokens, completion_tokens, model, False)
            
            # Cache the response
            self.optimization_service.cache_response(
                cache_key, response, prompt_tokens + completion_tokens
            )
            
            return response
            
        except Exception as e:
            self.logger.error(f"Error generating content: {str(e)}")
            self.usage["api_errors"] += 1
            
            # Return error message
            return (
                f"# Error Generating Content\n\n"
                f"There was an error generating content for topic: {prompt[:50]}...\n\n"
                f"Please try again later or contact support if the problem persists."
            )
    
    def generate_outline(self, topic, theme, tone="professional", target_audience="general"):
        """
        Generate a content outline with cost optimization.
        
        Args:
            topic (str): The topic to create an outline for
            theme (str): The blog theme for context
            tone (str): The desired tone of content
            target_audience (str): The target audience
            
        Returns:
            dict: An outline structure with sections
        """
        # Generate cache key
        cache_key = self._compute_cache_key(
            "generate_outline", topic, theme, tone, target_audience
        )
        
        # Check if we have a cached response
        cached_response = self.optimization_service.get_cached_response(cache_key)
        if cached_response:
            # Track cached usage (minimal token count)
            self._track_usage(10, 10, self.openai_service.draft_model, True)
            return cached_response
        
        # Always use the draft model for outlines to save costs
        model = self.openai_service.draft_model
        
        # Count tokens and estimate cost
        full_prompt = f"Outline for: {topic}\nTheme: {theme}\nTone: {tone}\nAudience: {target_audience}"
        prompt_tokens = self.optimization_service.count_tokens(full_prompt, model)
        max_completion_tokens = 1000
        
        # Estimate cost before making the API call
        estimated_cost = self._estimate_cost(prompt_tokens, max_completion_tokens, model)
        
        # Check if we're within budget
        if not self._check_budget(estimated_cost):
            self.logger.warning(f"Budget exceeded for outline generation: {topic}")
            
            # Return simplified outline as fallback
            fallback_outline = {
                "title": topic,
                "sections": [
                    {"title": "Introduction", "points": ["Background information", "Why this topic matters"]},
                    {"title": "Main Section 1", "points": ["Key point 1", "Key point 2"]},
                    {"title": "Main Section 2", "points": ["Key point 1", "Key point 2"]},
                    {"title": "Conclusion", "points": ["Summary", "Call to action"]}
                ]
            }
            return fallback_outline
        
        try:
            # Make the actual API call
            response = self.openai_service.generate_outline(
                topic=topic,
                theme=theme,
                tone=tone,
                target_audience=target_audience
            )
            
            # Estimate completion tokens
            completion_tokens = 0
            if isinstance(response, dict):
                completion_str = json.dumps(response)
                completion_tokens = self.optimization_service.count_tokens(completion_str, model)
            else:
                completion_tokens = 500  # Reasonable fallback estimate
            
            # Track usage
            self._track_usage(prompt_tokens, completion_tokens, model, False)
            
            # Cache the response
            self.optimization_service.cache_response(
                cache_key, response, prompt_tokens + completion_tokens
            )
            
            return response
            
        except Exception as e:
            self.logger.error(f"Error generating outline: {str(e)}")
            self.usage["api_errors"] += 1
            
            # Return a basic outline structure as fallback
            return {
                "title": topic,
                "sections": [
                    {"title": "Introduction", "points": []},
                    {"title": "Main Content", "points": []},
                    {"title": "Conclusion", "points": []}
                ]
            }
    
    def generate_seo_metadata(self, title, content):
        """
        Generate SEO metadata with cost optimization.
        
        Args:
            title (str): The content title
            content (str): The generated content
            
        Returns:
            dict: SEO metadata including meta description, keywords, etc.
        """
        # Only use a portion of the content for caching and token counting
        content_sample = content[:500] if content else ""
        
        # Generate cache key
        cache_key = self._compute_cache_key("generate_seo_metadata", title, content_sample)
        
        # Check if we have a cached response
        cached_response = self.optimization_service.get_cached_response(cache_key)
        if cached_response:
            # Track cached usage (minimal token count)
            self._track_usage(10, 10, self.openai_service.draft_model, True)
            return cached_response
        
        # Always use the draft model for metadata to save costs
        model = self.openai_service.draft_model
        
        # Count tokens and estimate cost
        full_prompt = f"SEO metadata for: {title}\nContent sample: {content_sample}"
        prompt_tokens = self.optimization_service.count_tokens(full_prompt, model)
        max_completion_tokens = 800
        
        # Estimate cost before making the API call
        estimated_cost = self._estimate_cost(prompt_tokens, max_completion_tokens, model)
        
        # Check if we're within budget
        if not self._check_budget(estimated_cost):
            self.logger.warning(f"Budget exceeded for SEO metadata generation: {title}")
            
            # Create basic metadata as fallback
            slug = title.lower().replace(' ', '-').replace('?', '').replace('!', '')
            for char in ',.;:@#$%^&*()+={}[]|\\<>/':
                slug = slug.replace(char, '')
            
            fallback_metadata = {
                "meta_description": f"Learn about {title} in this comprehensive guide.",
                "keywords": [title],
                "social_title": title,
                "social_description": f"Read our guide about {title}.",
                "slug": slug
            }
            return fallback_metadata
        
        try:
            # Make the actual API call
            response = self.openai_service.generate_seo_metadata(
                title=title,
                content=content
            )
            
            # Estimate completion tokens
            completion_tokens = 0
            if isinstance(response, dict):
                completion_str = json.dumps(response)
                completion_tokens = self.optimization_service.count_tokens(completion_str, model)
            else:
                completion_tokens = 300  # Reasonable fallback estimate
            
            # Track usage
            self._track_usage(prompt_tokens, completion_tokens, model, False)
            
            # Cache the response
            self.optimization_service.cache_response(
                cache_key, response, prompt_tokens + completion_tokens
            )
            
            return response
            
        except Exception as e:
            self.logger.error(f"Error generating SEO metadata: {str(e)}")
            self.usage["api_errors"] += 1
            
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
    
    def get_usage_statistics(self):
        """
        Get usage statistics for the optimized service.
        
        Returns:
            dict: Usage statistics and cache information
        """
        cache_stats = self.optimization_service.get_cache_stats()
        
        return {
            "usage": self.usage,
            "cache": cache_stats,
            "config": {
                "daily_budget": self.daily_budget,
                "monthly_budget": self.monthly_budget,
                "caching_enabled": self.optimization_service.enable_caching,
                "cache_ttl_seconds": self.optimization_service.cache_ttl_seconds
            }
        }
    
    def clear_cache(self):
        """Clear the response cache."""
        return self.optimization_service.clear_cache()
    
    def set_api_key(self, api_key):
        """Pass through method to the underlying OpenAI service."""
        return self.openai_service.set_api_key(api_key)