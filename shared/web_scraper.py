"""
Web scraping utilities for content generation
This module provides functions for scraping content from various sources
including websites, RSS feeds, and social media platforms.
"""

import logging
import os
import json
import re
from urllib.parse import urlparse
import trafilatura
import newspaper
from newspaper import Article
import feedparser
from bs4 import BeautifulSoup
import requests
from textblob import TextBlob

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class WebScraper:
    """Provides methods for extracting content from websites, RSS feeds, and other sources"""
    
    def __init__(self, user_agent=None):
        """
        Initialize the WebScraper with configurable user agent
        
        Args:
            user_agent (str, optional): Custom user agent for HTTP requests
        """
        self.user_agent = user_agent or 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        self.session = requests.Session()
        self.session.headers.update({'User-Agent': self.user_agent})
    
    def extract_text_content(self, url):
        """
        Extract the main text content from a webpage
        Uses trafilatura for high-quality content extraction
        
        Args:
            url (str): URL of the webpage to scrape
            
        Returns:
            dict: Content details including title, text, metadata
        """
        try:
            # Download the webpage
            downloaded = trafilatura.fetch_url(url)
            if not downloaded:
                logger.warning(f"Failed to download content from {url}")
                return None
            
            # Extract the main content
            result = trafilatura.extract(downloaded, output_format='json', with_metadata=True)
            if not result:
                logger.warning(f"Failed to extract content from {url}")
                return None
                
            # Parse the JSON result
            content = json.loads(result)
            
            # Add source URL and domain to metadata
            parsed_url = urlparse(url)
            content['source_url'] = url
            content['domain'] = parsed_url.netloc
            
            return content
            
        except Exception as e:
            logger.error(f"Error extracting content from {url}: {str(e)}")
            return None
    
    def extract_article(self, url):
        """
        Extract article content using newspaper3k
        Includes article parsing, NLP processing, and keyword extraction
        
        Args:
            url (str): URL of the article to scrape
            
        Returns:
            dict: Article details including title, text, keywords, summary
        """
        try:
            # Create an Article object
            article = Article(url)
            
            # Download and parse the article
            article.download()
            article.parse()
            
            # Perform NLP processing
            article.nlp()
            
            # Create sentiment analysis of text
            sentiment = TextBlob(article.text)
            
            # Return article details
            return {
                'title': article.title,
                'authors': article.authors,
                'publish_date': article.publish_date,
                'text': article.text,
                'summary': article.summary,
                'keywords': article.keywords,
                'top_image': article.top_image,
                'images': list(article.images),
                'source_url': url,
                'sentiment': {
                    'polarity': sentiment.sentiment.polarity,
                    'subjectivity': sentiment.sentiment.subjectivity
                }
            }
            
        except Exception as e:
            logger.error(f"Error extracting article from {url}: {str(e)}")
            return None
    
    def parse_rss_feed(self, feed_url, max_entries=10):
        """
        Parse an RSS feed and extract articles
        
        Args:
            feed_url (str): URL of the RSS feed
            max_entries (int, optional): Maximum number of entries to return
            
        Returns:
            list: List of feed entries with metadata
        """
        try:
            # Parse the feed
            feed = feedparser.parse(feed_url)
            
            if not feed.entries:
                logger.warning(f"No entries found in feed: {feed_url}")
                return []
            
            # Process entries
            results = []
            for entry in feed.entries[:max_entries]:
                # Extract key information
                item = {
                    'title': entry.get('title', ''),
                    'link': entry.get('link', ''),
                    'published': entry.get('published', ''),
                    'summary': entry.get('summary', '')
                }
                
                # Clean HTML from summary if present
                if item['summary']:
                    soup = BeautifulSoup(item['summary'], 'html.parser')
                    item['summary_text'] = soup.get_text()
                
                # Add to results
                results.append(item)
            
            return results
            
        except Exception as e:
            logger.error(f"Error parsing RSS feed {feed_url}: {str(e)}")
            return []
    
    def search_related_articles(self, query, num_results=5):
        """
        Search for articles related to a query using Google News
        Requires newspaper3k
        
        Args:
            query (str): Search query
            num_results (int, optional): Maximum number of results to return
            
        Returns:
            list: List of related article URLs
        """
        try:
            # Build a news source
            paper = newspaper.build(f'https://news.google.com/search?q={query}', memoize_articles=False)
            
            # Get article URLs
            articles = []
            for article in paper.articles[:num_results]:
                articles.append(article.url)
                
            return articles
            
        except Exception as e:
            logger.error(f"Error searching for related articles: {str(e)}")
            return []
    
    def extract_keywords(self, text, num_keywords=10):
        """
        Extract keywords from text using TextBlob
        
        Args:
            text (str): Text to analyze
            num_keywords (int, optional): Maximum number of keywords to return
            
        Returns:
            list: List of keywords with scores
        """
        try:
            # Create TextBlob
            blob = TextBlob(text)
            
            # Extract noun phrases as keywords
            keywords = []
            for phrase in blob.noun_phrases:
                if len(phrase.split()) <= 3:  # Limit to phrases with 3 or fewer words
                    keywords.append(phrase)
            
            # Count occurrences of each keyword
            keyword_counts = {}
            for keyword in keywords:
                if keyword in keyword_counts:
                    keyword_counts[keyword] += 1
                else:
                    keyword_counts[keyword] = 1
            
            # Sort by frequency
            sorted_keywords = sorted(keyword_counts.items(), key=lambda x: x[1], reverse=True)
            
            # Return top N keywords
            return sorted_keywords[:num_keywords]
            
        except Exception as e:
            logger.error(f"Error extracting keywords: {str(e)}")
            return []

    def analyze_sentiment(self, text):
        """
        Analyze sentiment of text using TextBlob
        
        Args:
            text (str): Text to analyze
            
        Returns:
            dict: Sentiment analysis results
        """
        try:
            # Create TextBlob
            blob = TextBlob(text)
            
            # Get sentiment
            sentiment = blob.sentiment
            
            # Determine sentiment category
            if sentiment.polarity > 0.3:
                category = 'positive'
            elif sentiment.polarity < -0.3:
                category = 'negative'
            else:
                category = 'neutral'
                
            return {
                'polarity': sentiment.polarity,
                'subjectivity': sentiment.subjectivity,
                'category': category
            }
            
        except Exception as e:
            logger.error(f"Error analyzing sentiment: {str(e)}")
            return None

def get_website_text_content(url):
    """
    Simple utility function to get text content from a website
    
    Args:
        url (str): URL to scrape
        
    Returns:
        str: Extracted text content
    """
    scraper = WebScraper()
    content = scraper.extract_text_content(url)
    return content.get('text', '') if content else ''

def parse_rss(feed_url):
    """
    Simple utility function to parse an RSS feed
    
    Args:
        feed_url (str): URL of the RSS feed
        
    Returns:
        list: Feed entries
    """
    scraper = WebScraper()
    return scraper.parse_rss_feed(feed_url)