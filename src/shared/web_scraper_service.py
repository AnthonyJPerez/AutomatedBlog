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


class WebScraperService:
    """
    Service for web scraping and content analysis.
    Provides methods for extracting content from websites, blogs, and RSS feeds.
    """

    def __init__(self):
        """Initialize the web scraper service with default settings."""
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
        self.timeout = 10
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
        
        Args:
            topic (str): The topic to research
            num_sources (int): Number of sources to include in the research
            
        Returns:
            dict: A dictionary containing research results
        """
        try:
            logger.info(f"Researching topic: {topic}")
            
            # This would normally use a search API, but we'll simulate it
            # In a production environment, you would use Google Search API, Bing API, etc.
            # For now, let's assume we have a list of relevant URLs to scrape
            
            # Sample URLs that might be returned from a search
            # In production, this would be replaced with actual search results
            search_urls = [
                f"https://en.wikipedia.org/wiki/{topic.replace(' ', '_')}",
                f"https://www.reddit.com/search/?q={topic.replace(' ', '%20')}",
                f"https://medium.com/search?q={topic.replace(' ', '%20')}"
            ]
            
            # Extract content from each URL
            articles = []
            for url in search_urls[:num_sources]:
                content = self.extract_content_from_url(url)
                if content:
                    articles.append(content)
            
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
    
    def get_trending_topics(self, category=None, limit=10):
        """
        Get trending topics based on recent web content.
        In a real implementation, this would use a trending API.
        
        Args:
            category (str): Optional category to filter topics by
            limit (int): Maximum number of topics to return
            
        Returns:
            list: A list of trending topics with their scores
        """
        # In a real implementation, this would use Google Trends, Twitter API, etc.
        # For now, we'll simulate trending topics
        
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
        topics = topics[:limit]
        
        # Add random trending score
        result = []
        for topic in topics:
            result.append({
                "topic": topic,
                "score": round(random.uniform(70, 100), 1),  # Random score between 70-100
                "change": round(random.uniform(-20, 20), 1)  # Random 24h change
            })
            
        # Sort by score
        result.sort(key=lambda x: x["score"], reverse=True)
        
        return result


# Create a singleton instance
web_scraper_service = WebScraperService()