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
    Maintains a database of trusted sources for web scraping and research.
    Automatically updates as new sources are discovered during research.
    """
    
    def __init__(self, db_path="data/sources.db"):
        """Initialize the source tracker with a SQLite database."""
        self.db_path = db_path
        self._ensure_db_directory()
        self._init_database()
        logger.info(f"SourceTracker initialized with database at {db_path}")
    
    def _ensure_db_directory(self):
        """Create directory for the database if it doesn't exist."""
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
    
    def _init_database(self):
        """Initialize the sources database if it doesn't exist."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Create sources table if it doesn't exist
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS sources (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                domain TEXT UNIQUE,
                url TEXT,
                title TEXT,
                quality_score REAL DEFAULT 0.0,
                category TEXT,
                language TEXT DEFAULT 'en',
                last_scraped TEXT,
                times_used INTEGER DEFAULT 1,
                first_discovered TEXT,
                has_rss INTEGER DEFAULT 0,
                rss_url TEXT,
                notes TEXT
            )
            ''')
            
            # Create topics_sources bridge table for tracking which sources are good for which topics
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS topics_sources (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                topic TEXT,
                source_id INTEGER,
                relevance_score REAL DEFAULT 0.0,
                last_used TEXT,
                UNIQUE(topic, source_id),
                FOREIGN KEY (source_id) REFERENCES sources(id)
            )
            ''')
            
            # Bootstrap with initial sources if the table is empty
            cursor.execute("SELECT COUNT(*) FROM sources")
            count = cursor.fetchone()[0]
            
            if count == 0:
                logger.info("Bootstrapping source database with initial sources")
                self._bootstrap_initial_sources(cursor)
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            logger.error(f"Error initializing sources database: {str(e)}")
    
    def _bootstrap_initial_sources(self, cursor):
        """Populate the database with initial trusted sources."""
        initial_sources = [
            {
                'domain': 'en.wikipedia.org',
                'url': 'https://en.wikipedia.org/',
                'title': 'Wikipedia',
                'quality_score': 9.0,
                'category': 'reference',
                'notes': 'General encyclopedia, high factual accuracy'
            },
            {
                'domain': 'techcrunch.com',
                'url': 'https://techcrunch.com/',
                'title': 'TechCrunch',
                'quality_score': 8.0,
                'category': 'technology',
                'has_rss': 1,
                'rss_url': 'https://techcrunch.com/feed/'
            },
            {
                'domain': 'hbr.org',
                'url': 'https://hbr.org/',
                'title': 'Harvard Business Review',
                'quality_score': 8.5,
                'category': 'business',
                'has_rss': 1,
                'rss_url': 'https://hbr.org/feed'
            },
            {
                'domain': 'nature.com',
                'url': 'https://www.nature.com/',
                'title': 'Nature',
                'quality_score': 9.5,
                'category': 'science',
                'has_rss': 1,
                'rss_url': 'https://www.nature.com/nature.rss'
            },
            {
                'domain': 'blog.google',
                'url': 'https://blog.google/',
                'title': 'Google Blog',
                'quality_score': 7.5,
                'category': 'technology',
                'has_rss': 1,
                'rss_url': 'https://blog.google/rss/'
            }
        ]
        
        now = datetime.now().isoformat()
        for source in initial_sources:
            source.setdefault('last_scraped', now)
            source.setdefault('first_discovered', now)
            source.setdefault('language', 'en')
            source.setdefault('has_rss', 0)
            source.setdefault('times_used', 1)
            
            cursor.execute('''
            INSERT INTO sources 
            (domain, url, title, quality_score, category, language, last_scraped, 
             times_used, first_discovered, has_rss, rss_url, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                source['domain'],
                source['url'],
                source['title'],
                source['quality_score'],
                source['category'],
                source['language'],
                source['last_scraped'],
                source['times_used'],
                source['first_discovered'],
                source['has_rss'],
                source.get('rss_url', None),
                source.get('notes', None)
            ))
    
    def add_source(self, url, title=None, category=None, quality_score=5.0, has_rss=False, rss_url=None):
        """
        Add a new source to the database.
        
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
            
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Check if the domain already exists
            cursor.execute("SELECT id FROM sources WHERE domain = ?", (domain,))
            existing = cursor.fetchone()
            
            if existing:
                # Update the existing record
                source_id = existing[0]
                cursor.execute('''
                UPDATE sources SET 
                url = ?, title = ?, last_scraped = ?, times_used = times_used + 1
                WHERE id = ?
                ''', (url, title, now, source_id))
                
                if category:
                    cursor.execute("UPDATE sources SET category = ? WHERE id = ?", (category, source_id))
                
                if quality_score:
                    cursor.execute('''
                    UPDATE sources SET quality_score = (quality_score + ?) / 2 WHERE id = ?
                    ''', (quality_score, source_id))
                
                if has_rss and rss_url:
                    cursor.execute('''
                    UPDATE sources SET has_rss = 1, rss_url = ? WHERE id = ?
                    ''', (rss_url, source_id))
                
                logger.info(f"Updated existing source: {domain} ({title})")
            else:
                # Insert a new record
                cursor.execute('''
                INSERT INTO sources 
                (domain, url, title, quality_score, category, last_scraped, times_used, 
                first_discovered, has_rss, rss_url)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    domain, url, title, quality_score, category, now, 1, now,
                    1 if has_rss else 0, rss_url
                ))
                source_id = cursor.lastrowid
                logger.info(f"Added new source: {domain} ({title})")
            
            conn.commit()
            conn.close()
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
            
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Find source id
            cursor.execute("SELECT id FROM sources WHERE domain = ?", (domain,))
            result = cursor.fetchone()
            
            if not result:
                logger.warning(f"Cannot associate topic with unknown source: {domain}")
                conn.close()
                return False
            
            source_id = result[0]
            now = datetime.now().isoformat()
            
            # Check if association already exists
            cursor.execute("SELECT id, relevance_score FROM topics_sources WHERE topic = ? AND source_id = ?", 
                         (topic, source_id))
            existing = cursor.fetchone()
            
            if existing:
                # Update the existing association
                assoc_id = existing[0]
                old_score = existing[1]
                # Average the new score with the old score
                updated_score = (old_score + relevance_score) / 2
                
                cursor.execute('''
                UPDATE topics_sources 
                SET relevance_score = ?, last_used = ?
                WHERE id = ?
                ''', (updated_score, now, assoc_id))
                
                logger.debug(f"Updated topic-source association: {topic} - {domain}")
            else:
                # Create a new association
                cursor.execute('''
                INSERT INTO topics_sources (topic, source_id, relevance_score, last_used)
                VALUES (?, ?, ?, ?)
                ''', (topic, source_id, relevance_score, now))
                
                logger.debug(f"Created new topic-source association: {topic} - {domain}")
            
            conn.commit()
            conn.close()
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
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Query for sources associated with this topic
            cursor.execute('''
            SELECT s.url, s.title, s.domain, s.quality_score, s.category, 
                   s.has_rss, s.rss_url, ts.relevance_score
            FROM sources s
            JOIN topics_sources ts ON s.id = ts.source_id
            WHERE ts.topic = ? AND s.quality_score >= ?
            ORDER BY ts.relevance_score DESC, s.quality_score DESC
            LIMIT ?
            ''', (topic, min_quality, limit))
            
            topic_sources = cursor.fetchall()
            
            # If we don't have enough topic-specific sources, get high-quality sources
            if len(topic_sources) < limit:
                remaining = limit - len(topic_sources)
                
                # Get domains we already have to avoid duplicates
                existing_domains = [s[2] for s in topic_sources]
                
                # Get additional high-quality general sources
                cursor.execute('''
                SELECT url, title, domain, quality_score, category, has_rss, rss_url, NULL as relevance_score
                FROM sources 
                WHERE domain NOT IN ({}) AND quality_score >= ?
                ORDER BY quality_score DESC, times_used DESC
                LIMIT ?
                '''.format(','.join(['?'] * len(existing_domains))), 
                (*existing_domains, min_quality, remaining))
                
                additional_sources = cursor.fetchall()
                topic_sources.extend(additional_sources)
            
            # Format the results
            results = []
            for source in topic_sources:
                results.append({
                    'url': source[0],
                    'title': source[1],
                    'domain': source[2],
                    'quality_score': source[3],
                    'category': source[4],
                    'has_rss': bool(source[5]),
                    'rss_url': source[6],
                    'relevance_score': source[7] if source[7] is not None else 0.0
                })
            
            conn.close()
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
            
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Get current quality score
            cursor.execute("SELECT id, quality_score FROM sources WHERE domain = ?", (domain,))
            result = cursor.fetchone()
            
            if not result:
                logger.warning(f"Cannot update quality for unknown source: {domain}")
                conn.close()
                return False
            
            source_id, current_score = result
            
            # Update the quality score, keeping it within 0-10 range
            new_score = max(0, min(10, current_score + quality_delta))
            
            cursor.execute('''
            UPDATE sources SET quality_score = ? WHERE id = ?
            ''', (new_score, source_id))
            
            conn.commit()
            conn.close()
            
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
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            query = '''
            SELECT url, title, domain, quality_score, category, has_rss, rss_url, times_used 
            FROM sources
            '''
            
            params = []
            if category:
                query += " WHERE category = ?"
                params.append(category)
            
            query += " ORDER BY times_used DESC, quality_score DESC LIMIT ?"
            params.append(limit)
            
            cursor.execute(query, params)
            
            results = []
            for source in cursor.fetchall():
                results.append({
                    'url': source[0],
                    'title': source[1],
                    'domain': source[2],
                    'quality_score': source[3],
                    'category': source[4],
                    'has_rss': bool(source[5]),
                    'rss_url': source[6],
                    'times_used': source[7]
                })
            
            conn.close()
            return results
            
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

    def research_topic(self, topic, num_sources=5):
        """
        Research a specific topic by searching for and analyzing relevant content.
        Uses SourceTracker to dynamically improve source selection over time.
        
        Args:
            topic (str): The topic to research
            num_sources (int): Number of sources to include in the research
            
        Returns:
            dict: A dictionary containing research results
        """
        try:
            logger.info(f"Researching topic: {topic}")
            
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
    
    def get_trending_topics(self, category=None, limit=10):
        """
        Get trending topics based on recent web content.
        Uses source tracker to get most popular sources if available.
        
        Args:
            category (str): Optional category to filter topics by
            limit (int): Maximum number of topics to return
            
        Returns:
            list: A list of trending topics with their scores
        """
        try:
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


# Create a singleton instance
web_scraper_service = WebScraperService()