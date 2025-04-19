"""
Translation Service for Multi-Blog Content Pipeline

This service handles language detection and translation for blog content across
the content generation pipeline.
"""

import logging
import os
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
        logger.info("Translation service initialized")
    
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