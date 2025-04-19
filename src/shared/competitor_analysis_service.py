"""
Competitor Analysis Service for the blog automation platform.
This service provides functionality for analyzing competitor blogs and content,
which is useful for research, SEO optimization, and content strategy.
"""

import logging
import re
import json
import os
import time
from urllib.parse import urlparse
from datetime import datetime, timedelta
from collections import Counter, defaultdict
import sqlite3
import hashlib
import math

# Web scraping and content extraction
import requests
from bs4 import BeautifulSoup
import trafilatura
from newspaper import Article, Source, ArticleException
import feedparser

# Text analysis and processing
from textblob import TextBlob
import nltk
from nltk.tokenize import sent_tokenize, word_tokenize
from nltk.corpus import stopwords
from nltk.util import ngrams

# Import for data visualization
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


class CompetitorAnalysisService:
    """
    Service for analyzing competitor blogs and content.
    Provides methods to track competitors, analyze their content and SEO strategies,
    and generate insights for content optimization.
    """
    
    def __init__(self, db_path=None):
        """
        Initialize the competitor analysis service.
        
        Args:
            db_path (str, optional): Path to the SQLite database file for storing competitor data.
                Defaults to 'data/competitor_analysis.db'.
        """
        self.logger = logging.getLogger('CompetitorAnalysisService')
        
        # Set database path
        if db_path is None:
            self.db_path = os.path.join('data', 'competitor_analysis.db')
        else:
            self.db_path = db_path
            
        # Ensure database directory exists
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
            
        # Initialize database
        self._init_database()
        
        # Set up request session for better performance
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/96.0.4664.110 Safari/537.36',
        })
        
        # Load stopwords
        self.stop_words = set(stopwords.words('english'))
    
    def _init_database(self):
        """Initialize the SQLite database with necessary tables."""
        try:
            # Connect to database
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Create tables if they don't exist
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS competitors (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    blog_id TEXT,
                    name TEXT NOT NULL,
                    url TEXT NOT NULL UNIQUE,
                    description TEXT,
                    category TEXT,
                    priority INTEGER DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_analyzed TIMESTAMP
                )
            ''')
            
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS competitor_content (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    competitor_id INTEGER,
                    title TEXT NOT NULL,
                    url TEXT NOT NULL UNIQUE,
                    content TEXT,
                    excerpt TEXT,
                    published_date TIMESTAMP,
                    word_count INTEGER,
                    analyzed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (competitor_id) REFERENCES competitors (id) ON DELETE CASCADE
                )
            ''')
            
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS competitor_keywords (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    competitor_id INTEGER,
                    content_id INTEGER,
                    keyword TEXT NOT NULL,
                    frequency INTEGER,
                    analyzed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (competitor_id) REFERENCES competitors (id) ON DELETE CASCADE,
                    FOREIGN KEY (content_id) REFERENCES competitor_content (id) ON DELETE CASCADE
                )
            ''')
            
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS competitor_seo (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    content_id INTEGER,
                    meta_title TEXT,
                    meta_description TEXT,
                    h1_tags TEXT,
                    h2_tags TEXT,
                    backlinks INTEGER DEFAULT 0,
                    analyzed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (content_id) REFERENCES competitor_content (id) ON DELETE CASCADE
                )
            ''')
            
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS competitor_topics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    competitor_id INTEGER,
                    topic TEXT NOT NULL,
                    frequency INTEGER,
                    last_post_date TIMESTAMP,
                    analyzed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (competitor_id) REFERENCES competitors (id) ON DELETE CASCADE
                )
            ''')
            
            # Create indexes for faster querying
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_competitor_blog_id ON competitors (blog_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_competitor_content_competitor_id ON competitor_content (competitor_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_competitor_keywords_content_id ON competitor_keywords (content_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_competitor_keywords_competitor_id ON competitor_keywords (competitor_id)')
            
            # Commit changes
            conn.commit()
        except Exception as e:
            self.logger.error(f"Error initializing database: {str(e)}")
            raise
        finally:
            # Close connection
            if conn:
                conn.close()
    
    def add_competitor(self, url, name=None, description=None, category=None, blog_id=None, priority=1):
        """
        Add a new competitor to track.
        
        Args:
            url (str): URL of the competitor's website or blog
            name (str, optional): Name of the competitor. If None, will attempt to extract from the website.
            description (str, optional): Description of the competitor.
            category (str, optional): Category or industry of the competitor.
            blog_id (str, optional): ID of the blog this competitor is associated with.
            priority (int, optional): Priority level (1-5, with 1 being highest). Defaults to 1.
            
        Returns:
            dict: The added competitor information.
        """
        try:
            # Normalize URL
            parsed_url = urlparse(url)
            if not parsed_url.scheme:
                url = f"https://{url}"
            
            # Extract name from website if not provided
            if name is None:
                try:
                    response = self.session.get(url, timeout=10)
                    if response.status_code == 200:
                        soup = BeautifulSoup(response.text, 'html.parser')
                        name = soup.title.string.strip() if soup.title else urlparse(url).netloc
                    else:
                        name = urlparse(url).netloc
                except Exception as e:
                    self.logger.warning(f"Could not extract name from website: {str(e)}")
                    name = urlparse(url).netloc
            
            # Connect to database
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Check if competitor already exists
            cursor.execute('SELECT id FROM competitors WHERE url = ?', (url,))
            existing = cursor.fetchone()
            
            if existing:
                # Update existing competitor
                cursor.execute('''
                    UPDATE competitors 
                    SET name = ?, description = ?, category = ?, blog_id = ?, priority = ?
                    WHERE url = ?
                ''', (name, description, category, blog_id, priority, url))
                competitor_id = existing[0]
                message = "Competitor updated successfully"
            else:
                # Insert new competitor
                cursor.execute('''
                    INSERT INTO competitors (name, url, description, category, blog_id, priority)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (name, url, description, category, blog_id, priority))
                competitor_id = cursor.lastrowid
                message = "Competitor added successfully"
            
            # Commit changes
            conn.commit()
            
            # Get the added/updated competitor
            cursor.execute('SELECT * FROM competitors WHERE id = ?', (competitor_id,))
            competitor = cursor.fetchone()
            
            # Convert to dictionary
            competitor_dict = {
                'id': competitor[0],
                'blog_id': competitor[1],
                'name': competitor[2],
                'url': competitor[3],
                'description': competitor[4],
                'category': competitor[5],
                'priority': competitor[6],
                'created_at': competitor[7],
                'last_analyzed': competitor[8]
            }
            
            return {
                'success': True,
                'message': message,
                'competitor': competitor_dict
            }
        
        except Exception as e:
            self.logger.error(f"Error adding competitor: {str(e)}")
            return {
                'success': False,
                'message': f"Error adding competitor: {str(e)}"
            }
        finally:
            # Close connection
            if conn:
                conn.close()
    
    def get_competitors(self, blog_id=None):
        """
        Get list of tracked competitors.
        
        Args:
            blog_id (str, optional): Filter competitors by blog ID.
            
        Returns:
            list: List of competitor dictionaries.
        """
        try:
            # Connect to database
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Get competitors
            if blog_id:
                cursor.execute('SELECT * FROM competitors WHERE blog_id = ? ORDER BY priority, name', (blog_id,))
            else:
                cursor.execute('SELECT * FROM competitors ORDER BY priority, name')
            
            competitors = cursor.fetchall()
            
            # Convert to list of dictionaries
            competitors_list = []
            for competitor in competitors:
                competitors_list.append({
                    'id': competitor[0],
                    'blog_id': competitor[1],
                    'name': competitor[2],
                    'url': competitor[3],
                    'description': competitor[4],
                    'category': competitor[5],
                    'priority': competitor[6],
                    'created_at': competitor[7],
                    'last_analyzed': competitor[8]
                })
            
            return competitors_list
        
        except Exception as e:
            self.logger.error(f"Error getting competitors: {str(e)}")
            return []
        finally:
            # Close connection
            if conn:
                conn.close()
    
    def delete_competitor(self, competitor_id):
        """
        Delete a competitor from tracking.
        
        Args:
            competitor_id (int): ID of the competitor to delete.
            
        Returns:
            dict: Result of the operation.
        """
        try:
            # Connect to database
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Check if competitor exists
            cursor.execute('SELECT id FROM competitors WHERE id = ?', (competitor_id,))
            existing = cursor.fetchone()
            
            if not existing:
                return {
                    'success': False,
                    'message': f"Competitor with ID {competitor_id} not found"
                }
            
            # Delete competitor (cascade will delete related data)
            cursor.execute('DELETE FROM competitors WHERE id = ?', (competitor_id,))
            
            # Commit changes
            conn.commit()
            
            return {
                'success': True,
                'message': f"Competitor deleted successfully"
            }
        
        except Exception as e:
            self.logger.error(f"Error deleting competitor: {str(e)}")
            return {
                'success': False,
                'message': f"Error deleting competitor: {str(e)}"
            }
        finally:
            # Close connection
            if conn:
                conn.close()
    
    def analyze_competitor(self, competitor_id, max_articles=10):
        """
        Analyze a competitor's website and content.
        
        Args:
            competitor_id (int): ID of the competitor to analyze.
            max_articles (int, optional): Maximum number of articles to analyze. Defaults to 10.
            
        Returns:
            dict: Analysis results.
        """
        try:
            # Connect to database
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Get competitor information
            cursor.execute('SELECT id, name, url FROM competitors WHERE id = ?', (competitor_id,))
            competitor = cursor.fetchone()
            
            if not competitor:
                return {
                    'success': False,
                    'message': f"Competitor with ID {competitor_id} not found"
                }
            
            competitor_id, competitor_name, competitor_url = competitor
            
            # Extract articles from competitor website
            articles = self._extract_articles(competitor_url, max_articles)
            
            # Process each article
            processed_articles = []
            top_keywords = Counter()
            topics = Counter()
            
            for article in articles:
                try:
                    # Add article to database if it doesn't exist
                    cursor.execute('SELECT id FROM competitor_content WHERE url = ?', (article['url'],))
                    existing = cursor.fetchone()
                    
                    if existing:
                        content_id = existing[0]
                    else:
                        cursor.execute('''
                            INSERT INTO competitor_content 
                            (competitor_id, title, url, content, excerpt, published_date, word_count)
                            VALUES (?, ?, ?, ?, ?, ?, ?)
                        ''', (
                            competitor_id, 
                            article['title'], 
                            article['url'],
                            article['content'],
                            article['excerpt'],
                            article.get('published_date'),
                            article['word_count']
                        ))
                        content_id = cursor.lastrowid
                    
                    # Extract and store SEO data
                    if 'seo' in article:
                        cursor.execute('SELECT id FROM competitor_seo WHERE content_id = ?', (content_id,))
                        existing_seo = cursor.fetchone()
                        
                        if existing_seo:
                            cursor.execute('''
                                UPDATE competitor_seo
                                SET meta_title = ?, meta_description = ?, h1_tags = ?, h2_tags = ?, analyzed_at = CURRENT_TIMESTAMP
                                WHERE content_id = ?
                            ''', (
                                article['seo'].get('meta_title'),
                                article['seo'].get('meta_description'),
                                json.dumps(article['seo'].get('h1_tags', [])),
                                json.dumps(article['seo'].get('h2_tags', [])),
                                content_id
                            ))
                        else:
                            cursor.execute('''
                                INSERT INTO competitor_seo
                                (content_id, meta_title, meta_description, h1_tags, h2_tags)
                                VALUES (?, ?, ?, ?, ?)
                            ''', (
                                content_id,
                                article['seo'].get('meta_title'),
                                article['seo'].get('meta_description'),
                                json.dumps(article['seo'].get('h1_tags', [])),
                                json.dumps(article['seo'].get('h2_tags', []))
                            ))
                    
                    # Extract and store keywords
                    if 'keywords' in article:
                        # Delete existing keywords for this content
                        cursor.execute('DELETE FROM competitor_keywords WHERE content_id = ?', (content_id,))
                        
                        # Add new keywords
                        for keyword, frequency in article['keywords'].items():
                            cursor.execute('''
                                INSERT INTO competitor_keywords
                                (competitor_id, content_id, keyword, frequency)
                                VALUES (?, ?, ?, ?)
                            ''', (competitor_id, content_id, keyword, frequency))
                            
                            # Add to top keywords counter
                            top_keywords[keyword] += frequency
                    
                    # Analyze topics
                    if 'topics' in article:
                        for topic in article['topics']:
                            topics[topic] += 1
                    
                    # Add processed article to the list
                    processed_articles.append({
                        'id': content_id,
                        'title': article['title'],
                        'url': article['url'],
                        'excerpt': article['excerpt'],
                        'word_count': article['word_count'],
                        'published_date': article.get('published_date')
                    })
                
                except Exception as e:
                    self.logger.error(f"Error processing article {article.get('url', 'unknown')}: {str(e)}")
                    continue
            
            # Store topics in the database
            for topic, frequency in topics.items():
                cursor.execute('SELECT id FROM competitor_topics WHERE competitor_id = ? AND topic = ?', 
                              (competitor_id, topic))
                existing_topic = cursor.fetchone()
                
                if existing_topic:
                    cursor.execute('''
                        UPDATE competitor_topics
                        SET frequency = ?, analyzed_at = CURRENT_TIMESTAMP
                        WHERE competitor_id = ? AND topic = ?
                    ''', (frequency, competitor_id, topic))
                else:
                    cursor.execute('''
                        INSERT INTO competitor_topics
                        (competitor_id, topic, frequency)
                        VALUES (?, ?, ?)
                    ''', (competitor_id, topic, frequency))
            
            # Update last analyzed timestamp
            cursor.execute('''
                UPDATE competitors
                SET last_analyzed = CURRENT_TIMESTAMP
                WHERE id = ?
            ''', (competitor_id,))
            
            # Commit changes
            conn.commit()
            
            # Prepare analysis results
            top_keywords_list = [{'keyword': kw, 'frequency': freq} for kw, freq in top_keywords.most_common(20)]
            top_topics_list = [{'topic': topic, 'frequency': freq} for topic, freq in topics.most_common(10)]
            
            return {
                'success': True,
                'message': f"Successfully analyzed {len(processed_articles)} articles from {competitor_name}",
                'competitor': {
                    'id': competitor_id,
                    'name': competitor_name,
                    'url': competitor_url
                },
                'articles': processed_articles,
                'top_keywords': top_keywords_list,
                'top_topics': top_topics_list
            }
        
        except Exception as e:
            self.logger.error(f"Error analyzing competitor: {str(e)}")
            return {
                'success': False,
                'message': f"Error analyzing competitor: {str(e)}"
            }
        finally:
            # Close connection
            if conn:
                conn.close()
    
    def _extract_articles(self, url, max_articles=10):
        """
        Extract articles from a competitor's website.
        
        Args:
            url (str): URL of the competitor's website
            max_articles (int): Maximum number of articles to extract
            
        Returns:
            list: List of article dictionaries
        """
        articles = []
        try:
            # Try to build a source with newspaper3k (better for blogs)
            source = Source(url)
            source.build()
            
            # Get article URLs from the source
            article_urls = list(source.article_urls())[:max_articles]
            
            # If no articles found, try RSS feed
            if not article_urls:
                # Try to find RSS feed
                response = self.session.get(url, timeout=10)
                if response.status_code == 200:
                    soup = BeautifulSoup(response.text, 'html.parser')
                    
                    # Look for RSS link
                    rss_link = None
                    for link in soup.find_all('link', type='application/rss+xml'):
                        rss_link = link.get('href')
                        if rss_link:
                            break
                    
                    # Parse RSS feed
                    if rss_link:
                        if not rss_link.startswith('http'):
                            parsed_url = urlparse(url)
                            base_url = f"{parsed_url.scheme}://{parsed_url.netloc}"
                            rss_link = f"{base_url.rstrip('/')}/{rss_link.lstrip('/')}"
                        
                        feed = feedparser.parse(rss_link)
                        
                        for entry in feed.entries[:max_articles]:
                            article_urls.append(entry.link)
            
            # If still no articles, try parsing links from the homepage
            if not article_urls:
                soup = BeautifulSoup(response.text, 'html.parser')
                
                # Find potential blog links
                blog_links = []
                for link in soup.find_all('a', href=True):
                    href = link['href']
                    
                    # Skip external links, social media links, etc.
                    if href.startswith('#') or 'javascript:' in href:
                        continue
                    
                    # Skip common non-article links
                    if any(skip in href.lower() for skip in ['contact', 'about', 'login', 'signup', 'category', 'tag']):
                        continue
                    
                    # Make sure URL is absolute
                    if not href.startswith('http'):
                        parsed_url = urlparse(url)
                        base_url = f"{parsed_url.scheme}://{parsed_url.netloc}"
                        href = f"{base_url.rstrip('/')}/{href.lstrip('/')}"
                    
                    # Only include links to the same domain
                    if urlparse(href).netloc == urlparse(url).netloc:
                        blog_links.append(href)
                
                # Use unique links as article URLs
                article_urls = list(set(blog_links))[:max_articles]
            
            # Process each article URL
            for article_url in article_urls:
                try:
                    time.sleep(1)  # Rate limiting
                    article = Article(article_url)
                    article.download()
                    article.parse()
                    
                    # Extract additional SEO information
                    seo_data = self._extract_seo_data(article_url)
                    
                    # Extract keywords
                    keywords = self._extract_keywords(article.text)
                    
                    # Extract topics
                    topics = self._extract_topics(article.title, article.text)
                    
                    # Build article data
                    article_data = {
                        'title': article.title,
                        'url': article_url,
                        'content': article.text,
                        'excerpt': article.text[:300] + '...' if len(article.text) > 300 else article.text,
                        'published_date': article.publish_date.isoformat() if article.publish_date else None,
                        'word_count': len(article.text.split()),
                        'seo': seo_data,
                        'keywords': keywords,
                        'topics': topics
                    }
                    
                    articles.append(article_data)
                
                except Exception as e:
                    self.logger.warning(f"Error extracting article from {article_url}: {str(e)}")
                    continue
        
        except Exception as e:
            self.logger.error(f"Error extracting articles from {url}: {str(e)}")
        
        return articles
    
    def _extract_seo_data(self, url):
        """
        Extract SEO data from a URL.
        
        Args:
            url (str): URL to extract SEO data from
            
        Returns:
            dict: SEO data
        """
        seo_data = {
            'meta_title': None,
            'meta_description': None,
            'h1_tags': [],
            'h2_tags': []
        }
        
        try:
            response = self.session.get(url, timeout=10)
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'html.parser')
                
                # Extract meta title
                if soup.title:
                    seo_data['meta_title'] = soup.title.string.strip()
                
                # Extract meta description
                meta_desc = soup.find('meta', attrs={'name': 'description'})
                if meta_desc and 'content' in meta_desc.attrs:
                    seo_data['meta_description'] = meta_desc['content'].strip()
                
                # Extract H1 tags
                for h1 in soup.find_all('h1'):
                    if h1.text.strip():
                        seo_data['h1_tags'].append(h1.text.strip())
                
                # Extract H2 tags
                for h2 in soup.find_all('h2'):
                    if h2.text.strip():
                        seo_data['h2_tags'].append(h2.text.strip())
        
        except Exception as e:
            self.logger.warning(f"Error extracting SEO data from {url}: {str(e)}")
        
        return seo_data
    
    def _extract_keywords(self, text):
        """
        Extract keywords from text.
        
        Args:
            text (str): Text to extract keywords from
            
        Returns:
            dict: Dictionary of keywords and their frequencies
        """
        try:
            # Tokenize text
            words = word_tokenize(text.lower())
            
            # Remove stopwords and punctuation
            words = [word for word in words if word.isalnum() and word not in self.stop_words]
            
            # Get word frequencies
            word_freq = Counter(words)
            
            # Get bigrams (meaningful 2-word phrases)
            bigrams_list = list(ngrams(words, 2))
            bigram_freq = Counter(bigrams_list)
            
            # Combine unigrams and bigrams
            keywords = {}
            
            # Add top unigrams
            for word, freq in word_freq.most_common(30):
                if len(word) > 3:  # Ignore very short words
                    keywords[word] = freq
            
            # Add top bigrams
            for bigram, freq in bigram_freq.most_common(20):
                if freq > 1:  # Only include bigrams that appear more than once
                    keywords[' '.join(bigram)] = freq
            
            return keywords
        
        except Exception as e:
            self.logger.error(f"Error extracting keywords: {str(e)}")
            return {}
    
    def _extract_topics(self, title, content):
        """
        Extract potential topics from an article.
        
        Args:
            title (str): Article title
            content (str): Article content
            
        Returns:
            list: List of potential topics
        """
        topics = []
        try:
            # Extract from title (usually most relevant)
            title_blob = TextBlob(title)
            
            # Extract noun phrases from title
            for phrase in title_blob.noun_phrases:
                if len(phrase.split()) > 1:  # Only multi-word phrases
                    topics.append(phrase)
            
            # If no topics found in title, try H1 and H2 tags in content
            if not topics and content:
                # Approximate H2 tags by looking for lines ending with newlines
                lines = content.split('\n')
                potential_headers = [line.strip() for line in lines if len(line.strip()) > 0 and len(line.strip().split()) < 10]
                
                for header in potential_headers[:5]:  # Only check first few potential headers
                    header_blob = TextBlob(header)
                    for phrase in header_blob.noun_phrases:
                        if len(phrase.split()) > 1:
                            topics.append(phrase)
            
            # If still no topics, use TextBlob to extract main noun phrases from content
            if not topics and content:
                content_sample = content[:1000]  # Use a sample to save processing time
                content_blob = TextBlob(content_sample)
                
                # Get the most common noun phrases
                phrases = list(content_blob.noun_phrases)
                phrase_counter = Counter(phrases)
                
                for phrase, count in phrase_counter.most_common(5):
                    if len(phrase.split()) > 1 and count > 1:
                        topics.append(phrase)
        
        except Exception as e:
            self.logger.error(f"Error extracting topics: {str(e)}")
        
        return list(set(topics))  # Return unique topics
    
    def get_competitor_analysis(self, competitor_id=None, blog_id=None):
        """
        Get competitor analysis results.
        
        Args:
            competitor_id (int, optional): ID of specific competitor to get analysis for.
            blog_id (str, optional): Filter by blog ID.
            
        Returns:
            dict: Competitor analysis results
        """
        try:
            # Connect to database
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row  # Use row factory for dict-like access
            cursor = conn.cursor()
            
            # Get competitors
            if competitor_id:
                cursor.execute('SELECT * FROM competitors WHERE id = ?', (competitor_id,))
            elif blog_id:
                cursor.execute('SELECT * FROM competitors WHERE blog_id = ? ORDER BY priority, name', (blog_id,))
            else:
                cursor.execute('SELECT * FROM competitors ORDER BY priority, name')
            
            competitors_rows = cursor.fetchall()
            
            if not competitors_rows:
                return {
                    'success': False,
                    'message': 'No competitors found with the specified criteria'
                }
            
            # Prepare results
            competitors = []
            for comp in competitors_rows:
                competitor = dict(comp)
                
                # Get latest articles
                cursor.execute('''
                    SELECT id, title, url, excerpt, word_count, published_date
                    FROM competitor_content
                    WHERE competitor_id = ?
                    ORDER BY published_date DESC NULLS LAST
                    LIMIT 10
                ''', (competitor['id'],))
                
                articles = [dict(row) for row in cursor.fetchall()]
                
                # Get top keywords
                cursor.execute('''
                    SELECT keyword, SUM(frequency) as total_frequency
                    FROM competitor_keywords
                    WHERE competitor_id = ?
                    GROUP BY keyword
                    ORDER BY total_frequency DESC
                    LIMIT 20
                ''', (competitor['id'],))
                
                keywords = [dict(row) for row in cursor.fetchall()]
                
                # Get top topics
                cursor.execute('''
                    SELECT topic, frequency
                    FROM competitor_topics
                    WHERE competitor_id = ?
                    ORDER BY frequency DESC
                    LIMIT 10
                ''', (competitor['id'],))
                
                topics = [dict(row) for row in cursor.fetchall()]
                
                # Add to competitors list
                competitor['articles'] = articles
                competitor['top_keywords'] = keywords
                competitor['top_topics'] = topics
                competitors.append(competitor)
            
            # Return analysis results
            if competitor_id:
                return {
                    'success': True,
                    'competitor': competitors[0]
                }
            else:
                return {
                    'success': True,
                    'competitors': competitors
                }
        
        except Exception as e:
            self.logger.error(f"Error getting competitor analysis: {str(e)}")
            return {
                'success': False,
                'message': f"Error getting competitor analysis: {str(e)}"
            }
        finally:
            # Close connection
            if conn:
                conn.close()
    
    def get_competitive_gap_analysis(self, blog_id, topic_list=None):
        """
        Perform gap analysis to identify topics competitors are covering that your blog isn't.
        
        Args:
            blog_id (str): ID of the blog to analyze
            topic_list (list, optional): List of your current blog topics
            
        Returns:
            dict: Gap analysis results
        """
        try:
            # Connect to database
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            # Get competitors for this blog
            cursor.execute('SELECT id FROM competitors WHERE blog_id = ?', (blog_id,))
            competitor_ids = [row['id'] for row in cursor.fetchall()]
            
            if not competitor_ids:
                return {
                    'success': False,
                    'message': f"No competitors found for blog ID {blog_id}"
                }
            
            # Get all topics from competitors
            placeholders = ','.join(['?'] * len(competitor_ids))
            cursor.execute(f'''
                SELECT topic, SUM(frequency) as total_frequency
                FROM competitor_topics
                WHERE competitor_id IN ({placeholders})
                GROUP BY topic
                ORDER BY total_frequency DESC
            ''', competitor_ids)
            
            competitor_topics = [dict(row) for row in cursor.fetchall()]
            
            # Identify gaps (topics not in your blog)
            gaps = []
            if topic_list:
                for topic in competitor_topics:
                    # Check if this topic is not covered in your blog
                    is_gap = True
                    for blog_topic in topic_list:
                        # Simple substring matching (can be improved with semantic similarity)
                        if (topic['topic'] in blog_topic.lower() or 
                            blog_topic.lower() in topic['topic']):
                            is_gap = False
                            break
                    
                    if is_gap:
                        gaps.append(topic)
            else:
                # If no topic list provided, return all competitor topics as potential gaps
                gaps = competitor_topics
            
            # Get competitor keywords for gap analysis
            cursor.execute(f'''
                SELECT keyword, SUM(frequency) as total_frequency
                FROM competitor_keywords
                WHERE competitor_id IN ({placeholders})
                GROUP BY keyword
                ORDER BY total_frequency DESC
                LIMIT 50
            ''', competitor_ids)
            
            keywords = [dict(row) for row in cursor.fetchall()]
            
            return {
                'success': True,
                'gap_topics': gaps[:20],  # Top 20 gap topics
                'competitor_keywords': keywords
            }
        
        except Exception as e:
            self.logger.error(f"Error performing gap analysis: {str(e)}")
            return {
                'success': False,
                'message': f"Error performing gap analysis: {str(e)}"
            }
        finally:
            # Close connection
            if conn:
                conn.close()
    
    def get_content_recommendations(self, blog_id, theme=None, topic=None):
        """
        Get content recommendations based on competitor analysis.
        
        Args:
            blog_id (str): ID of the blog
            theme (str, optional): Blog theme
            topic (str, optional): Specific topic to get recommendations for
            
        Returns:
            dict: Content recommendations
        """
        try:
            # Connect to database
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            # Get competitors for this blog
            cursor.execute('SELECT id FROM competitors WHERE blog_id = ?', (blog_id,))
            competitor_ids = [row['id'] for row in cursor.fetchall()]
            
            if not competitor_ids:
                return {
                    'success': False,
                    'message': f"No competitors found for blog ID {blog_id}"
                }
            
            # Prepare recommendations
            recommendations = {
                'keyword_recommendations': [],
                'content_structure': [],
                'topic_ideas': []
            }
            
            # Get keyword recommendations
            placeholders = ','.join(['?'] * len(competitor_ids))
            
            # If a specific topic is provided, get related keywords
            if topic:
                cursor.execute(f'''
                    SELECT cc.title, cc.url, ck.keyword, ck.frequency
                    FROM competitor_keywords ck
                    JOIN competitor_content cc ON ck.content_id = cc.id
                    WHERE ck.competitor_id IN ({placeholders})
                    AND (cc.title LIKE ? OR ck.keyword LIKE ?)
                    ORDER BY ck.frequency DESC
                    LIMIT 30
                ''', competitor_ids + [f'%{topic}%', f'%{topic}%'])
                
                keyword_rows = cursor.fetchall()
                
                # Aggregate keywords
                keyword_freq = Counter()
                related_content = {}
                
                for row in keyword_rows:
                    keyword_freq[row['keyword']] += row['frequency']
                    
                    if row['keyword'] not in related_content:
                        related_content[row['keyword']] = []
                    
                    if len(related_content[row['keyword']]) < 3:  # Limit to 3 examples per keyword
                        related_content[row['keyword']].append({
                            'title': row['title'],
                            'url': row['url']
                        })
                
                # Format keyword recommendations
                for keyword, freq in keyword_freq.most_common(15):
                    recommendations['keyword_recommendations'].append({
                        'keyword': keyword,
                        'frequency': freq,
                        'examples': related_content.get(keyword, [])
                    })
                
                # Get content structure (H tags) for similar content
                cursor.execute(f'''
                    SELECT cs.h1_tags, cs.h2_tags, cc.title, cc.url
                    FROM competitor_seo cs
                    JOIN competitor_content cc ON cs.content_id = cc.id
                    WHERE cc.competitor_id IN ({placeholders})
                    AND cc.title LIKE ?
                    LIMIT 10
                ''', competitor_ids + [f'%{topic}%'])
                
                structure_rows = cursor.fetchall()
                
                for row in structure_rows:
                    try:
                        h1_tags = json.loads(row['h1_tags']) if row['h1_tags'] else []
                        h2_tags = json.loads(row['h2_tags']) if row['h2_tags'] else []
                        
                        if h1_tags or h2_tags:
                            recommendations['content_structure'].append({
                                'title': row['title'],
                                'url': row['url'],
                                'h1_tags': h1_tags,
                                'h2_tags': h2_tags
                            })
                    except:
                        continue
            else:
                # Without a specific topic, get top keywords overall
                cursor.execute(f'''
                    SELECT keyword, SUM(frequency) as total_frequency
                    FROM competitor_keywords
                    WHERE competitor_id IN ({placeholders})
                    GROUP BY keyword
                    ORDER BY total_frequency DESC
                    LIMIT 20
                ''', competitor_ids)
                
                for row in cursor.fetchall():
                    recommendations['keyword_recommendations'].append({
                        'keyword': row['keyword'],
                        'frequency': row['total_frequency']
                    })
            
            # Get topic ideas
            cursor.execute(f'''
                SELECT topic, SUM(frequency) as total_frequency
                FROM competitor_topics
                WHERE competitor_id IN ({placeholders})
                GROUP BY topic
                ORDER BY total_frequency DESC
                LIMIT 15
            ''', competitor_ids)
            
            for row in cursor.fetchall():
                recommendations['topic_ideas'].append({
                    'topic': row['topic'],
                    'frequency': row['total_frequency']
                })
            
            return {
                'success': True,
                'recommendations': recommendations
            }
        
        except Exception as e:
            self.logger.error(f"Error getting content recommendations: {str(e)}")
            return {
                'success': False,
                'message': f"Error getting content recommendations: {str(e)}"
            }
        finally:
            # Close connection
            if conn:
                conn.close()
    
    def generate_competitor_report(self, blog_id, format='json'):
        """
        Generate a comprehensive competitor analysis report.
        
        Args:
            blog_id (str): ID of the blog
            format (str, optional): Report format ('json', 'html', or 'markdown')
            
        Returns:
            dict: Report data in the specified format
        """
        try:
            # Get competitor analysis data
            analysis_data = self.get_competitor_analysis(blog_id=blog_id)
            
            if not analysis_data['success']:
                return analysis_data
            
            # Get gap analysis
            gap_analysis = self.get_competitive_gap_analysis(blog_id)
            
            # Prepare report data
            report = {
                'blog_id': blog_id,
                'generated_at': datetime.now().isoformat(),
                'competitors': analysis_data.get('competitors', []),
                'gap_analysis': gap_analysis.get('gap_topics', []),
                'keyword_opportunities': gap_analysis.get('competitor_keywords', [])
            }
            
            # Format report based on requested format
            if format == 'json':
                return {
                    'success': True,
                    'format': 'json',
                    'report': report
                }
            elif format == 'html':
                # Basic HTML formatting for the report
                html = self._generate_html_report(report)
                return {
                    'success': True,
                    'format': 'html',
                    'report': html
                }
            elif format == 'markdown':
                # Markdown formatting for the report
                markdown = self._generate_markdown_report(report)
                return {
                    'success': True,
                    'format': 'markdown',
                    'report': markdown
                }
            else:
                return {
                    'success': False,
                    'message': f"Unsupported format: {format}"
                }
        
        except Exception as e:
            self.logger.error(f"Error generating competitor report: {str(e)}")
            return {
                'success': False,
                'message': f"Error generating competitor report: {str(e)}"
            }
    
    def _generate_html_report(self, report_data):
        """Generate HTML version of the competitor report."""
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Competitor Analysis Report</title>
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; margin: 0; padding: 20px; color: #333; }}
                h1, h2, h3 {{ color: #2c3e50; }}
                table {{ border-collapse: collapse; width: 100%; margin-bottom: 20px; }}
                th, td {{ padding: 12px 15px; text-align: left; border-bottom: 1px solid #ddd; }}
                th {{ background-color: #f8f9fa; }}
                .competitor {{ margin-bottom: 30px; border: 1px solid #eee; padding: 20px; border-radius: 5px; }}
                .section {{ margin-bottom: 25px; }}
                .keyword-tag {{ display: inline-block; background: #e9ecef; padding: 5px 10px; margin: 5px; border-radius: 3px; }}
            </style>
        </head>
        <body>
            <h1>Competitor Analysis Report</h1>
            <p>Generated on: {report_data['generated_at']}</p>
            
            <div class="section">
                <h2>Competitive Gap Analysis</h2>
                <p>Topics your competitors are covering that you might be missing:</p>
                <div>
        """
        
        # Add gap topics
        for topic in report_data['gap_analysis']:
            html += f'<span class="keyword-tag">{topic["topic"]} ({topic["total_frequency"]})</span>'
        
        html += """
                </div>
            </div>
            
            <div class="section">
                <h2>Keyword Opportunities</h2>
                <table>
                    <thead>
                        <tr>
                            <th>Keyword</th>
                            <th>Frequency</th>
                        </tr>
                    </thead>
                    <tbody>
        """
        
        # Add keyword opportunities
        for keyword in report_data['keyword_opportunities'][:20]:
            html += f"""
                <tr>
                    <td>{keyword['keyword']}</td>
                    <td>{keyword['total_frequency']}</td>
                </tr>
            """
        
        html += """
                    </tbody>
                </table>
            </div>
            
            <h2>Competitor Analysis</h2>
        """
        
        # Add each competitor
        for competitor in report_data['competitors']:
            html += f"""
            <div class="competitor">
                <h3>{competitor['name']}</h3>
                <p>URL: <a href="{competitor['url']}" target="_blank">{competitor['url']}</a></p>
                
                <div class="section">
                    <h4>Top Keywords</h4>
                    <div>
            """
            
            # Add top keywords
            for keyword in competitor.get('top_keywords', []):
                html += f'<span class="keyword-tag">{keyword["keyword"]} ({keyword["total_frequency"]})</span>'
            
            html += """
                    </div>
                </div>
                
                <div class="section">
                    <h4>Top Topics</h4>
                    <div>
            """
            
            # Add top topics
            for topic in competitor.get('top_topics', []):
                html += f'<span class="keyword-tag">{topic["topic"]} ({topic["frequency"]})</span>'
            
            html += """
                    </div>
                </div>
                
                <div class="section">
                    <h4>Recent Content</h4>
                    <table>
                        <thead>
                            <tr>
                                <th>Title</th>
                                <th>Word Count</th>
                                <th>Published Date</th>
                            </tr>
                        </thead>
                        <tbody>
            """
            
            # Add recent articles
            for article in competitor.get('articles', []):
                published_date = article.get('published_date', 'Unknown')
                html += f"""
                    <tr>
                        <td><a href="{article['url']}" target="_blank">{article['title']}</a></td>
                        <td>{article['word_count']}</td>
                        <td>{published_date}</td>
                    </tr>
                """
            
            html += """
                        </tbody>
                    </table>
                </div>
            </div>
            """
        
        html += """
        </body>
        </html>
        """
        
        return html
    
    def _generate_markdown_report(self, report_data):
        """Generate Markdown version of the competitor report."""
        markdown = f"""# Competitor Analysis Report

Generated on: {report_data['generated_at']}

## Competitive Gap Analysis

Topics your competitors are covering that you might be missing:

"""
        
        # Add gap topics
        for topic in report_data['gap_analysis']:
            markdown += f"- **{topic['topic']}** ({topic['total_frequency']})\n"
        
        markdown += "\n## Keyword Opportunities\n\n"
        markdown += "| Keyword | Frequency |\n|---------|----------|\n"
        
        # Add keyword opportunities
        for keyword in report_data['keyword_opportunities'][:20]:
            markdown += f"| {keyword['keyword']} | {keyword['total_frequency']} |\n"
        
        markdown += "\n## Competitor Analysis\n"
        
        # Add each competitor
        for competitor in report_data['competitors']:
            markdown += f"""
### {competitor['name']}

URL: [{competitor['url']}]({competitor['url']})

#### Top Keywords

"""
            # Add top keywords
            for keyword in competitor.get('top_keywords', []):
                markdown += f"- {keyword['keyword']} ({keyword['total_frequency']})\n"
            
            markdown += "\n#### Top Topics\n\n"
            
            # Add top topics
            for topic in competitor.get('top_topics', []):
                markdown += f"- {topic['topic']} ({topic['frequency']})\n"
            
            markdown += "\n#### Recent Content\n\n"
            markdown += "| Title | Word Count | Published Date |\n|-------|-----------|---------------|\n"
            
            # Add recent articles
            for article in competitor.get('articles', []):
                published_date = article.get('published_date', 'Unknown')
                markdown += f"| [{article['title']}]({article['url']}) | {article['word_count']} | {published_date} |\n"
            
            markdown += "\n"
        
        return markdown