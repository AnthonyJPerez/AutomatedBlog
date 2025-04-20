import os
import logging
from logging import StreamHandler
import datetime
import inspect
import json
import traceback
from typing import Dict, Any, Optional, Union

class LoggingService:
    """
    Service for consistent logging across the application.
    Provides structured logging with context information.
    """
    
    # Logger instances cache
    _loggers = {}
    
    # Default log level
    _default_level = logging.INFO
    
    @classmethod
    def configure(cls, level=None):
        """
        Configure the logging service.
        
        Args:
            level (int): The log level to use
        """
        # Set log level
        if level is None:
            # Get log level from environment variable, default to INFO
            level_name = os.environ.get("LOG_LEVEL", "INFO")
            level = getattr(logging, level_name, logging.INFO)
        
        cls._default_level = level
        
        # Configure root logger
        root_logger = logging.getLogger()
        root_logger.setLevel(level)
        
        # Clear existing handlers to avoid duplicate logs
        for handler in root_logger.handlers[:]:
            root_logger.removeHandler(handler)
        
        # Add console handler
        console_handler = StreamHandler()
        console_handler.setLevel(level)
        
        # Create formatter
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        console_handler.setFormatter(formatter)
        
        # Add handler to root logger
        root_logger.addHandler(console_handler)
    
    @classmethod
    def get_logger(cls, name):
        """
        Get a logger with the given name.
        
        Args:
            name (str): The name of the logger
            
        Returns:
            StructuredLogger: The logger instance
        """
        if name not in cls._loggers:
            logger = logging.getLogger(name)
            structured_logger = StructuredLogger(logger)
            cls._loggers[name] = structured_logger
        
        return cls._loggers[name]
    
    @classmethod
    def get_function_logger(cls):
        """
        Get a logger for the calling function.
        
        Returns:
            StructuredLogger: The logger instance
        """
        # Get the calling frame
        frame = inspect.currentframe().f_back
        
        # Get function name and module
        func_name = frame.f_code.co_name
        module_name = frame.f_globals.get('__name__')
        
        # Create logger name
        logger_name = f"{module_name}.{func_name}" if module_name else func_name
        
        return cls.get_logger(logger_name)

class StructuredLogger:
    """
    Wrapper around a Logger that provides structured logging capabilities.
    Adds context information to log messages.
    """
    
    def __init__(self, logger):
        """
        Initialize the structured logger.
        
        Args:
            logger (Logger): The underlying logger
        """
        self.logger = logger
        self.context = {}
    
    def add_context(self, **kwargs):
        """
        Add context information to the logger.
        
        Args:
            **kwargs: Key-value pairs to add to the context
        """
        self.context.update(kwargs)
    
    def clear_context(self):
        """Clear all context information."""
        self.context.clear()
    
    def _format_message(self, message, extra=None):
        """
        Format a log message with context information.
        
        Args:
            message (str): The log message
            extra (dict): Extra context for this message
            
        Returns:
            str: The formatted message
        """
        # Combine context and extra
        context = dict(self.context)
        if extra:
            context.update(extra)
        
        # If context is empty, return the original message
        if not context:
            return message
        
        # Format context as JSON
        try:
            context_str = json.dumps(context)
            return f"{message} - Context: {context_str}"
        except Exception:
            return f"{message} - Context: (Error formatting context)"
    
    def debug(self, message, *args, **kwargs):
        """Log a debug message."""
        extra = kwargs.pop('extra', {})
        self.logger.debug(self._format_message(message, extra), *args, **kwargs)
    
    def info(self, message, *args, **kwargs):
        """Log an info message."""
        extra = kwargs.pop('extra', {})
        self.logger.info(self._format_message(message, extra), *args, **kwargs)
    
    def warning(self, message, *args, **kwargs):
        """Log a warning message."""
        extra = kwargs.pop('extra', {})
        self.logger.warning(self._format_message(message, extra), *args, **kwargs)
    
    def error(self, message, *args, **kwargs):
        """Log an error message."""
        extra = kwargs.pop('extra', {})
        exc_info = kwargs.get('exc_info')
        
        # Add exception details to extra if exc_info is True
        if exc_info:
            try:
                extra['exception'] = traceback.format_exc()
            except Exception:
                pass
        
        self.logger.error(self._format_message(message, extra), *args, **kwargs)
    
    def critical(self, message, *args, **kwargs):
        """Log a critical message."""
        extra = kwargs.pop('extra', {})
        exc_info = kwargs.get('exc_info')
        
        # Add exception details to extra if exc_info is True
        if exc_info:
            try:
                extra['exception'] = traceback.format_exc()
            except Exception:
                pass
        
        self.logger.critical(self._format_message(message, extra), *args, **kwargs)
    
    def log(self, level, message, *args, **kwargs):
        """Log a message with the specified level."""
        extra = kwargs.pop('extra', {})
        self.logger.log(level, self._format_message(message, extra), *args, **kwargs)
    
    def exception(self, message, *args, **kwargs):
        """Log an exception message."""
        extra = kwargs.pop('extra', {})
        
        try:
            extra['exception'] = traceback.format_exc()
        except Exception:
            pass
        
        self.logger.exception(self._format_message(message, extra), *args, **kwargs)

# Configure logging service on import
LoggingService.configure()
