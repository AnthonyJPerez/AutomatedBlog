import json
import datetime
from typing import List, Dict, Any, Optional, Union

class BaseModel:
    """Base class for all models with common serialization methods."""
    
    def to_dict(self):
        """Convert model to dictionary."""
        result = {}
        for key, value in self.__dict__.items():
            # Skip keys that start with underscore
            if key.startswith('_'):
                continue
            
            # Convert any nested models to dictionaries
            if isinstance(value, BaseModel):
                result[key] = value.to_dict()
            # Convert lists of models to lists of dictionaries
            elif isinstance(value, list) and value and isinstance(value[0], BaseModel):
                result[key] = [item.to_dict() for item in value]
            # Regular value
            else:
                result[key] = value
        
        return result
    
    @classmethod
    def from_dict(cls, data):
        """Create a model instance from a dictionary."""
        instance = cls()
        
        for key, value in data.items():
            if hasattr(instance, key):
                setattr(instance, key, value)
        
        return instance
    
    def to_json(self):
        """Convert model to JSON string."""
        return json.dumps(self.to_dict(), indent=2)
    
    @classmethod
    def from_json(cls, json_str):
        """Create a model instance from a JSON string."""
        data = json.loads(json_str)
        return cls.from_dict(data)

class BlogConfig(BaseModel):
    """Configuration for a blog in the automation system."""
    
    def __init__(
        self,
        blog_id: str = "",
        blog_name: str = "",
        theme: str = "",
        tone: str = "professional",
        target_audience: str = "general",
        content_types: List[str] = None,
        publishing_frequency: str = "weekly",
        wordpress_url: str = "",
        wordpress_username: str = "",
        wordpress_app_password: str = "",
        adsense_publisher_id: str = "",
        adsense_ad_slots: List[str] = None,
        region: str = "US",
        previous_topics: List[str] = None,
        needs_domain: bool = False,
        created_at: str = None,
        last_published_date: str = None
    ):
        self.blog_id = blog_id
        self.blog_name = blog_name
        self.theme = theme
        self.tone = tone
        self.target_audience = target_audience
        self.content_types = content_types or ["article"]
        self.publishing_frequency = publishing_frequency
        self.wordpress_url = wordpress_url
        self.wordpress_username = wordpress_username
        self.wordpress_app_password = wordpress_app_password
        self.adsense_publisher_id = adsense_publisher_id
        self.adsense_ad_slots = adsense_ad_slots or []
        self.region = region
        self.previous_topics = previous_topics or []
        self.needs_domain = needs_domain
        self.created_at = created_at or datetime.datetime.utcnow().isoformat()
        self.last_published_date = last_published_date

class BlogTask(BaseModel):
    """A task for generating content for a blog."""
    
    def __init__(
        self,
        id: str = "",
        blog_id: str = "",
        blog_name: str = "",
        status: str = "pending",
        created_at: str = None,
        updated_at: str = None,
        theme: str = "",
        tone: str = "professional",
        target_audience: str = "general",
        content_types: List[str] = None,
        wordpress_url: str = "",
        wordpress_username: str = "",
        adsense_ad_slots: List[str] = None,
        error_message: str = None
    ):
        self.id = id
        self.blog_id = blog_id
        self.blog_name = blog_name
        self.status = status
        self.created_at = created_at or datetime.datetime.utcnow().isoformat()
        self.updated_at = updated_at or datetime.datetime.utcnow().isoformat()
        self.theme = theme
        self.tone = tone
        self.target_audience = target_audience
        self.content_types = content_types or ["article"]
        self.wordpress_url = wordpress_url
        self.wordpress_username = wordpress_username
        self.adsense_ad_slots = adsense_ad_slots or []
        self.error_message = error_message

class BlogContent(BaseModel):
    """Generated content for a blog post."""
    
    def __init__(
        self,
        id: str = "",
        task_id: str = "",
        blog_id: str = "",
        blog_name: str = "",
        title: str = "",
        content: str = "",
        outline: Dict[str, Any] = None,
        seo_metadata: Dict[str, Any] = None,
        research_data: List[Dict[str, Any]] = None,
        domain_suggestions: List[Dict[str, Any]] = None,
        created_at: str = None,
        status: str = "draft"
    ):
        self.id = id
        self.task_id = task_id
        self.blog_id = blog_id
        self.blog_name = blog_name
        self.title = title
        self.content = content
        self.outline = outline or {}
        self.seo_metadata = seo_metadata or {}
        self.research_data = research_data or []
        self.domain_suggestions = domain_suggestions or []
        self.created_at = created_at or datetime.datetime.utcnow().isoformat()
        self.status = status

class PublishResult(BaseModel):
    """Result of publishing a blog post."""
    
    def __init__(
        self,
        id: str = "",
        content_id: str = "",
        task_id: str = "",
        blog_id: str = "",
        blog_name: str = "",
        title: str = "",
        post_id: str = None,
        post_url: str = None,
        status: str = "pending",
        error_message: str = None,
        published_at: str = None
    ):
        self.id = id
        self.content_id = content_id
        self.task_id = task_id
        self.blog_id = blog_id
        self.blog_name = blog_name
        self.title = title
        self.post_id = post_id
        self.post_url = post_url
        self.status = status
        self.error_message = error_message
        self.published_at = published_at or datetime.datetime.utcnow().isoformat()
