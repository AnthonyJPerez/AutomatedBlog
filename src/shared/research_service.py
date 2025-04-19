import os
import json
import logging
import random
import time
from datetime import datetime, timedelta
from pytrends.request import TrendReq
import requests
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry

# Import web scraper service if available
try:
    from .web_scraper_service import web_scraper_service
    web_scraper_available = True
except ImportError:
    web_scraper_available = False

class ResearchService:
    """
    Service for researching trending topics using Google Trends and web scraping.
    Provides methods to identify popular and trending topics related to a blog theme,
    and enhances the research with additional content from web sources.
    """
    
    def __init__(self):
        """Initialize the research service with API configuration."""
        # Configure logger
        self.logger = logging.getLogger('ResearchService')
        
        # Set up retry strategy for HTTP requests
        retry_strategy = Retry(
            total=3,
            backoff_factor=0.2,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["HEAD", "GET", "OPTIONS"]
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session = requests.Session()
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)
        
        # Initialize PyTrends with session and HL (language) parameter
        try:
            self.pytrends = TrendReq(hl='en-US', tz=0, timeout=(10, 25), retries=3, backoff_factor=0.2, requests_args={'verify': True})
            self.pytrends_available = True
        except Exception as e:
            self.logger.error(f"Error initializing PyTrends: {str(e)}")
            self.pytrends_available = False
        
        # Track web scraper availability
        self.web_scraper_available = web_scraper_available
        if self.web_scraper_available:
            self.logger.info("Web scraper service is available for enhanced research")
        else:
            self.logger.warning("Web scraper service is not available, using basic research only")
        
        # Initialize cache for trend data (to avoid duplicate API calls)
        self.trend_cache = {}
        self.cache_expiry = 3600  # Cache data for 1 hour
    
    def research_topics(self, theme, target_audience="general", region="US", max_results=10):
        """
        Research trending topics related to a given theme.
        
        Args:
            theme (str): The blog theme to research
            target_audience (str): Target audience for the content
            region (str): Region code for trend data (default: US)
            max_results (int): Maximum number of results to return
            
        Returns:
            list: List of trending topics with scores and metadata
        """
        # Check if results are in cache and not expired
        cache_key = f"{theme}:{target_audience}:{region}"
        if cache_key in self.trend_cache:
            cache_time, cache_data = self.trend_cache[cache_key]
            if time.time() - cache_time < self.cache_expiry:
                self.logger.info(f"Returning cached trend data for {theme}")
                return cache_data
        
        results = []
        
        # Use PyTrends if available
        if self.pytrends_available:
            try:
                # Get related queries for the theme
                self.pytrends.build_payload([theme], cat=0, timeframe='now 7-d', geo=region)
                related_queries = self.pytrends.related_queries()
                
                if related_queries and theme in related_queries and related_queries[theme]['top'] is not None:
                    # Add top related queries
                    for query in related_queries[theme]['top'].head(max_results).itertuples():
                        results.append({
                            'keyword': query.query,
                            'title': self._generate_title(query.query, theme),
                            'trend_score': int(query.value),
                            'trend_type': 'top',
                            'source': 'google_trends'
                        })
                
                if related_queries and theme in related_queries and related_queries[theme]['rising'] is not None:
                    # Add rising related queries
                    for query in related_queries[theme]['rising'].head(max_results).itertuples():
                        results.append({
                            'keyword': query.query,
                            'title': self._generate_title(query.query, theme),
                            'trend_score': int(min(query.value, 100)),  # Cap at 100
                            'trend_type': 'rising',
                            'source': 'google_trends'
                        })
                
                # Get related topics
                related_topics = self.pytrends.related_topics()
                
                if related_topics and theme in related_topics and related_topics[theme]['top'] is not None:
                    # Add top related topics
                    for topic in related_topics[theme]['top'].head(max_results).itertuples():
                        results.append({
                            'keyword': topic.topic_title,
                            'title': self._generate_title(topic.topic_title, theme),
                            'trend_score': int(topic.value),
                            'trend_type': 'top',
                            'source': 'google_trends'
                        })
            
            except Exception as e:
                self.logger.error(f"Error getting trend data from PyTrends: {str(e)}")
                self.pytrends_available = False
        
        # If PyTrends is not available or didn't return enough results, use fallback
        if not self.pytrends_available or len(results) < 5:
            self.logger.warning(f"Using fallback trend generation for {theme}")
            
            fallback_results = self._generate_fallback_topics(theme, target_audience, max(5, max_results - len(results)))
            results.extend(fallback_results)
        
        # Deduplicate results by keyword
        seen_keywords = set()
        unique_results = []
        
        for result in results:
            keyword = result['keyword'].lower()
            if keyword not in seen_keywords:
                seen_keywords.add(keyword)
                unique_results.append(result)
        
        # Sort by trend score (descending)
        sorted_results = sorted(unique_results, key=lambda x: x.get('trend_score', 0), reverse=True)
        
        # Limit to max_results
        final_results = sorted_results[:max_results]
        
        # Enhance results with web scraper if available
        if self.web_scraper_available and web_scraper_service:
            try:
                self.logger.info(f"Enhancing research results with web scraper data for {theme}")
                enriched_results = self.enrich_topics_with_web_data(final_results, theme)
                final_results = enriched_results
            except Exception as e:
                self.logger.error(f"Error enhancing research results with web scraper: {str(e)}")
        
        # Add to cache
        self.trend_cache[cache_key] = (time.time(), final_results)
        
        return final_results
        
    def enrich_topics_with_web_data(self, topics, theme):
        """
        Enhance topic research results with additional data from web sources.
        
        Args:
            topics (list): List of topic results from research_topics
            theme (str): The blog theme
            
        Returns:
            list: Enhanced list of topics with additional web data
        """
        if not self.web_scraper_available or not web_scraper_service:
            return topics
        
        enriched_topics = []
        
        for topic in topics:
            try:
                # Create keyword for searching
                keyword = topic['keyword']
                search_term = f"{keyword} {theme}".strip()
                
                # Get trending topics for related content
                trending_topics = web_scraper_service.get_trending_topics(
                    category=theme.lower() if theme else None, 
                    limit=5
                )
                
                # Get additional context for the topic
                self.logger.info(f"Researching web content for: {search_term}")
                research_data = web_scraper_service.research_topic(search_term, num_sources=2)
                
                # Extract relevant information
                web_keywords = []
                sentiment_info = None
                summary = None
                sources = []
                
                if research_data:
                    # Get keywords from web research
                    if 'keywords' in research_data and research_data['keywords']:
                        web_keywords = [item['keyword'] for item in research_data['keywords'][:10] if 'keyword' in item]
                    
                    # Get sources for context
                    if 'articles' in research_data and research_data['articles']:
                        for article in research_data['articles']:
                            if article and 'url' in article:
                                source = {
                                    'url': article.get('url', ''),
                                    'title': article.get('title', 'Untitled Article'),
                                }
                                
                                # Get text summary if available
                                if 'analysis' in article and 'summary' in article['analysis']:
                                    source['summary'] = article['analysis']['summary']
                                    
                                # Get sentiment if available
                                if 'analysis' in article and 'sentiment' in article['analysis']:
                                    if not sentiment_info:  # Save first sentiment info found
                                        sentiment_info = article['analysis']['sentiment']
                                
                                sources.append(source)
                                
                                # Use first article summary if we don't have one yet
                                if not summary and source.get('summary'):
                                    summary = source.get('summary')
                
                # Enhance the original topic with additional context
                enriched_topic = topic.copy()  # Don't modify the original
                
                # Add web research data
                enriched_topic['web_research'] = {
                    'related_keywords': web_keywords,
                    'summary': summary,
                    'sources': sources[:3],  # Limit to top 3 sources
                    'sentiment': sentiment_info,
                    'related_trends': trending_topics[:5] if trending_topics else []
                }
                
                enriched_topics.append(enriched_topic)
                
            except Exception as e:
                self.logger.error(f"Error enriching topic {topic['keyword']}: {str(e)}")
                enriched_topics.append(topic)  # Use original if enrichment fails
        
        return enriched_topics
    
    def _generate_title(self, keyword, theme):
        """
        Generate a blog post title from a keyword and theme.
        
        Args:
            keyword (str): The main keyword
            theme (str): The blog theme
            
        Returns:
            str: A generated blog post title
        """
        # Title templates
        templates = [
            f"The Ultimate Guide to {keyword}",
            f"{keyword}: What You Need to Know in {datetime.now().year}",
            f"How {keyword} is Transforming {theme}",
            f"Top 10 {keyword} Strategies for {theme} Enthusiasts",
            f"Why {keyword} Matters for Your {theme} Success",
            f"Exploring the Connection Between {keyword} and {theme}",
            f"The Future of {keyword} in {theme}",
            f"{keyword} 101: A Beginner's Guide",
            f"Expert Tips for Mastering {keyword} in Your {theme} Journey",
            f"Understanding {keyword}: A Deep Dive"
        ]
        
        return random.choice(templates)
    
    def _generate_fallback_topics(self, theme, target_audience, count=5):
        """
        Generate fallback topic suggestions when API is unavailable.
        
        Args:
            theme (str): The blog theme
            target_audience (str): Target audience for the content
            count (int): Number of fallback topics to generate
            
        Returns:
            list: List of generated topic suggestions
        """
        # Common topics by theme category
        common_topics = {
            "technology": [
                "artificial intelligence", "machine learning", "blockchain", 
                "cybersecurity", "cloud computing", "data science", 
                "internet of things", "virtual reality", "augmented reality",
                "digital transformation", "edge computing", "5g technology"
            ],
            "health": [
                "wellness", "nutrition", "fitness", "mental health", 
                "meditation", "yoga", "healthy eating", "weight loss",
                "stress management", "sleep hygiene", "immune system",
                "holistic health", "preventative care"
            ],
            "finance": [
                "investing", "personal finance", "retirement planning", 
                "cryptocurrency", "stock market", "budgeting", 
                "passive income", "financial independence", "real estate investing",
                "tax strategies", "debt management", "wealth building"
            ],
            "marketing": [
                "content marketing", "social media marketing", "seo", 
                "email marketing", "digital marketing", "influencer marketing", 
                "brand building", "marketing automation", "conversion optimization",
                "customer engagement", "marketing analytics", "growth hacking"
            ],
            "lifestyle": [
                "minimalism", "productivity", "self-improvement", 
                "work-life balance", "remote work", "travel", 
                "home decor", "sustainability", "personal development",
                "morning routines", "relationships", "career growth"
            ]
        }
        
        # Try to match theme to a category
        theme_lower = theme.lower()
        selected_category = None
        
        for category in common_topics:
            if category in theme_lower:
                selected_category = category
                break
        
        # If no category match, use general topics
        if not selected_category:
            selected_category = random.choice(list(common_topics.keys()))
        
        topics = random.sample(common_topics[selected_category], min(count, len(common_topics[selected_category])))
        
        # Generate results
        results = []
        for i, topic in enumerate(topics):
            # Random trend score between 60 and 95
            trend_score = random.randint(60, 95)
            
            results.append({
                'keyword': topic,
                'title': self._generate_title(topic, theme),
                'trend_score': trend_score,
                'trend_type': 'suggestion',
                'source': 'system_generated'
            })
        
        return results