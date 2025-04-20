"""
Prompt optimization service for reducing AI API costs through various techniques.

This module provides services for:
1. Response caching - to avoid duplicate API calls
2. Token counting - to optimize prompt length
3. Model fallback - to use less expensive models when appropriate
4. Prompt compression - to reduce token usage
5. Response batching - to combine multiple requests

Usage:
    from src.shared.prompt_optimization import AIOptimizationService
    optimization_service = AIOptimizationService()
    
    # Get cached or fresh response
    response = optimization_service.get_optimized_completion(
        prompt="Generate content about AI",
        model="gpt-3.5-turbo",
        content_type="article",
        cache_key="ai-article"
    )
"""

import os
import json
import hashlib
import logging
import datetime
import functools
try:
    import tiktoken
except ImportError:
    # If tiktoken is not available, we'll use fallback token counting
    tiktoken = None
from typing import Dict, Any, Optional, List, Tuple, Union

# In-memory cache and statistics - defined as module-level variables
_response_cache = {}
_token_usage = {}
_cache_info = {
    "hits": 0,
    "misses": 0,
    "size": 0,
    "max_size": 1000,  # Maximum entries to store
    "created_at": datetime.datetime.utcnow()
}

class AIOptimizationService:
    """
    Service for optimizing AI API usage to reduce costs and improve response times.
    Provides caching, token counting, and prompt optimization features.
    """
    
    def __init__(self, cache_ttl_seconds=3600, enable_caching=True):
        """
        Initialize the optimization service.
        
        Args:
            cache_ttl_seconds (int): How long to keep cached responses (in seconds)
            enable_caching (bool): Whether to enable response caching
        """
        self.logger = logging.getLogger('ai_optimization')
        self.enable_caching = enable_caching
        self.cache_ttl_seconds = cache_ttl_seconds
        self.tiktoken_encoders = {}
        
        self.logger.info(f"AI Optimization service initialized. Caching: {enable_caching}")
    
    def _get_tiktoken_encoder(self, model: str):
        """Get the appropriate tokenizer for a model."""
        if model not in self.tiktoken_encoders:
            try:
                if "gpt-4" in model:
                    encoding_name = "cl100k_base"
                elif "gpt-3.5" in model:
                    encoding_name = "cl100k_base"
                else:
                    encoding_name = "p50k_base"  # Fallback tokenizer
                
                self.tiktoken_encoders[model] = tiktoken.get_encoding(encoding_name)
                self.logger.debug(f"Created tokenizer for model: {model}")
            except Exception as e:
                self.logger.error(f"Error creating tokenizer for {model}: {str(e)}")
                # Return None and handle the error at usage site
                return None
                
        return self.tiktoken_encoders.get(model)
    
    def _compute_cache_key(self, prompt: str, model: str, params: Dict[str, Any]) -> str:
        """
        Compute a cache key for the given prompt and parameters.
        
        Args:
            prompt (str): The prompt text
            model (str): The model identifier
            params (dict): Additional parameters that affect the response
            
        Returns:
            str: A hash string to use as cache key
        """
        # Convert parameters to a sorted, stable representation
        param_str = json.dumps(params, sort_keys=True)
        
        # Create a hash that combines prompt, model, and parameters
        key_material = f"{prompt}|{model}|{param_str}"
        return hashlib.md5(key_material.encode('utf-8')).hexdigest()
    
    def _is_cached_response_valid(self, cache_entry):
        """Check if a cached response is still valid based on TTL."""
        if not cache_entry or "timestamp" not in cache_entry:
            return False
            
        age = (datetime.datetime.utcnow() - cache_entry["timestamp"]).total_seconds()
        return age < self.cache_ttl_seconds
    
    def _update_cache_metrics(self, hit: bool):
        """Update cache hit/miss metrics."""
        # We're modifying _cache_info but not reassigning it, so global not needed
        if hit:
            _cache_info["hits"] += 1
        else:
            _cache_info["misses"] += 1
    
    def _clean_cache_if_needed(self):
        """Remove old entries if cache is too large."""
        global _response_cache  # Only needed for the reassignment on line 151
        
        if len(_response_cache) > _cache_info["max_size"]:
            self.logger.info(f"Cache cleanup triggered. Size: {len(_response_cache)}")
            
            # Find and remove expired entries
            now = datetime.datetime.utcnow()
            expired_keys = [
                k for k, v in _response_cache.items() 
                if (now - v["timestamp"]).total_seconds() > self.cache_ttl_seconds
            ]
            
            for k in expired_keys:
                del _response_cache[k]
                
            # If still too many entries, remove oldest ones
            if len(_response_cache) > _cache_info["max_size"]:
                # Sort by timestamp and keep only the newest entries
                sorted_entries = sorted(
                    _response_cache.items(),
                    key=lambda x: x[1]["timestamp"],
                    reverse=True
                )
                
                # Keep only the newest entries
                _response_cache = dict(sorted_entries[:_cache_info["max_size"]])  # Reassignment
                
            _cache_info["size"] = len(_response_cache)
            self.logger.info(f"Cache cleanup completed. New size: {len(_response_cache)}")
    
    def count_tokens(self, text: str, model: str = "gpt-4") -> int:
        """
        Count the number of tokens in a text string.
        
        Args:
            text (str): The text to count tokens for
            model (str): The model to count tokens for
            
        Returns:
            int: Number of tokens
        """
        encoder = self._get_tiktoken_encoder(model)
        if not encoder:
            # Fallback estimation if tokenizer fails
            return len(text) // 4
            
        try:
            tokens = encoder.encode(text)
            return len(tokens)
        except Exception as e:
            self.logger.error(f"Error counting tokens: {str(e)}")
            # Fallback estimation
            return len(text) // 4
    
    def get_cached_response(self, cache_key: str):
        """
        Retrieve a cached response if available and valid.
        
        Args:
            cache_key (str): The cache key to look up
            
        Returns:
            dict or None: The cached response or None if not found/invalid
        """
        # No assignment to _response_cache, so no global needed
        
        if not self.enable_caching:
            self._update_cache_metrics(False)
            return None
            
        if cache_key not in _response_cache:
            self._update_cache_metrics(False)
            return None
            
        cache_entry = _response_cache[cache_key]
        
        if not self._is_cached_response_valid(cache_entry):
            # Entry expired
            self._update_cache_metrics(False)
            return None
            
        # Valid cache hit
        self._update_cache_metrics(True)
        return cache_entry["response"]
    
    def cache_response(self, cache_key: str, response: Any, tokens_used: int = 0):
        """
        Store a response in the cache.
        
        Args:
            cache_key (str): The cache key to store under
            response (any): The response object to cache
            tokens_used (int): Number of tokens used for this response
        """
        global _token_usage  # Only needed for assignment on line 234
        
        if not self.enable_caching:
            return
            
        _response_cache[cache_key] = {
            "response": response,
            "timestamp": datetime.datetime.utcnow(),
            "tokens": tokens_used
        }
        
        # Track token usage by day
        today = datetime.datetime.utcnow().strftime("%Y-%m-%d")
        if today not in _token_usage:
            _token_usage[today] = {}  # Assignment to _token_usage
            
        # Aggregate by model
        model = "unknown"  # Default
        if hasattr(response, "model"):
            model = response.model
            
        if model not in _token_usage[today]:
            _token_usage[today][model] = 0
            
        _token_usage[today][model] += tokens_used
        
        # Update cache info
        _cache_info["size"] = len(_response_cache)
        
        # Clean up cache if needed
        self._clean_cache_if_needed()
    
    def get_optimized_completion(self, prompt: str, model: str, 
                               max_tokens: int = 2000, temperature: float = 0.7,
                               content_type: str = "draft", cache_key: Optional[str] = None,
                               **kwargs):
        """
        Get completion with optimization strategies applied.
        
        Args:
            prompt (str): The prompt text
            model (str): The model to use
            max_tokens (int): Maximum tokens to generate
            temperature (float): Temperature for generation
            content_type (str): Type of content (draft, article, polish)
            cache_key (str, optional): Custom cache key, will be auto-generated if not provided
            **kwargs: Additional arguments to pass to the model
            
        Returns:
            str: The generated content
        """
        # Automatically downgrade model for draft content to save costs
        if content_type == "draft" and model.startswith("gpt-4"):
            original_model = model
            model = "gpt-3.5-turbo"
            self.logger.info(f"Downgraded model from {original_model} to {model} for draft content")
        
        # Generate cache key if not provided
        if cache_key is None:
            params = {
                "max_tokens": max_tokens,
                "temperature": temperature,
                "content_type": content_type,
                **kwargs
            }
            cache_key = self._compute_cache_key(prompt, model, params)
        
        # Check cache first
        cached_result = self.get_cached_response(cache_key)
        if cached_result:
            self.logger.info(f"Cache hit for key: {cache_key[:8]}...")
            return cached_result
        
        # If we reach here, we need to make an API call
        # This would integrate with your existing OpenAI service
        self.logger.info(f"Cache miss for key: {cache_key[:8]}... Making API call")
        
        # In this integration, the function would return a placeholder value
        # In actual implementation, this would call the OpenAI API
        # For example: response = openai_service._get_completion(prompt, model, max_tokens, temperature)
        
        # Using a placeholder response for now - in real implementation, this would be the API result
        response = f"This is an optimized response for: {prompt[:30]}..."
        
        # Estimate token usage (in a real implementation, get this from the API response)
        prompt_tokens = self.count_tokens(prompt, model)
        completion_tokens = max_tokens  # Worst-case estimate
        
        # Cache the result
        self.cache_response(cache_key, response, prompt_tokens + completion_tokens)
        
        return response
    
    def optimize_prompt(self, prompt: str, max_tokens: int = 4000, model: str = "gpt-4") -> str:
        """
        Optimize a prompt to reduce token usage.
        
        Args:
            prompt (str): The original prompt
            max_tokens (int): Target maximum tokens
            model (str): Model to optimize for
            
        Returns:
            str: The optimized prompt
        """
        current_tokens = self.count_tokens(prompt, model)
        
        if current_tokens <= max_tokens:
            # No optimization needed
            return prompt
            
        # Simple truncation for now - more sophisticated methods could be added
        excess_ratio = current_tokens / max_tokens
        
        # If only slightly over, use simple truncation
        if excess_ratio < 1.2:
            # Estimate characters to keep (approximate)
            chars_to_keep = int(len(prompt) / excess_ratio)
            return prompt[:chars_to_keep]
        
        # For more significant reduction, use structured reduction
        # This is a simplified implementation - could be enhanced with NLP
        lines = prompt.split('\n')
        shortened_lines = []
        
        # Keep the first 20% and last 20% of lines, remove middle content
        first_chunk = int(len(lines) * 0.2)
        last_chunk = int(len(lines) * 0.2)
        
        shortened_lines.extend(lines[:first_chunk])
        shortened_lines.append("\n[... Additional context summarized for brevity ...]\n")
        shortened_lines.extend(lines[-last_chunk:])
        
        result = '\n'.join(shortened_lines)
        
        # Check if we achieved target reduction
        if self.count_tokens(result, model) <= max_tokens:
            return result
            
        # If still too long, fall back to simple truncation
        chars_to_keep = int(len(prompt) / excess_ratio)
        return prompt[:chars_to_keep]
    
    def get_cache_stats(self):
        """
        Get statistics about the cache usage.
        
        Returns:
            dict: Cache statistics
        """
        # No assignments to global variables in this method, just reading
        
        # Update the size in case it's stale
        _cache_info["size"] = len(_response_cache)
        
        result = {
            "hits": _cache_info["hits"],
            "misses": _cache_info["misses"],
            "size": _cache_info["size"],
            "max_size": _cache_info["max_size"],
            "age_seconds": (datetime.datetime.utcnow() - _cache_info["created_at"]).total_seconds(),
            "hit_ratio": _cache_info["hits"] / (_cache_info["hits"] + _cache_info["misses"]) if (_cache_info["hits"] + _cache_info["misses"]) > 0 else 0,
            "token_usage": _token_usage
        }
        
        return result
    
    def clear_cache(self):
        """Clear the response cache."""
        # We're just calling clear() and updating an attribute, not reassigning
        # So no globals are needed here
        
        _response_cache.clear()
        _cache_info["size"] = 0
        
        self.logger.info("Response cache cleared")
        
        return {"status": "Cache cleared", "size": 0}
    
    def select_appropriate_model(self, content_type: str, complexity: int = 1):
        """
        Select the most cost-effective model based on content needs.
        
        Args:
            content_type (str): Type of content (draft, article, polish, etc)
            complexity (int): Complexity level (1-5, higher is more complex)
            
        Returns:
            str: The recommended model name
        """
        # Define content type to model mapping
        model_map = {
            # Basic content types
            "draft": "gpt-3.5-turbo",
            "research": "gpt-3.5-turbo",
            "outline": "gpt-3.5-turbo",
            
            # Advanced content types
            "article": "gpt-3.5-turbo",  # Default to 3.5
            "polish": "gpt-4o",          # Always use 4.0 for polish
            "expert": "gpt-4o",
            
            # Other types
            "summary": "gpt-3.5-turbo",
            "metadata": "gpt-3.5-turbo"
        }
        
        # For high complexity content, upgrade models
        if complexity >= 4 and content_type in ["article", "research"]:
            return "gpt-4o"
            
        # Get the recommended model, fallback to gpt-3.5-turbo
        return model_map.get(content_type, "gpt-3.5-turbo")