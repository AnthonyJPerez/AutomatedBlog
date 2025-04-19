"""
Translation Service for Multi-Blog Content Pipeline

This service handles language detection and translation for blog content across
the content generation pipeline.
"""

import logging
import os
import json
import hashlib
import datetime
from langdetect import detect, LangDetectException
from typing import Dict, List, Optional, Tuple, Union

# Initialize logging
logger = logging.getLogger(__name__)

# Dictionary of supported languages with their ISO 639-1 codes
SUPPORTED_LANGUAGES = {
    'en': 'English',
    'es': 'Spanish',
    'fr': 'French',
    'de': 'German',
    'it': 'Italian',
    'pt': 'Portuguese',
    'nl': 'Dutch',
    'ru': 'Russian',
    'ja': 'Japanese',
    'zh': 'Chinese',
    'ko': 'Korean',
    'ar': 'Arabic',
    'hi': 'Hindi',
}

class TranslationService:
    """
    Service for language detection and content translation.
    """
    
    def __init__(self, openai_service=None):
        """
        Initialize the translation service.
        
        Args:
            openai_service: An instance of OpenAIService for translations
        """
        from src.shared.openai_service import OpenAIService
        
        self.openai_service = openai_service or OpenAIService()
        
        # Set up cache directory
        self.cache_dir = "data/translation_cache"
        os.makedirs(self.cache_dir, exist_ok=True)
        
        # Check if cache is enabled
        self.cache_enabled = os.environ.get("TRANSLATION_CACHE_ENABLED", "True").lower() == "true"
        
        # Initialize cache stats
        self.cache_hits = 0
        self.cache_misses = 0
        
        logger.info(f"Translation service initialized with cache {'enabled' if self.cache_enabled else 'disabled'}")
    
    def detect_language(self, text: str) -> Tuple[str, float]:
        """
        Detect the language of the provided text.
        
        Args:
            text: The text to detect language for
            
        Returns:
            Tuple containing language code and confidence score
        """
        try:
            # Use langdetect to identify the language
            language_code = detect(text)
            
            # We'll use high confidence when using langdetect
            confidence = 0.95
            
            return language_code, confidence
        except LangDetectException as e:
            logger.warning(f"Language detection failed: {str(e)}")
            return 'en', 0.0  # Default to English with zero confidence
    
    def _get_cache_key(self, text: str, source_language: str, target_language: str) -> str:
        """
        Generate a unique cache key for a translation request.
        
        Args:
            text: The text to translate
            source_language: Source language code
            target_language: Target language code
            
        Returns:
            A hash string to use as cache key
        """
        # Create a unique identifier for this translation request
        content_hash = hashlib.md5(text.encode('utf-8')).hexdigest()
        return f"{source_language}_{target_language}_{content_hash}"
    
    def _get_from_cache(self, text: str, source_language: str, target_language: str) -> Optional[str]:
        """
        Try to retrieve a translation from the cache.
        
        Args:
            text: The text to translate
            source_language: Source language code
            target_language: Target language code
            
        Returns:
            The cached translation if available, None otherwise
        """
        if not self.cache_enabled:
            return None
            
        try:
            cache_key = self._get_cache_key(text, source_language, target_language)
            cache_file = os.path.join(self.cache_dir, f"{cache_key}.json")
            
            if os.path.exists(cache_file):
                with open(cache_file, 'r', encoding='utf-8') as f:
                    cached_data = json.load(f)
                    self.cache_hits += 1
                    logger.debug(f"Translation cache hit: {cache_key[:10]}...")
                    return cached_data.get('translation')
            
            self.cache_misses += 1
            logger.debug(f"Translation cache miss: {cache_key[:10]}...")
            return None
        except Exception as e:
            logger.warning(f"Error accessing translation cache: {str(e)}")
            return None
    
    def _save_to_cache(self, text: str, source_language: str, target_language: str, translation: str) -> bool:
        """
        Save a translation to the cache.
        
        Args:
            text: The original text
            source_language: Source language code
            target_language: Target language code
            translation: The translated text
            
        Returns:
            True if successfully cached, False otherwise
        """
        if not self.cache_enabled:
            return False
        
        try:
            cache_key = self._get_cache_key(text, source_language, target_language)
            cache_file = os.path.join(self.cache_dir, f"{cache_key}.json")
            
            cached_data = {
                'source_language': source_language,
                'target_language': target_language,
                'original_text': text,
                'translation': translation,
                'timestamp': datetime.datetime.now().isoformat()
            }
            
            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump(cached_data, f, ensure_ascii=False, indent=2)
                
            logger.debug(f"Saved translation to cache: {cache_key[:10]}...")
            return True
        except Exception as e:
            logger.warning(f"Error saving to translation cache: {str(e)}")
            return False
            
    def translate_text(self, text: str, target_language: str = 'en', source_language: Optional[str] = None) -> str:
        """
        Translate text to the target language.
        
        Args:
            text: The text to translate
            target_language: ISO 639-1 language code for the target language
            source_language: Optional source language code. If None, will be auto-detected.
            
        Returns:
            Translated text
        """
        if not text.strip():
            return text
            
        # Detect language if source not specified
        if not source_language:
            source_language, _ = self.detect_language(text)
        
        # If source and target are the same, return original text
        if source_language == target_language:
            return text
        
        # Try to get from cache first
        cached_translation = self._get_from_cache(text, source_language, target_language)
        if cached_translation:
            return cached_translation
            
        # If not in cache, perform translation
        try:
            source_language_name = SUPPORTED_LANGUAGES.get(source_language, source_language)
            target_language_name = SUPPORTED_LANGUAGES.get(target_language, target_language)
            
            system_message = (
                f"You are a professional translator specializing in translating from "
                f"{source_language_name} to {target_language_name}. "
                f"Translate the text while maintaining the original meaning, tone, and style. "
                f"Preserve formatting, line breaks, and special characters."
            )
            
            response = self.openai_service.chat_completion(
                system_message=system_message,
                user_message=text,
                temperature=0.1,
                max_tokens=None  # Allow the model to determine appropriate response length
            )
            
            # Save successful translation to cache
            self._save_to_cache(text, source_language, target_language, response)
            
            return response
        except Exception as e:
            logger.error(f"Translation error: {str(e)}")
            return text  # Return original text if translation fails
    
    def translate_markdown_content(self, markdown: str, target_language: str = 'en') -> str:
        """
        Translate markdown content while preserving formatting.
        
        Args:
            markdown: Markdown content to translate
            target_language: Target language code
            
        Returns:
            Translated markdown
        """
        if not markdown.strip():
            return markdown
        
        # Detect source language
        source_language, _ = self.detect_language(markdown)
        
        # Skip translation if source and target match
        if source_language == target_language:
            return markdown
            
        # Try to get from cache first
        cached_translation = self._get_from_cache(markdown, source_language, target_language)
        if cached_translation:
            return cached_translation
        
        # Use specialized prompt for markdown translation
        system_message = (
            f"You are a professional translator specializing in markdown content. "
            f"Translate the following markdown from {SUPPORTED_LANGUAGES.get(source_language, source_language)} "
            f"to {SUPPORTED_LANGUAGES.get(target_language, target_language)}. "
            f"Preserve all markdown formatting, links, code blocks, and special characters. "
            f"Do not translate code inside code blocks or text between backticks."
        )
        
        try:
            translated_content = self.openai_service.chat_completion(
                system_message=system_message,
                user_message=markdown,
                temperature=0.1
            )
            
            # Save successful translation to cache
            self._save_to_cache(markdown, source_language, target_language, translated_content)
            
            return translated_content
        except Exception as e:
            logger.error(f"Markdown translation error: {str(e)}")
            return markdown
    
    def translate_blog_content(self, blog_content: Dict, target_language: str) -> Dict:
        """
        Translate an entire blog content object.
        
        Args:
            blog_content: Dictionary containing blog content
            target_language: Target language code
            
        Returns:
            Translated blog content dictionary
        """
        translated_content = blog_content.copy()
        
        # Translate title
        if 'title' in translated_content:
            translated_content['title'] = self.translate_text(
                translated_content['title'], 
                target_language
            )
        
        # Translate main content
        if 'content' in translated_content:
            translated_content['content'] = self.translate_markdown_content(
                translated_content['content'],
                target_language
            )
        
        # Translate meta description
        if 'meta_description' in translated_content:
            translated_content['meta_description'] = self.translate_text(
                translated_content['meta_description'],
                target_language
            )
        
        # Translate excerpt
        if 'excerpt' in translated_content:
            translated_content['excerpt'] = self.translate_text(
                translated_content['excerpt'],
                target_language
            )
        
        # Add language metadata
        translated_content['language'] = target_language
        
        return translated_content
    
    def get_supported_languages(self) -> Dict[str, str]:
        """
        Get a dictionary of supported languages.
        
        Returns:
            Dictionary of language codes and names
        """
        return SUPPORTED_LANGUAGES
        
    def get_cache_stats(self) -> Dict[str, Union[int, float, bool]]:
        """
        Get cache performance statistics.
        
        Returns:
            Dictionary with cache statistics
        """
        total_requests = self.cache_hits + self.cache_misses
        hit_rate = 0.0
        if total_requests > 0:
            hit_rate = float(self.cache_hits) / total_requests * 100.0
            
        stats = {
            'enabled': self.cache_enabled,
            'hits': self.cache_hits,
            'misses': self.cache_misses,
            'total_requests': total_requests,
            'hit_rate_percent': hit_rate
        }
        
        # Count cache files
        try:
            cache_files = [f for f in os.listdir(self.cache_dir) if f.endswith('.json')]
            stats['cache_entries'] = len(cache_files)
        except Exception:
            stats['cache_entries'] = 0
            
        return stats
        
    def clear_cache(self) -> Dict[str, Union[int, bool]]:
        """
        Clear the translation cache.
        
        Returns:
            Dictionary with clear operation results
        """
        result = {
            'success': False,
            'deleted_entries': 0
        }
        
        if not self.cache_enabled:
            return result
            
        try:
            deleted_count = 0
            for f in os.listdir(self.cache_dir):
                if f.endswith('.json'):
                    os.remove(os.path.join(self.cache_dir, f))
                    deleted_count += 1
                    
            # Reset stats
            self.cache_hits = 0
            self.cache_misses = 0
            
            result['success'] = True
            result['deleted_entries'] = deleted_count
            
            logger.info(f"Translation cache cleared. Deleted {deleted_count} entries.")
            
            return result
        except Exception as e:
            logger.error(f"Error clearing translation cache: {str(e)}")
            return result