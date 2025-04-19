import os
import json
import logging
import time
import random
from datetime import datetime, timedelta

# Try to import PyTrends but fallback gracefully if not available
try:
    from pytrends.request import TrendReq
except ImportError:
    logging.getLogger('research_service').error("PyTrends not available, using fallback data")
    TrendReq = None

class ResearchService:
    """
    Service for conducting research on trending topics related to a blog theme.
    Uses Google Trends (PyTrends) to identify popular topics for content generation.
    """
    
    def __init__(self):
        self.logger = logging.getLogger('research_service')
        
        # Initialize PyTrends client if available
        self.pytrends = None
        if TrendReq:
            try:
                self.pytrends = TrendReq(hl='en-US', tz=360, timeout=(10, 25))
            except Exception as e:
                self.logger.error(f"Error initializing PyTrends: {str(e)}")
    
    def research_topics(self, theme, target_audience, region='US', timeframe='today 1-m'):
        """
        Research trending topics related to the given theme and target audience.
        
        Args:
            theme (str): The thematic focus of the blog
            target_audience (str): The intended audience for the content
            region (str): The geographic region for trends (default: 'US')
            timeframe (str): The time frame for trends (default: 'today 1-m')
            
        Returns:
            list: A list of trending topics with relevance scores and details
        """
        self.logger.info(f"Researching topics for theme: {theme}, audience: {target_audience}, region: {region}")
        
        # Generate keyword combinations to research
        keywords = self._generate_keywords(theme, target_audience)
        
        results = []
        
        # If PyTrends is not available, generate fallback results
        if not self.pytrends:
            self.logger.warning("PyTrends not available, using fallback data")
            for keyword_set in keywords[:3]:  # Limit to first 3 sets
                for keyword in keyword_set:
                    fallback_result = {
                        'keyword': keyword,
                        'title': self._generate_title_from_keyword(keyword),
                        'trend_score': random.uniform(20, 50),  # Fallback trend score
                        'related_top': [],
                        'related_rising': [],
                        'relevance_to_theme': self._calculate_relevance(keyword, theme),
                        'relevance_to_audience': self._calculate_relevance(keyword, target_audience),
                        'researched_at': datetime.utcnow().isoformat(),
                        'is_fallback': True
                    }
                    results.append(fallback_result)
            return self._process_results(results, theme, target_audience)
        
        # Research each keyword combination with retries if PyTrends is available
        for keyword_set in keywords:
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    # Get interest over time for the keyword set
                    self.pytrends.build_payload(keyword_set, cat=0, timeframe=timeframe, geo=region)
                    interest_over_time = self.pytrends.interest_over_time()
                    
                    # Get related queries for more topic ideas
                    related_queries = self.pytrends.related_queries()
                    
                    # Process the results
                    for keyword in keyword_set:
                        # Skip if no data is available
                        if interest_over_time.empty or keyword not in interest_over_time.columns:
                            continue
                        
                        # Calculate trend score (average interest over the period)
                        trend_score = interest_over_time[keyword].mean()
                        
                        # Get related queries for this keyword
                        related_top = []
                        related_rising = []
                        
                        if keyword in related_queries and related_queries[keyword]:
                            if 'top' in related_queries[keyword] and not related_queries[keyword]['top'].empty:
                                related_top = related_queries[keyword]['top']['query'].tolist()[:5]
                            
                            if 'rising' in related_queries[keyword] and not related_queries[keyword]['rising'].empty:
                                related_rising = related_queries[keyword]['rising']['query'].tolist()[:5]
                        
                        # Create result entry
                        result = {
                            'keyword': keyword,
                            'title': self._generate_title_from_keyword(keyword),
                            'trend_score': float(trend_score),
                            'related_top': related_top,
                            'related_rising': related_rising,
                            'relevance_to_theme': self._calculate_relevance(keyword, theme),
                            'relevance_to_audience': self._calculate_relevance(keyword, target_audience),
                            'researched_at': datetime.utcnow().isoformat()
                        }
                        
                        results.append(result)
                    
                    # Successful research, break the retry loop
                    break
                    
                except Exception as e:
                    self.logger.error(f"Error researching keyword set {keyword_set} (attempt {attempt+1}/{max_retries}): {str(e)}")
                    if attempt < max_retries - 1:
                        time.sleep(2 ** attempt)  # Exponential backoff
                    else:
                        # If all retries fail, add a fallback result
                        for keyword in keyword_set:
                            fallback_result = {
                                'keyword': keyword,
                                'title': self._generate_title_from_keyword(keyword),
                                'trend_score': random.uniform(20, 50),  # Fallback trend score
                                'related_top': [],
                                'related_rising': [],
                                'relevance_to_theme': self._calculate_relevance(keyword, theme),
                                'relevance_to_audience': self._calculate_relevance(keyword, target_audience),
                                'researched_at': datetime.utcnow().isoformat(),
                                'is_fallback': True
                            }
                            results.append(fallback_result)
            
            # Wait between keyword sets to avoid rate limiting
            time.sleep(1)
        
        return self._process_results(results, theme, target_audience)
    
    def _process_results(self, results, theme, target_audience):
        """Process and sort research results"""
        # If no results, return empty list
        if not results:
            return []
            
        # Sort results by combined score (trend score + relevance)
        for result in results:
            result['combined_score'] = (
                result['trend_score'] * 0.4 + 
                result['relevance_to_theme'] * 0.3 + 
                result['relevance_to_audience'] * 0.3
            )
        
        results.sort(key=lambda x: x['combined_score'], reverse=True)
        
        # Take top results
        top_results = results[:10]
        
        self.logger.info(f"Research completed. Found {len(top_results)} potential topics.")
        return top_results
    
    def select_best_topic(self, research_results, previous_topics=None):
        """
        Select the best topic from research results, avoiding previous topics.
        
        Args:
            research_results (list): List of research results with topic details
            previous_topics (list): List of previously used topics to avoid
            
        Returns:
            dict: The selected topic details
        """
        if not research_results:
            # Fallback topic if no research results are available
            return {
                'keyword': 'current trends',
                'title': 'Current Trends in the Industry: What You Need to Know',
                'trend_score': 50,
                'combined_score': 50,
                'is_fallback': True
            }
        
        # Filter out previously used topics if provided
        if previous_topics:
            filtered_results = [r for r in research_results if r['title'] not in previous_topics]
            
            # If all topics have been used before, use the original list
            if not filtered_results:
                filtered_results = research_results
        else:
            filtered_results = research_results
        
        # Select the top-scoring topic
        return filtered_results[0]
    
    def _generate_keywords(self, theme, target_audience):
        """Generate keyword combinations to research based on theme and audience"""
        # Extract main theme keywords
        theme_keywords = [theme.lower()]
        
        # Add variations
        if ' ' in theme:
            theme_keywords.extend(theme.lower().split())
        
        # Extract audience keywords
        audience_keywords = [target_audience.lower()]
        
        # Add variations
        if ' ' in target_audience:
            audience_parts = target_audience.lower().split()
            audience_keywords.extend(audience_parts)
        
        # Generate combinations
        combinations = []
        
        # Theme-only combinations
        combinations.append(theme_keywords[:min(len(theme_keywords), 5)])
        
        # Theme + audience combinations
        for t_keyword in theme_keywords[:2]:  # Limit to first 2 theme keywords
            for a_keyword in audience_keywords[:2]:  # Limit to first 2 audience keywords
                combo = [t_keyword, a_keyword]
                
                # Add some common qualifiers
                qualifiers = ['best', 'top', 'how to', 'guide', 'tips']
                for q in qualifiers[:1]:  # Limit to 1 qualifier to stay within limit
                    if len(combo) < 5:  # PyTrends has a limit of 5 keywords
                        combo.append(f"{q} {t_keyword}")
                
                combinations.append(combo[:5])  # Limit to 5 keywords
        
        return combinations
    
    def _calculate_relevance(self, keyword, reference):
        """Calculate simple relevance score between keyword and reference"""
        keyword_lower = keyword.lower()
        reference_lower = reference.lower()
        
        # Direct match
        if keyword_lower == reference_lower:
            return 1.0
        
        # Partial match
        if keyword_lower in reference_lower or reference_lower in keyword_lower:
            return 0.8
        
        # Word-level match
        keyword_words = set(keyword_lower.split())
        reference_words = set(reference_lower.split())
        common_words = keyword_words.intersection(reference_words)
        
        if common_words:
            return 0.5 + (len(common_words) / max(len(keyword_words), len(reference_words)) * 0.5)
        
        # Default low relevance
        return 0.2
    
    def _generate_title_from_keyword(self, keyword):
        """Generate a blog post title from a keyword"""
        # List of title templates
        templates = [
            "The Ultimate Guide to {keyword}",
            "{keyword}: Everything You Need to Know",
            "How to Master {keyword} in {current_year}",
            "Top 10 Strategies for {keyword} Success",
            "{keyword}: Best Practices for Beginners",
            "Why {keyword} Matters More Than Ever",
            "The Future of {keyword}: Trends and Predictions",
            "Essential {keyword} Tips You Can't Ignore",
            "{keyword} 101: A Beginner's Guide",
            "Mastering {keyword}: Expert Advice"
        ]
        
        # Select a random template
        template = random.choice(templates)
        
        # Format with the keyword and current year
        title = template.format(
            keyword=keyword.title(),
            current_year=datetime.utcnow().year
        )
        
        return title