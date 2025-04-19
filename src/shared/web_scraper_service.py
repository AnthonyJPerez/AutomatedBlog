"""
Web Scraping Service for the blog automation platform.
This service provides functionality for scraping and analyzing web content,
which is useful for research and content generation.
"""

import logging
import re
import json
import os
import random
import sqlite3
from urllib.parse import urlparse, urljoin
from datetime import datetime, timedelta

# Web scraping and content extraction
import requests
import trafilatura
from bs4 import BeautifulSoup
from newspaper import Article, Source
import feedparser

# Text analysis and processing
from textblob import TextBlob
import nltk
from nltk.tokenize import sent_tokenize, word_tokenize
from nltk.corpus import stopwords
from collections import Counter

# Import for word cloud generation
from wordcloud import WordCloud
import matplotlib.pyplot as plt
import matplotlib
matplotlib.use('Agg')  # Use non-interactive backend

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Download NLTK data if not already downloaded
try:
    nltk.data.find('tokenizers/punkt')
except LookupError:
    nltk.download('punkt', quiet=True)

try:
    nltk.data.find('corpora/stopwords')
except LookupError:
    nltk.download('stopwords', quiet=True)


class SourceTracker:
    """
    Maintains a file-based list of trusted sources for web scraping and research.
    Automatically updates as new sources are discovered during research.
    """
    
    def __init__(self, sources_file="data/sources.json", topics_file="data/topic_sources.json"):
        """Initialize the source tracker with JSON files."""
        self.sources_file = sources_file
        self.topics_file = topics_file
        self.sources = {}
        self.topic_sources = {}
        self._ensure_data_directory()
        self._load_data()
        logger.info(f"SourceTracker initialized with sources file at {sources_file}")
    
    def _ensure_data_directory(self):
        """Create directory for the data files if it doesn't exist."""
        os.makedirs(os.path.dirname(self.sources_file), exist_ok=True)
    
    def _load_data(self):
        """Load sources and topic associations from files."""
        # Load sources
        if os.path.exists(self.sources_file):
            try:
                with open(self.sources_file, 'r') as f:
                    self.sources = json.load(f)
                logger.info(f"Loaded {len(self.sources)} sources from {self.sources_file}")
            except Exception as e:
                logger.error(f"Error loading sources from {self.sources_file}: {str(e)}")
                self.sources = {}
        
        # If no sources file exists or it was empty, bootstrap with initial sources
        if not self.sources:
            logger.info("Bootstrapping source tracker with initial sources")
            self._bootstrap_initial_sources()
            self._save_sources()
        
        # Load topic-source associations
        if os.path.exists(self.topics_file):
            try:
                with open(self.topics_file, 'r') as f:
                    self.topic_sources = json.load(f)
                logger.info(f"Loaded topic-source associations from {self.topics_file}")
            except Exception as e:
                logger.error(f"Error loading topic sources from {self.topics_file}: {str(e)}")
                self.topic_sources = {}
        else:
            self.topic_sources = {}
            self._save_topic_sources()
    
    def _save_sources(self):
        """Save sources to file."""
        try:
            with open(self.sources_file, 'w') as f:
                json.dump(self.sources, f, indent=2)
            logger.debug(f"Saved {len(self.sources)} sources to {self.sources_file}")
            return True
        except Exception as e:
            logger.error(f"Error saving sources to {self.sources_file}: {str(e)}")
            return False
    
    def _save_topic_sources(self):
        """Save topic-source associations to file."""
        try:
            with open(self.topics_file, 'w') as f:
                json.dump(self.topic_sources, f, indent=2)
            logger.debug(f"Saved topic-source associations to {self.topics_file}")
            return True
        except Exception as e:
            logger.error(f"Error saving topic sources to {self.topics_file}: {str(e)}")
            return False
    
    def _bootstrap_initial_sources(self):
        """Populate the sources with initial trusted sources."""
        initial_sources = [
            {
                'domain': 'en.wikipedia.org',
                'url': 'https://en.wikipedia.org/',
                'title': 'Wikipedia',
                'quality_score': 9.0,
                'category': 'reference',
                'language': 'en',
                'has_rss': False,
                'rss_url': None,
                'times_used': 1,
                'notes': 'General encyclopedia, high factual accuracy',
                'last_scraped': datetime.now().isoformat(),
                'first_discovered': datetime.now().isoformat()
            },
            {
                'domain': 'techcrunch.com',
                'url': 'https://techcrunch.com/',
                'title': 'TechCrunch',
                'quality_score': 8.0,
                'category': 'technology',
                'language': 'en',
                'has_rss': True,
                'rss_url': 'https://techcrunch.com/feed/',
                'times_used': 1,
                'notes': 'Technology news and analysis',
                'last_scraped': datetime.now().isoformat(),
                'first_discovered': datetime.now().isoformat()
            },
            {
                'domain': 'hbr.org',
                'url': 'https://hbr.org/',
                'title': 'Harvard Business Review',
                'quality_score': 8.5,
                'category': 'business',
                'language': 'en',
                'has_rss': True,
                'rss_url': 'https://hbr.org/feed',
                'times_used': 1,
                'notes': 'Business management research and ideas',
                'last_scraped': datetime.now().isoformat(),
                'first_discovered': datetime.now().isoformat()
            },
            {
                'domain': 'nature.com',
                'url': 'https://www.nature.com/',
                'title': 'Nature',
                'quality_score': 9.5,
                'category': 'science',
                'language': 'en',
                'has_rss': True,
                'rss_url': 'https://www.nature.com/nature.rss',
                'times_used': 1,
                'notes': 'Leading international science journal',
                'last_scraped': datetime.now().isoformat(),
                'first_discovered': datetime.now().isoformat()
            },
            {
                'domain': 'blog.google',
                'url': 'https://blog.google/',
                'title': 'Google Blog',
                'quality_score': 7.5,
                'category': 'technology',
                'language': 'en',
                'has_rss': True,
                'rss_url': 'https://blog.google/rss/',
                'times_used': 1,
                'notes': 'Official Google blog with product announcements',
                'last_scraped': datetime.now().isoformat(),
                'first_discovered': datetime.now().isoformat()
            }
        ]
        
        # Add sources to our dictionary with domain as key
        for source in initial_sources:
            self.sources[source['domain']] = source
    
    def add_source(self, url, title=None, category=None, quality_score=5.0, has_rss=False, rss_url=None):
        """
        Add a new source to the sources file.
        
        Args:
            url (str): The URL of the source
            title (str): The title or name of the source
            category (str): The category of the source (e.g., technology, health)
            quality_score (float): A quality score from 0-10
            has_rss (bool): Whether the source has an RSS feed
            rss_url (str): The URL of the RSS feed if available
            
        Returns:
            bool: True if added successfully, False otherwise
        """
        try:
            parsed_url = urlparse(url)
            domain = parsed_url.netloc
            
            # Default title to domain if none provided
            if not title:
                title = domain
            
            now = datetime.now().isoformat()
            
            if domain in self.sources:
                # Update existing source
                source = self.sources[domain]
                source['url'] = url
                source['title'] = title
                source['last_scraped'] = now
                source['times_used'] = source.get('times_used', 0) + 1
                
                if category:
                    source['category'] = category
                
                if quality_score:
                    # Average with existing score if present
                    current_score = source.get('quality_score', 5.0)
                    source['quality_score'] = (current_score + quality_score) / 2
                
                if has_rss and rss_url:
                    source['has_rss'] = True
                    source['rss_url'] = rss_url
                
                logger.info(f"Updated existing source: {domain} ({title})")
            else:
                # Create new source
                self.sources[domain] = {
                    'domain': domain,
                    'url': url,
                    'title': title,
                    'quality_score': quality_score,
                    'category': category,
                    'language': 'en',
                    'last_scraped': now,
                    'times_used': 1,
                    'first_discovered': now,
                    'has_rss': has_rss,
                    'rss_url': rss_url if has_rss else None,
                    'notes': None
                }
                logger.info(f"Added new source: {domain} ({title})")
            
            # Save changes to file
            self._save_sources()
            return True
            
        except Exception as e:
            logger.error(f"Error adding source {url}: {str(e)}")
            return False
    
    def associate_topic_with_source(self, topic, url, relevance_score=5.0):
        """
        Associate a topic with a source to track which sources are relevant for which topics.
        
        Args:
            topic (str): The topic name
            url (str): The URL of the source
            relevance_score (float): How relevant the source is for the topic (0-10)
            
        Returns:
            bool: True if associated successfully, False otherwise
        """
        try:
            parsed_url = urlparse(url)
            domain = parsed_url.netloc
            
            if domain not in self.sources:
                logger.warning(f"Cannot associate topic with unknown source: {domain}")
                return False
            
            now = datetime.now().isoformat()
            
            # Initialize topic in topic_sources if not present
            if topic not in self.topic_sources:
                self.topic_sources[topic] = {}
            
            # Check if association already exists
            if domain in self.topic_sources[topic]:
                # Update existing association
                current_score = self.topic_sources[topic][domain]['relevance_score']
                # Average the new score with the existing score
                updated_score = (current_score + relevance_score) / 2
                
                self.topic_sources[topic][domain] = {
                    'relevance_score': updated_score,
                    'last_used': now
                }
                
                logger.debug(f"Updated topic-source association: {topic} - {domain}")
            else:
                # Create new association
                self.topic_sources[topic][domain] = {
                    'relevance_score': relevance_score,
                    'last_used': now
                }
                
                logger.debug(f"Created new topic-source association: {topic} - {domain}")
            
            # Save changes to file
            self._save_topic_sources()
            return True
            
        except Exception as e:
            logger.error(f"Error associating topic with source: {str(e)}")
            return False
    
    def get_sources_for_topic(self, topic, limit=5, min_quality=5.0):
        """
        Get the best sources for a given topic.
        
        Args:
            topic (str): The topic to find sources for
            limit (int): Maximum number of sources to return
            min_quality (float): Minimum quality score (0-10)
            
        Returns:
            list: List of source dictionaries with URL and metadata
        """
        try:
            results = []
            
            # If we have associations for this topic, use them
            if topic in self.topic_sources:
                topic_sources = self.topic_sources[topic]
                
                # Build a list of sources with their relevance scores
                relevant_sources = []
                for domain, data in topic_sources.items():
                    if domain in self.sources:
                        source = self.sources[domain]
                        
                        # Check if the source meets minimum quality
                        if source.get('quality_score', 0) >= min_quality:
                            # Create a copy of the source and add relevance score
                            source_copy = dict(source)
                            source_copy['relevance_score'] = data.get('relevance_score', 5.0)
                            relevant_sources.append(source_copy)
                
                # Sort by relevance score (descending)
                relevant_sources.sort(key=lambda x: x.get('relevance_score', 0), reverse=True)
                
                # Add top sources to results
                results.extend(relevant_sources[:limit])
            
            # If we don't have enough topic-specific sources, add high-quality general sources
            if len(results) < limit:
                remaining = limit - len(results)
                
                # Get domains we already have to avoid duplicates
                existing_domains = [s['domain'] for s in results]
                
                # Get additional high-quality sources
                general_sources = []
                for domain, source in self.sources.items():
                    if domain not in existing_domains and source.get('quality_score', 0) >= min_quality:
                        # Add default relevance score
                        source_copy = dict(source)
                        source_copy['relevance_score'] = 0.0
                        general_sources.append(source_copy)
                
                # Sort by quality score (descending)
                general_sources.sort(key=lambda x: x.get('quality_score', 0), reverse=True)
                
                # Add top general sources to results
                results.extend(general_sources[:remaining])
            
            return results
            
        except Exception as e:
            logger.error(f"Error getting sources for topic {topic}: {str(e)}")
            return []
    
    def update_source_quality(self, url, quality_delta):
        """
        Update the quality score of a source based on the usefulness of its content.
        
        Args:
            url (str): The URL of the source
            quality_delta (float): Change in quality score (-1.0 to +1.0)
            
        Returns:
            bool: True if updated successfully, False otherwise
        """
        try:
            parsed_url = urlparse(url)
            domain = parsed_url.netloc
            
            if domain not in self.sources:
                logger.warning(f"Cannot update quality for unknown source: {domain}")
                return False
            
            # Get current quality score
            current_score = self.sources[domain].get('quality_score', 5.0)
            
            # Update the quality score, keeping it within 0-10 range
            new_score = max(0, min(10, current_score + quality_delta))
            self.sources[domain]['quality_score'] = new_score
            
            # Save changes to file
            self._save_sources()
            
            logger.debug(f"Updated quality score for {domain}: {current_score} -> {new_score}")
            return True
            
        except Exception as e:
            logger.error(f"Error updating source quality: {str(e)}")
            return False
    
    def get_trending_sources(self, category=None, limit=10):
        """
        Get the most frequently used and high-quality sources.
        
        Args:
            category (str): Optional category to filter by
            limit (int): Maximum number of sources to return
            
        Returns:
            list: List of source dictionaries
        """
        try:
            results = []
            
            # Filter sources by category if specified
            if category:
                filtered_sources = [s for s in self.sources.values() if s.get('category') == category]
            else:
                filtered_sources = list(self.sources.values())
            
            # Sort by times_used and quality_score
            sorted_sources = sorted(
                filtered_sources, 
                key=lambda x: (x.get('times_used', 0), x.get('quality_score', 0)), 
                reverse=True
            )
            
            # Return limited number of sources
            return sorted_sources[:limit]
            
        except Exception as e:
            logger.error(f"Error getting trending sources: {str(e)}")
            return []


class WebScraperService:
    """
    Service for web scraping and content analysis.
    Provides methods for extracting content from websites, blogs, and RSS feeds.
    
    Integrates with SourceTracker to maintain a dynamic database of trusted sources,
    which improves over time as new sources are discovered during research.
    """

    def __init__(self):
        """Initialize the web scraper service with default settings."""
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
        self.timeout = 10
        self.source_tracker = SourceTracker()
        logger.info("Web Scraper Service initialized")

    def extract_content_from_url(self, url):
        """
        Extract main content from a URL using trafilatura.
        
        Args:
            url (str): The URL to extract content from
            
        Returns:
            dict: A dictionary containing extracted content, metadata, and analysis
        """
        try:
            logger.info(f"Extracting content from URL: {url}")
            downloaded = trafilatura.fetch_url(url)
            if not downloaded:
                logger.warning(f"Failed to download content from URL: {url}")
                return None

            # Extract the main content
            text = trafilatura.extract(downloaded)
            if not text:
                logger.warning(f"Failed to extract text content from URL: {url}")
                return None

            # Extract metadata if available
            metadata = trafilatura.extract_metadata(downloaded)
            
            # Extract the title from metadata or attempt to parse it
            title = None
            if metadata and 'title' in metadata:
                title = metadata['title']
            else:
                # Parse with BeautifulSoup as fallback for title extraction
                try:
                    soup = BeautifulSoup(downloaded, 'html.parser')
                    title_tag = soup.find('title')
                    if title_tag:
                        title = title_tag.text.strip()
                except Exception as e:
                    logger.error(f"Error extracting title with BeautifulSoup: {str(e)}")
            
            # Perform basic text analysis
            sentiment = self._analyze_sentiment(text)
            keywords = self._extract_keywords(text)
            summary = self._summarize_text(text)
            
            result = {
                'url': url,
                'title': title,
                'content': text,
                'metadata': metadata,
                'analysis': {
                    'sentiment': sentiment,
                    'keywords': keywords,
                    'summary': summary,
                    'word_count': len(text.split()),
                    'extracted_at': datetime.now().isoformat()
                }
            }
            
            logger.info(f"Successfully extracted and analyzed content from {url}")
            return result
        
        except Exception as e:
            logger.error(f"Error extracting content from URL {url}: {str(e)}")
            return None
            
    def extract_content_from_url_with_context(self, url, blog_context):
        """
        Extract content from a URL using trafilatura with blog context awareness.
        This enhanced version analyzes content relevance to specific blog themes.
        
        Args:
            url (str): The URL to extract content from
            blog_context (dict): Blog context information (name, theme, topics, audience)
            
        Returns:
            dict: A dictionary containing extracted content, metadata, and relevance scoring
        """
        try:
            # First get content normally
            content_data = self.extract_content_from_url(url)
            
            if not content_data:
                return None
                
            # Add blog context relevance scoring
            if 'content' in content_data and content_data['content']:
                text = content_data['content']
                
                # Calculate relevance scores based on blog context
                relevance_scores = self._calculate_blog_relevance(text, blog_context)
                
                # Add relevance information to the content data
                content_data['blog_relevance'] = relevance_scores
                
                # If we have an analysis section, enhance it with blog-specific insights
                if 'analysis' in content_data:
                    content_data['analysis']['blog_insights'] = self._generate_blog_insights(
                        text, blog_context, content_data['analysis']
                    )
                
            # Add the blog context that was used
            content_data['blog_context'] = {
                'name': blog_context.get('name', ''),
                'theme': blog_context.get('theme', ''),
                'topics': blog_context.get('topics', [])
            }
                
            return content_data
            
        except Exception as e:
            logger.error(f"Error extracting content with context from {url}: {str(e)}")
            return None

    def extract_with_newspaper(self, url):
        """
        Extract article content using the newspaper3k library.
        This is particularly useful for news articles and blogs.
        
        Args:
            url (str): The URL to extract content from
            
        Returns:
            dict: A dictionary containing the extracted article content and metadata
        """
        try:
            logger.info(f"Extracting article from URL: {url}")
            article = Article(url)
            article.download()
            article.parse()
            article.nlp()  # This performs natural language processing
            
            result = {
                'url': url,
                'title': article.title,
                'text': article.text,
                'summary': article.summary,
                'keywords': article.keywords,
                'publish_date': article.publish_date.isoformat() if article.publish_date else None,
                'top_image': article.top_image,
                'images': list(article.images),
                'authors': article.authors,
                'word_count': len(article.text.split()),
                'extracted_at': datetime.now().isoformat()
            }
            
            logger.info(f"Successfully extracted article from {url}")
            return result
        
        except Exception as e:
            logger.error(f"Error extracting article from URL {url}: {str(e)}")
            return None
            
    def extract_with_newspaper_and_context(self, url, blog_context):
        """
        Extract article content using the newspaper3k library with blog context awareness.
        
        Args:
            url (str): The URL to extract content from
            blog_context (dict): Blog context information (name, theme, topics, audience)
            
        Returns:
            dict: A dictionary containing the extracted article content and metadata with relevance scoring
        """
        try:
            # First get article normally
            result = self.extract_with_newspaper(url)
            
            if not result:
                return None
                
            # Add blog context relevance scoring
            if 'text' in result and result['text']:
                text = result['text']
                
                # Calculate relevance scores based on blog context
                relevance_scores = self._calculate_blog_relevance(text, blog_context)
                
                # Add relevance information to the result
                result['blog_relevance'] = relevance_scores
                
                # Generate blog-specific insights for this content
                result['blog_insights'] = self._generate_blog_insights(
                    text, blog_context, {
                        'keywords': result.get('keywords', []),
                        'summary': result.get('summary', '')
                    }
                )
                
            # Add the blog context that was used
            result['blog_context'] = {
                'name': blog_context.get('name', ''),
                'theme': blog_context.get('theme', ''),
                'topics': blog_context.get('topics', [])
            }
                
            return result
            
        except Exception as e:
            logger.error(f"Error extracting article with context from {url}: {str(e)}")
            return None

    def fetch_rss_feed(self, feed_url, limit=10):
        """
        Fetch and parse an RSS feed to extract recent articles.
        
        Args:
            feed_url (str): The URL of the RSS feed
            limit (int): Maximum number of entries to return
            
        Returns:
            list: A list of dictionaries containing feed entries
        """
        try:
            logger.info(f"Fetching RSS feed: {feed_url}")
            feed = feedparser.parse(feed_url)
            
            if not feed.entries:
                logger.warning(f"No entries found in RSS feed: {feed_url}")
                return []
            
            results = []
            for i, entry in enumerate(feed.entries):
                if i >= limit:
                    break
                    
                item = {
                    'title': entry.get('title', ''),
                    'link': entry.get('link', ''),
                    'summary': entry.get('summary', ''),
                    'published': entry.get('published', ''),
                    'id': entry.get('id', ''),
                }
                
                # Add additional fields if available
                if 'author' in entry:
                    item['author'] = entry.author
                if 'tags' in entry:
                    item['tags'] = [tag.term for tag in entry.tags] if hasattr(entry.tags, '__iter__') else []
                if 'content' in entry:
                    item['content'] = entry.content[0].value if entry.content and len(entry.content) > 0 and 'value' in entry.content[0] else ''
                
                results.append(item)
            
            logger.info(f"Successfully fetched {len(results)} entries from RSS feed: {feed_url}")
            return results
        
        except Exception as e:
            logger.error(f"Error fetching RSS feed {feed_url}: {str(e)}")
            return []
            
    def fetch_rss_feed_with_context(self, feed_url, limit=10, blog_context=None):
        """
        Fetch and parse an RSS feed with blog context awareness.
        Analyzes entries for relevance to the blog theme and reorders/filters accordingly.
        
        Args:
            feed_url (str): The URL of the RSS feed
            limit (int): Maximum number of entries to return
            blog_context (dict): Blog context information (name, theme, topics, audience)
            
        Returns:
            list: A list of dictionaries containing feed entries with relevance scoring
        """
        try:
            # First get feed entries normally
            entries = self.fetch_rss_feed(feed_url, limit * 2)  # Get more entries than needed for filtering
            
            if not entries or not blog_context:
                return entries
                
            # Process entries with context awareness
            processed_entries = []
            for entry in entries:
                # Extract text content from entry for analysis
                text = ""
                if 'summary' in entry and entry['summary']:
                    text += entry['summary'] + " "
                if 'content' in entry and entry['content']:
                    text += entry['content'] + " "
                if 'title' in entry and entry['title']:
                    text += entry['title']
                
                if not text.strip():
                    # Skip entries with no text content for analysis
                    continue
                
                # Calculate relevance score
                relevance_scores = self._calculate_blog_relevance(text, blog_context)
                
                # Add relevance information to the entry
                entry['blog_relevance'] = relevance_scores
                
                # Add blog context that was used
                entry['blog_context'] = {
                    'name': blog_context.get('name', ''),
                    'theme': blog_context.get('theme', ''),
                    'topics': blog_context.get('topics', [])
                }
                
                processed_entries.append(entry)
            
            # Sort entries by relevance score (descending)
            processed_entries.sort(key=lambda x: x.get('blog_relevance', {}).get('overall_score', 0), reverse=True)
            
            # Return only the most relevant entries
            return processed_entries[:limit]
            
        except Exception as e:
            logger.error(f"Error processing RSS feed with context {feed_url}: {str(e)}")
            return self.fetch_rss_feed(feed_url, limit)  # Fall back to regular fetch

    def research_topic(self, topic, num_sources=5, context=None):
        """
        Research a specific topic by searching for and analyzing relevant content.
        Uses SourceTracker to dynamically improve source selection over time.
        
        Args:
            topic (str): The topic to research
            num_sources (int): Number of sources to include in the research
            context (dict, optional): Blog context information to guide research relevance,
                                      containing theme, topics, description, tone, audience
            
        Returns:
            dict: A dictionary containing research results
        """
        try:
            logger.info(f"Researching topic: {topic}")
            
            # If we have blog context, use it to enrich the research
            blog_context_string = ""
            if context:
                logger.info(f"Using blog context: {context.get('theme')} with tone: {context.get('tone')}")
                
                # Create a context string that can be used to enhance search queries
                theme = context.get('theme', '')
                topics = context.get('topics', [])
                description = context.get('description', '')
                audience = context.get('audience', 'general')
                
                # Build a context string incorporating blog information
                blog_context_string = f"{theme} "
                if topics:
                    blog_context_string += ' '.join(topics) + " "
                if description:
                    blog_context_string += description
                
                # Adjust the topic to be more specific to the blog context
                if theme and not topic.lower() in theme.lower():
                    original_topic = topic
                    topic = f"{topic} for {theme}"
                    logger.info(f"Modified research topic from '{original_topic}' to '{topic}' based on blog context")
            
            # Get good sources for this topic from our source tracker
            known_sources = self.source_tracker.get_sources_for_topic(topic, limit=num_sources)
            
            # If we don't have enough known sources, add some general search URLs
            # In a production environment, these would be actual search API results
            if len(known_sources) < num_sources:
                # Generate search URLs for the remaining slots
                search_urls = [
                    f"https://en.wikipedia.org/wiki/{topic.replace(' ', '_')}",
                    f"https://www.reddit.com/search/?q={topic.replace(' ', '%20')}",
                    f"https://medium.com/search?q={topic.replace(' ', '%20')}"
                ]
                
                # Use only the number of search URLs needed to reach num_sources
                remaining = num_sources - len(known_sources)
                search_urls = search_urls[:remaining]
                
                # Convert search URLs to the same format as known_sources
                for url in search_urls:
                    parsed_url = urlparse(url)
                    known_sources.append({
                        'url': url,
                        'domain': parsed_url.netloc,
                        'title': parsed_url.netloc,
                        'quality_score': 5.0,  # Default quality score
                        'category': None,
                        'has_rss': False,
                        'rss_url': None,
                        'relevance_score': 5.0  # Default relevance score
                    })
            
            # Extract content from each source
            articles = []
            for source in known_sources:
                url = source['url']
                content = self.extract_content_from_url(url)
                
                if content:
                    # Update our source tracker with information we discovered
                    if 'title' in content and content['title']:
                        # Update source info in tracker
                        self.source_tracker.add_source(
                            url=url,
                            title=content['title'],
                            category=source.get('category'),
                            quality_score=source.get('quality_score', 5.0)
                        )
                        
                        # Associate this topic with the source
                        relevance_score = source.get('relevance_score', 5.0)
                        if 'analysis' in content:
                            # Adjust relevance score based on keyword density
                            if 'keywords' in content['analysis'] and content['analysis']['keywords']:
                                # Check if any topic keywords appear in the content keywords
                                topic_words = set(topic.lower().split())
                                content_keywords = set([k.lower() for k in content['analysis']['keywords']])
                                overlap = topic_words.intersection(content_keywords)
                                
                                # Boost relevance score based on keyword overlap
                                if overlap:
                                    relevance_score += min(3.0, len(overlap))
                        
                        # Finalize the source-topic association
                        self.source_tracker.associate_topic_with_source(
                            topic=topic, 
                            url=url,
                            relevance_score=min(10.0, relevance_score)
                        )
                    
                    # Add content to research results
                    articles.append(content)
                    
                    # Try to find RSS feed if we don't have one for this source
                    if not source.get('has_rss') and 'metadata' in content:
                        try:
                            # Check if there's an RSS link in the metadata
                            soup = BeautifulSoup(content.get('html', ''), 'html.parser')
                            rss_links = soup.select('link[type="application/rss+xml"]')
                            
                            if rss_links:
                                rss_url = rss_links[0].get('href')
                                if rss_url:
                                    # Update the source with RSS info
                                    self.source_tracker.add_source(
                                        url=url,
                                        title=source.get('title') or content.get('title'),
                                        has_rss=True,
                                        rss_url=rss_url
                                    )
                                    logger.info(f"Discovered RSS feed for {url}: {rss_url}")
                        except Exception as rss_error:
                            logger.warning(f"Error looking for RSS feed in {url}: {str(rss_error)}")
            
            # Combine keywords from all sources
            all_keywords = []
            for article in articles:
                if 'analysis' in article and 'keywords' in article['analysis']:
                    all_keywords.extend(article['analysis']['keywords'])
            
            # Count keyword frequencies
            keyword_counter = Counter(all_keywords)
            top_keywords = [{"keyword": kw, "count": count} for kw, count in keyword_counter.most_common(20)]
            
            # Generate word cloud if we have keywords
            wordcloud_path = None
            if all_keywords:
                wordcloud_path = self._generate_wordcloud(all_keywords, topic)
            
            # Look for additional sources to add from the articles we found
            # (e.g., extract links from content and add as potential future sources)
            self._extract_additional_sources(articles, topic)
            
            # Prepare research results
            research_results = {
                'topic': topic,
                'sources': len(articles),
                'articles': articles,
                'keywords': top_keywords,
                'wordcloud_path': wordcloud_path,
                'research_date': datetime.now().isoformat()
            }
            
            # Add blog context information if available
            if context:
                research_results['blog_context'] = {
                    'theme': context.get('theme', ''),
                    'audience': context.get('audience', 'general'),
                    'tone': context.get('tone', 'informative')
                }
            
            logger.info(f"Successfully completed research on topic: {topic}")
            return research_results
        
        except Exception as e:
            logger.error(f"Error researching topic {topic}: {str(e)}")
            return {
                'topic': topic,
                'error': str(e),
                'research_date': datetime.now().isoformat()
            }

    def _analyze_sentiment(self, text):
        """
        Analyze the sentiment of a text using TextBlob.
        
        Args:
            text (str): The text to analyze
            
        Returns:
            dict: A dictionary containing sentiment analysis results
        """
        try:
            analysis = TextBlob(text)
            # Sentiment polarity ranges from -1 (negative) to 1 (positive)
            sentiment = analysis.sentiment
            
            # Determine sentiment category
            category = "neutral"
            if sentiment.polarity > 0.2:
                category = "positive"
            elif sentiment.polarity < -0.2:
                category = "negative"
            
            return {
                'polarity': sentiment.polarity,
                'subjectivity': sentiment.subjectivity,
                'category': category
            }
        except Exception as e:
            logger.error(f"Error analyzing sentiment: {str(e)}")
            return {'polarity': 0, 'subjectivity': 0, 'category': 'unknown'}

    def _extract_keywords(self, text, max_keywords=20):
        """
        Extract important keywords from text using NLTK.
        
        Args:
            text (str): The text to extract keywords from
            max_keywords (int): Maximum number of keywords to return
            
        Returns:
            list: A list of the most important keywords
        """
        try:
            # Tokenize and convert to lowercase
            tokens = word_tokenize(text.lower())
            
            # Remove stopwords, punctuation, and short words
            stopword_list = set(stopwords.words('english'))
            words = [word for word in tokens if word.isalpha() and word not in stopword_list and len(word) > 3]
            
            # Count frequencies
            word_freq = Counter(words)
            
            # Return the most common words
            return [word for word, count in word_freq.most_common(max_keywords)]
        except Exception as e:
            logger.error(f"Error extracting keywords: {str(e)}")
            return []

    def _summarize_text(self, text, num_sentences=5):
        """
        Generate a summary of the text using extractive summarization.
        
        Args:
            text (str): The text to summarize
            num_sentences (int): Number of sentences to include in the summary
            
        Returns:
            str: A summary of the text
        """
        try:
            # Split into sentences
            sentences = sent_tokenize(text)
            
            # If we have fewer sentences than requested, return all
            if len(sentences) <= num_sentences:
                return text
            
            # Tokenize and remove stopwords
            stopword_list = set(stopwords.words('english'))
            word_frequencies = {}
            
            for sentence in sentences:
                for word in word_tokenize(sentence.lower()):
                    if word.isalpha() and word not in stopword_list:
                        if word not in word_frequencies:
                            word_frequencies[word] = 1
                        else:
                            word_frequencies[word] += 1
            
            # Normalize word frequencies
            max_frequency = max(word_frequencies.values()) if word_frequencies else 1
            for word in word_frequencies:
                word_frequencies[word] = word_frequencies[word] / max_frequency
            
            # Calculate sentence scores
            sentence_scores = {}
            for i, sentence in enumerate(sentences):
                for word in word_tokenize(sentence.lower()):
                    if word in word_frequencies:
                        if i not in sentence_scores:
                            sentence_scores[i] = word_frequencies[word]
                        else:
                            sentence_scores[i] += word_frequencies[word]
            
            # Get top sentences
            top_sentences = sorted(sentence_scores.items(), key=lambda x: x[1], reverse=True)[:num_sentences]
            top_sentences = sorted(top_sentences, key=lambda x: x[0])  # Sort by position in the original text
            
            # Combine into summary
            summary = ' '.join([sentences[i] for i, score in top_sentences])
            return summary
        
        except Exception as e:
            logger.error(f"Error summarizing text: {str(e)}")
            return text[:500] + "..." if len(text) > 500 else text  # Fallback to text truncation

    def _generate_wordcloud(self, keywords, topic):
        """
        Generate a word cloud image from keywords.
        
        Args:
            keywords (list): List of keywords to include in the word cloud
            topic (str): Topic name for the filename
            
        Returns:
            str: Path to the generated word cloud image
        """
        try:
            # Create wordcloud if we have meaningful keywords
            if not keywords:
                return None
                
            # Create output directory if it doesn't exist
            output_dir = os.path.join("static", "images", "wordclouds")
            os.makedirs(output_dir, exist_ok=True)
            
            # Create a safe filename from the topic
            safe_topic = re.sub(r'[^\w\s-]', '', topic.lower()).strip().replace(' ', '_')
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{safe_topic}_{timestamp}.png"
            output_path = os.path.join(output_dir, filename)
            
            # Create word cloud
            wordcloud = WordCloud(
                width=800, 
                height=400, 
                background_color='white',
                max_words=100,
                contour_width=3,
                contour_color='steelblue'
            ).generate(' '.join(keywords))
            
            # Save the image
            plt.figure(figsize=(10, 5))
            plt.imshow(wordcloud, interpolation='bilinear')
            plt.axis('off')
            plt.tight_layout(pad=0)
            plt.savefig(output_path)
            plt.close()
            
            logger.info(f"Generated word cloud image at {output_path}")
            return output_path
        
        except Exception as e:
            logger.error(f"Error generating word cloud: {str(e)}")
            return None
    
    def _calculate_blog_relevance(self, text, blog_context):
        """
        Calculate relevance scores for text content based on blog context.
        
        Args:
            text (str): The text content to analyze
            blog_context (dict): Blog context information (name, theme, topics, audience)
            
        Returns:
            dict: Dictionary with various relevance scores
        """
        try:
            # Extract blog context details
            blog_theme = blog_context.get('theme', '').lower()
            blog_topics = [t.lower() for t in blog_context.get('topics', [])]
            blog_audience = blog_context.get('audience', '').lower()
            blog_tone = blog_context.get('tone', '').lower()
            
            # Prepare text for analysis
            text_lower = text.lower()
            words = text_lower.split()
            
            # Initialize scores
            theme_score = 0
            topic_score = 0
            audience_score = 0
            tone_score = 0
            
            # Calculate theme relevance
            if blog_theme:
                theme_words = blog_theme.split()
                theme_matches = sum(1 for word in theme_words if word in text_lower)
                theme_score = min(10, theme_matches * 2)  # Scale up to max 10
            
            # Calculate topic relevance
            matching_topics = []
            for topic in blog_topics:
                topic_words = topic.split()
                topic_matches = sum(1 for word in topic_words if word in text_lower)
                if topic_matches > 0:
                    topic_score += min(5, topic_matches)  # Add up to 5 points per topic
                    matching_topics.append(topic)
            topic_score = min(10, topic_score)  # Cap at 10
            
            # Calculate audience relevance
            if blog_audience:
                audience_words = blog_audience.split()
                audience_matches = sum(1 for word in audience_words if word in text_lower)
                audience_score = min(5, audience_matches * 2)  # Scale up to max 5
            
            # Calculate tone relevance using sentiment
            if blog_tone:
                # Analyze sentiment
                blob = TextBlob(text)
                sentiment = blob.sentiment
                
                # Match tone to sentiment
                tone_match = 0
                if blog_tone in ['positive', 'upbeat', 'optimistic'] and sentiment.polarity > 0.2:
                    tone_match = min(5, sentiment.polarity * 10)
                elif blog_tone in ['negative', 'critical', 'cautious'] and sentiment.polarity < -0.2:
                    tone_match = min(5, abs(sentiment.polarity) * 10)
                elif blog_tone in ['neutral', 'balanced', 'objective'] and abs(sentiment.polarity) < 0.3:
                    tone_match = 5 - (abs(sentiment.polarity) * 10)  # Higher for more neutral
                
                tone_score = max(0, tone_match)
            
            # Calculate keyword relevance
            keywords = self._extract_keywords(text)
            keyword_relevance = sum(1 for kw in keywords if 
                                    kw.lower() in blog_theme.lower() or 
                                    any(kw.lower() in t.lower() for t in blog_topics))
            keyword_score = min(5, keyword_relevance)
            
            # Calculate overall score (weighted sum)
            overall_score = (
                theme_score * 0.35 +    # Theme is most important
                topic_score * 0.3 +     # Topics are very important
                audience_score * 0.15 + # Audience is somewhat important
                tone_score * 0.1 +      # Tone is less important
                keyword_score * 0.1     # Keyword relevance is additional factor
            )
            
            return {
                'theme_score': theme_score,
                'topic_score': topic_score,
                'audience_score': audience_score,
                'tone_score': tone_score,
                'keyword_score': keyword_score,
                'overall_score': overall_score,
                'matching_topics': matching_topics,
                'max_possible': 10  # The maximum possible score
            }
            
        except Exception as e:
            logger.error(f"Error calculating blog relevance: {str(e)}")
            return {
                'theme_score': 0,
                'topic_score': 0,
                'audience_score': 0,
                'tone_score': 0,
                'keyword_score': 0,
                'overall_score': 0,
                'matching_topics': [],
                'max_possible': 10,
                'error': str(e)
            }
    
    def _generate_blog_insights(self, text, blog_context, analysis):
        """
        Generate blog-specific insights based on content analysis and blog context.
        
        Args:
            text (str): The text content to analyze
            blog_context (dict): Blog context information
            analysis (dict): Existing analysis data
            
        Returns:
            dict: Dictionary with blog-specific insights
        """
        try:
            blog_theme = blog_context.get('theme', '')
            blog_topics = blog_context.get('topics', [])
            blog_audience = blog_context.get('audience', '')
            
            # Extract keywords from content
            keywords = analysis.get('keywords', []) if isinstance(analysis, dict) else []
            
            # Calculate keyword overlap with blog topics
            topic_overlap = []
            for topic in blog_topics:
                topic_lower = topic.lower()
                matching_keywords = [k for k in keywords if k.lower() in topic_lower or topic_lower in k.lower()]
                if matching_keywords:
                    topic_overlap.append({
                        'topic': topic,
                        'matching_keywords': matching_keywords
                    })
            
            # Determine if content is on-theme
            on_theme = False
            theme_keywords = []
            if blog_theme:
                theme_words = blog_theme.lower().split()
                text_lower = text.lower()
                
                # Check for theme words in the text
                theme_mentions = sum(text_lower.count(word) for word in theme_words if len(word) > 3)
                on_theme = theme_mentions >= 2  # Arbitrary threshold
                
                # Find keywords related to theme
                theme_keywords = [k for k in keywords if any(word in k.lower() for word in theme_words)]
            
            # Calculate content readability (basic metric)
            sentences = text.split('.')
            avg_words_per_sentence = sum(len(s.split()) for s in sentences if s.strip()) / max(1, len(sentences))
            
            # Determine if readability matches audience
            readability_matches_audience = True  # Default assumption
            if blog_audience:
                if 'technical' in blog_audience.lower() and avg_words_per_sentence < 15:
                    readability_matches_audience = False
                elif 'beginner' in blog_audience.lower() and avg_words_per_sentence > 20:
                    readability_matches_audience = False
            
            return {
                'on_theme': on_theme,
                'theme_keywords': theme_keywords,
                'topic_overlap': topic_overlap,
                'readability': {
                    'avg_words_per_sentence': round(avg_words_per_sentence, 1),
                    'matches_audience': readability_matches_audience
                },
                'recommendation': self._generate_content_recommendation(
                    on_theme, bool(topic_overlap), readability_matches_audience, blog_context
                )
            }
            
        except Exception as e:
            logger.error(f"Error generating blog insights: {str(e)}")
            return {
                'error': str(e),
                'on_theme': False,
                'topic_overlap': [],
                'recommendation': 'Error generating insights'
            }
    
    def _generate_content_recommendation(self, on_theme, has_topic_overlap, readability_matches_audience, blog_context):
        """
        Generate a recommendation for how to use this content based on relevance to blog.
        
        Args:
            on_theme (bool): Whether the content matches the blog theme
            has_topic_overlap (bool): Whether there's overlap with blog topics
            readability_matches_audience (bool): Whether readability matches audience
            blog_context (dict): Blog context information
            
        Returns:
            str: A recommendation string
        """
        if on_theme and has_topic_overlap and readability_matches_audience:
            return f"Highly relevant content for {blog_context.get('name')} blog. Consider using as primary source."
        elif on_theme and has_topic_overlap:
            return f"Relevant to theme and topics of {blog_context.get('name')} blog, but may need readability adjustment."
        elif on_theme:
            return f"On-theme for {blog_context.get('name')} blog, but lacks topic specificity."
        elif has_topic_overlap:
            return f"Contains topic overlap with {blog_context.get('name')} blog, but isn't fully on-theme."
        else:
            return f"Low relevance to {blog_context.get('name')} blog. Consider as supplementary content only."
            
    def _extract_additional_sources(self, articles, topic, max_sources=3):
        """
        Extract additional sources from article content to expand our knowledge base.
        
        Args:
            articles (list): List of article dictionaries
            topic (str): The current topic being researched
            max_sources (int): Maximum number of additional sources to extract
            
        Returns:
            None (updates source tracker internally)
        """
        try:
            # Track domains we've already processed
            processed_domains = set()
            additional_sources = []
            
            for article in articles:
                # Skip if no content or url
                if not article.get('content') or not article.get('url'):
                    continue
                
                # Get the domain of the current article to avoid self-references
                current_domain = urlparse(article['url']).netloc
                processed_domains.add(current_domain)
                
                # Extract links from the article content using BeautifulSoup
                # In a real scenario, we would have the HTML content
                # But since we're using trafilatura which returns plaintext,
                # we'll simulate by looking for patterns that might be URLs
                
                # Extract links with regex (simple pattern for demonstration)
                url_pattern = re.compile(r'https?://[^\s()<>]+(?:\([^\s()<>]+\)|[^\s`!()\[\]{};:\'".,<>?«»""''])+')
                found_urls = url_pattern.findall(article.get('content', ''))
                
                # Process each URL
                for url in found_urls[:10]:  # Limit to first 10 URLs to avoid too many requests
                    try:
                        # Parse URL and check if we should process it
                        parsed_url = urlparse(url)
                        domain = parsed_url.netloc
                        
                        # Skip if already processed or same as current domain
                        if not domain or domain in processed_domains:
                            continue
                        
                        # Skip common social media, multimedia and non-article domains
                        skip_domains = ['youtube.com', 'facebook.com', 'twitter.com', 'instagram.com',
                                       'linkedin.com', 'pinterest.com', 'flickr.com', 'imgur.com']
                        if any(skip_domain in domain for skip_domain in skip_domains):
                            continue
                        
                        # Add to processed list to avoid duplicates
                        processed_domains.add(domain)
                        
                        # Add to sources list for potential future use
                        additional_sources.append({
                            'url': url,
                            'domain': domain,
                            'source_article': article['url'],
                            'topic': topic
                        })
                        
                        # Stop if we've found enough sources
                        if len(additional_sources) >= max_sources:
                            break
                    
                    except Exception as url_error:
                        logger.warning(f"Error processing URL {url}: {str(url_error)}")
                
                # Stop if we've found enough sources
                if len(additional_sources) >= max_sources:
                    break
            
            # Add new sources to our tracker 
            for source in additional_sources:
                try:
                    # Add the source to our tracker
                    self.source_tracker.add_source(
                        url=source['url'],
                        title=None,  # We'll let the tracker set a default title
                        category=None,  # Category unknown at this point
                        quality_score=4.0  # Start with slightly lower score for discovered sources
                    )
                    
                    # Associate with the current topic
                    self.source_tracker.associate_topic_with_source(
                        topic=topic,
                        url=source['url'],
                        relevance_score=5.0  # Default relevance score
                    )
                    
                    logger.info(f"Added additional source for future research: {source['url']}")
                    
                except Exception as add_error:
                    logger.warning(f"Error adding additional source {source['url']}: {str(add_error)}")
            
            logger.info(f"Extracted {len(additional_sources)} additional sources for future research")
            
        except Exception as e:
            logger.error(f"Error extracting additional sources: {str(e)}")
    
    def get_trending_topics(self, category=None, limit=10, context=None):
        """
        Get trending topics based on recent web content.
        Uses source tracker to get most popular sources if available.
        
        Args:
            category (str): Optional category to filter topics by
            limit (int): Maximum number of topics to return
            context (dict, optional): Blog context information to guide topic relevance,
                                     containing theme, topics, description, tone, audience
            
        Returns:
            list: A list of trending topics with their scores
        """
        try:
            # Log information about context if provided
            if context:
                logger.info(f"Using blog context for trending topics: {context.get('theme')} with topics: {context.get('topics')}")
                
                # If no category is specified but context has a theme, use the theme as category
                if not category and context.get('theme'):
                    theme = context.get('theme').lower()
                    # Map theme to closest category
                    if any(keyword in theme for keyword in ['tech', 'software', 'digital', 'code', 'ai']):
                        category = 'technology'
                    elif any(keyword in theme for keyword in ['health', 'fitness', 'wellness', 'medical']):
                        category = 'health'
                    elif any(keyword in theme for keyword in ['business', 'entrepreneur', 'finance', 'work']):
                        category = 'business'
                    elif any(keyword in theme for keyword in ['life', 'home', 'travel', 'food', 'art']):
                        category = 'lifestyle'
                    logger.info(f"Auto-selected category '{category}' based on blog theme")
            
            # First check if we have sources with RSS feeds to get real trending content
            trending_sources = self.source_tracker.get_trending_sources(category=category, limit=5)
            real_trending_topics = []
            
            # Get recent content from RSS feeds if available
            for source in trending_sources:
                if source.get('has_rss') and source.get('rss_url'):
                    try:
                        # Fetch the RSS feed
                        entries = self.fetch_rss_feed(source['rss_url'], limit=5)
                        
                        # Extract titles as potential trending topics
                        for entry in entries:
                            if entry.get('title'):
                                # Clean and normalize the title
                                title = entry.get('title').strip()
                                
                                # Add to trending topics with source info
                                real_trending_topics.append({
                                    "topic": title,
                                    "score": source.get('quality_score', 5.0) * 10,  # Scale to 0-100
                                    "change": 5.0,  # Positive change for fresh content
                                    "source": source['title'],
                                    "link": entry.get('link')
                                })
                    except Exception as rss_error:
                        logger.warning(f"Error fetching RSS feed from {source['title']}: {str(rss_error)}")
            
            # If we have real trending topics from RSS feeds, use them
            if real_trending_topics:
                # Sort by score and limit
                real_trending_topics.sort(key=lambda x: x["score"], reverse=True)
                if len(real_trending_topics) >= limit:
                    return real_trending_topics[:limit]
            
            # If we don't have enough real trending topics, fall back to simulated ones
            # In a real implementation, this would use Google Trends, Twitter API, etc.
            sample_topics_by_category = {
                "technology": [
                    "Artificial Intelligence", "Machine Learning", "Blockchain", 
                    "5G Technology", "Quantum Computing", "Cybersecurity",
                    "Edge Computing", "Internet of Things", "Virtual Reality",
                    "Cloud Computing", "Robotics", "Data Science"
                ],
                "health": [
                    "Mental Health", "Nutrition", "Exercise Science", 
                    "Telehealth", "Preventive Care", "Sleep Science",
                    "Mindfulness", "Personalized Medicine", "Longevity",
                    "Gut Health", "Immune System", "Plant-based Diet"
                ],
                "business": [
                    "Remote Work", "Digital Transformation", "Sustainability", 
                    "Entrepreneurship", "Future of Work", "Leadership",
                    "E-commerce", "Financial Independence", "Marketing Strategy",
                    "Personal Branding", "Business Analytics", "Customer Experience"
                ],
                "lifestyle": [
                    "Minimalism", "Digital Detox", "Sustainable Living", 
                    "Work-Life Balance", "Home Office Design", "Productivity",
                    "Personal Development", "Travel Trends", "Culinary Arts",
                    "Personal Finance", "Fitness at Home", "Creative Hobbies"
                ]
            }
            
            # Generate random sample
            if category and category in sample_topics_by_category:
                topics = sample_topics_by_category[category]
            else:
                # If no category specified or invalid category, use all categories
                topics = []
                for cat_topics in sample_topics_by_category.values():
                    topics.extend(cat_topics)
            
            # Shuffle and limit
            random.shuffle(topics)
            remaining_slots = limit - len(real_trending_topics)
            topics = topics[:remaining_slots]
            
            # Add random trending score
            simulated_topics = []
            for topic in topics:
                simulated_topics.append({
                    "topic": topic,
                    "score": round(random.uniform(70, 100), 1),  # Random score between 70-100
                    "change": round(random.uniform(-20, 20), 1),  # Random 24h change
                    "source": "Trending Analysis",
                    "link": None
                })
            
            # Combine real and simulated topics
            result = real_trending_topics + simulated_topics
            
            # If we have blog context, enhance topic relevance
            if context and context.get('topics'):
                blog_topics = [t.lower() for t in context.get('topics', [])]
                blog_theme = context.get('theme', '').lower()
                
                # Boost scores for topics relevant to the blog
                for topic_item in result:
                    topic_text = topic_item['topic'].lower()
                    
                    # Check if any of the blog topics or theme appears in the trending topic
                    # This is a simple relevance check, in a production system you'd use NLP
                    boost = 0
                    
                    # Boost for theme match
                    if blog_theme and (blog_theme in topic_text or any(word in topic_text for word in blog_theme.split())):
                        boost += 15
                        topic_item['theme_match'] = True
                    
                    # Boost for topic match
                    for blog_topic in blog_topics:
                        if blog_topic in topic_text or any(word in topic_text for word in blog_topic.split()):
                            boost += 10
                            topic_item['topic_match'] = True
                            break
                    
                    # Apply the boost
                    if boost > 0:
                        topic_item['score'] += boost
                        topic_item['boosted_for_relevance'] = True
                        logger.info(f"Boosted score for '{topic_item['topic']}' by {boost} points for relevance to blog theme/topics")
            
            # Sort by score
            result.sort(key=lambda x: x["score"], reverse=True)
            
            return result
        
        except Exception as e:
            logger.error(f"Error getting trending topics: {str(e)}")
            
            # Fallback to basic simulated topics if there's an error
            return [
                {"topic": "Artificial Intelligence", "score": 95.0, "change": 2.5, "source": "Fallback", "link": None},
                {"topic": "Digital Transformation", "score": 90.0, "change": 1.5, "source": "Fallback", "link": None},
                {"topic": "Mental Health", "score": 88.5, "change": 3.0, "source": "Fallback", "link": None},
                {"topic": "Remote Work", "score": 85.0, "change": -1.0, "source": "Fallback", "link": None},
                {"topic": "Sustainable Living", "score": 82.5, "change": 5.0, "source": "Fallback", "link": None}
            ][:limit]
            
    def get_trending_topics_with_context(self, category=None, limit=10, blog_context=None):
        """
        Get trending topics specifically filtered and ranked for blog context relevance.
        This specialized version ensures that all returned topics are highly relevant to the blog.
        
        Args:
            category (str): Optional category to filter topics by
            limit (int): Maximum number of topics to return
            blog_context (dict): Blog context information (name, theme, topics, audience)
            
        Returns:
            list: A list of trending topics with their scores, prioritized for blog relevance
        """
        if not blog_context:
            # If no blog context provided, fall back to regular trending topics
            return self.get_trending_topics(category, limit)
            
        try:
            logger.info(f"Getting trending topics with context for blog: {blog_context.get('name')}")
            
            # Get a larger set of trending topics to filter from
            all_topics = self.get_trending_topics(category, limit * 3, blog_context)
            
            if not all_topics:
                logger.warning("No trending topics found to filter for blog context")
                return []
                
            # Extract blog context information
            blog_name = blog_context.get('name', '')
            blog_theme = blog_context.get('theme', '').lower()
            blog_topics = [t.lower() for t in blog_context.get('topics', [])]
            blog_audience = blog_context.get('audience', '').lower()
            
            # Calculate relevance score for each topic
            for topic in all_topics:
                topic_text = topic['topic'].lower()
                
                # Start with the existing score
                relevance_score = 0
                
                # Check theme relevance
                if blog_theme and (blog_theme in topic_text or any(word in topic_text for word in blog_theme.split())):
                    relevance_score += 30
                    topic['theme_match'] = True
                
                # Check topic relevance
                for blog_topic in blog_topics:
                    if blog_topic in topic_text or any(word in topic_text for word in blog_topic.split()):
                        relevance_score += 20
                        if not 'matching_topics' in topic:
                            topic['matching_topics'] = []
                        topic['matching_topics'].append(blog_topic)
                
                # Check audience relevance
                if blog_audience and blog_audience in topic_text:
                    relevance_score += 15
                    topic['audience_match'] = True
                
                # Store the relevance score
                topic['relevance_score'] = relevance_score
                
                # Adjust the main score to prioritize relevance
                topic['original_score'] = topic['score']
                topic['score'] = topic['score'] + relevance_score
            
            # Sort by the adjusted score
            all_topics.sort(key=lambda x: x['score'], reverse=True)
            
            # Add blog context info to the response
            context_topics = all_topics[:limit]
            for topic in context_topics:
                topic['blog_context'] = {
                    'name': blog_name,
                    'theme': blog_context.get('theme', ''),
                    'topics': blog_context.get('topics', [])
                }
            
            return context_topics
            
        except Exception as e:
            logger.error(f"Error getting trending topics with context: {str(e)}")
            return self.get_trending_topics(category, limit)


# Create a singleton instance
web_scraper_service = WebScraperService()