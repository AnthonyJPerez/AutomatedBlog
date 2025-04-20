"""
Analytics Service for tracking blog performance metrics.

This service handles:
1. Storing and retrieving analytics data (traffic, engagement, ad clicks)
2. Generating reports and insights
3. Providing data for content optimization
4. Integration with Google Analytics
5. Integration with WordPress analytics plugins (MonsterInsights, Jetpack)
6. Integration with Google Search Console for SEO data
7. Integration with Google AdSense for ad performance
"""

import datetime
import json
import logging
import os
import time
from collections import defaultdict
from typing import Dict, List, Optional, Tuple, Union, Any

logger = logging.getLogger(__name__)

class AnalyticsService:
    """Service for tracking and analyzing blog performance metrics."""
    
    def __init__(self, storage_service=None):
        """
        Initialize the analytics service.
        
        Args:
            storage_service: Reference to the storage service for data persistence
        """
        self.storage_service = storage_service
        self.ga_integration_enabled = False
        self.adsense_integration_enabled = False
        self.search_console_integration_enabled = False
        self.wordpress_analytics_enabled = False
        
        # Check for Google Analytics credentials
        if os.environ.get("GOOGLE_ANALYTICS_API_KEY"):
            self.ga_integration_enabled = True
            logger.info("Google Analytics integration enabled")
        
        # Check for Google AdSense credentials
        if os.environ.get("GOOGLE_ADSENSE_API_KEY"):
            self.adsense_integration_enabled = True
            logger.info("Google AdSense integration enabled")
        
        # Check for Google Search Console credentials
        if os.environ.get("GOOGLE_SEARCH_CONSOLE_API_KEY"):
            self.search_console_integration_enabled = True
            logger.info("Google Search Console integration enabled")
        
        # Check for WordPress Analytics integration
        if os.environ.get("WORDPRESS_ANALYTICS_ENABLED", "").lower() == "true":
            self.wordpress_analytics_enabled = True
            logger.info("WordPress Analytics integration enabled")
            
        logger.info("Analytics service initialized")
        
    def record_page_view(self, blog_id: str, post_id: str, data: Dict[str, Any]) -> bool:
        """
        Record a page view for a specific blog post.
        
        Args:
            blog_id: ID of the blog
            post_id: ID of the post being viewed
            data: Dictionary with view data including:
                - user_agent: User agent string
                - ip_address: IP address (anonymized)
                - referrer: Referring URL
                - timestamp: View timestamp
                - session_id: Unique session identifier
                
        Returns:
            bool: True if the view was recorded successfully, False otherwise
        """
        try:
            # Get the analytics data file path for this blog
            views_path = self._get_analytics_file_path(blog_id, "views.json")
            
            # Load existing data or create new structure
            if os.path.exists(views_path):
                with open(views_path, 'r') as f:
                    views_data = json.load(f)
            else:
                views_data = {"views": []}
            
            # Add the new view
            view_entry = {
                "post_id": post_id,
                "timestamp": data.get("timestamp", datetime.datetime.now().isoformat()),
                "user_agent": data.get("user_agent", ""),
                "referrer": data.get("referrer", "direct"),
                "session_id": data.get("session_id", ""),
                "country": data.get("country", "unknown"),
                "device_type": data.get("device_type", "unknown")
            }
            
            views_data["views"].append(view_entry)
            
            # Save the updated data
            with open(views_path, 'w') as f:
                json.dump(views_data, f, indent=2)
                
            # Update the aggregate metrics
            self._update_aggregate_metrics(blog_id)
            
            return True
            
        except Exception as e:
            logger.error(f"Error recording page view for blog {blog_id}, post {post_id}: {str(e)}")
            return False
            
    def record_engagement(self, blog_id: str, post_id: str, engagement_type: str, data: Dict[str, Any]) -> bool:
        """
        Record an engagement event for a specific blog post.
        
        Args:
            blog_id: ID of the blog
            post_id: ID of the post 
            engagement_type: Type of engagement (comment, share, like, etc.)
            data: Dictionary with engagement data
                
        Returns:
            bool: True if the engagement was recorded successfully, False otherwise
        """
        try:
            # Get the analytics data file path for this blog
            engagement_path = self._get_analytics_file_path(blog_id, "engagement.json")
            
            # Load existing data or create new structure
            if os.path.exists(engagement_path):
                with open(engagement_path, 'r') as f:
                    engagement_data = json.load(f)
            else:
                engagement_data = {"engagements": []}
            
            # Add the new engagement
            engagement_entry = {
                "post_id": post_id,
                "type": engagement_type,
                "timestamp": data.get("timestamp", datetime.datetime.now().isoformat()),
                "user_id": data.get("user_id", "anonymous"),
                "platform": data.get("platform", "website"),
                "metadata": data.get("metadata", {})
            }
            
            engagement_data["engagements"].append(engagement_entry)
            
            # Save the updated data
            with open(engagement_path, 'w') as f:
                json.dump(engagement_data, f, indent=2)
                
            # Update the aggregate metrics
            self._update_aggregate_metrics(blog_id)
            
            return True
            
        except Exception as e:
            logger.error(f"Error recording engagement for blog {blog_id}, post {post_id}: {str(e)}")
            return False
            
    def record_ad_click(self, blog_id: str, post_id: str, data: Dict[str, Any]) -> bool:
        """
        Record an ad click for a specific blog post.
        
        Args:
            blog_id: ID of the blog
            post_id: ID of the post
            data: Dictionary with ad click data including:
                - ad_id: ID of the ad that was clicked
                - ad_position: Position of the ad on the page
                - ad_network: Ad network (AdSense, etc.)
                - ad_revenue: Revenue generated by the click
                - timestamp: Click timestamp
                - session_id: Unique session identifier
                
        Returns:
            bool: True if the ad click was recorded successfully, False otherwise
        """
        try:
            # Get the analytics data file path for this blog
            ad_clicks_path = self._get_analytics_file_path(blog_id, "ad_clicks.json")
            
            # Load existing data or create new structure
            if os.path.exists(ad_clicks_path):
                with open(ad_clicks_path, 'r') as f:
                    ad_clicks_data = json.load(f)
            else:
                ad_clicks_data = {"ad_clicks": []}
            
            # Add the new ad click
            ad_click_entry = {
                "post_id": post_id,
                "ad_id": data.get("ad_id", ""),
                "ad_position": data.get("ad_position", ""),
                "ad_network": data.get("ad_network", "adsense"),
                "ad_revenue": data.get("ad_revenue", 0.0),
                "timestamp": data.get("timestamp", datetime.datetime.now().isoformat()),
                "session_id": data.get("session_id", ""),
                "device_type": data.get("device_type", "unknown")
            }
            
            ad_clicks_data["ad_clicks"].append(ad_click_entry)
            
            # Save the updated data
            with open(ad_clicks_path, 'w') as f:
                json.dump(ad_clicks_data, f, indent=2)
                
            # Update the aggregate metrics
            self._update_aggregate_metrics(blog_id)
            
            return True
            
        except Exception as e:
            logger.error(f"Error recording ad click for blog {blog_id}, post {post_id}: {str(e)}")
            return False
    
    def get_analytics_summary(self, blog_id: str, period: str = "all") -> Dict[str, Any]:
        """
        Get a summary of analytics for a specific blog.
        
        Args:
            blog_id: ID of the blog
            period: Time period for the summary (day, week, month, year, all)
                
        Returns:
            Dict with summary data
        """
        try:
            # Get the aggregate metrics file
            metrics_path = self._get_analytics_file_path(blog_id, "aggregate_metrics.json")
            
            if not os.path.exists(metrics_path):
                # No metrics available yet
                return {
                    "total_views": 0,
                    "total_engagements": 0,
                    "total_ad_clicks": 0,
                    "estimated_revenue": 0.0,
                    "top_posts": [],
                    "top_referrers": [],
                    "traffic_by_country": {},
                    "traffic_by_device": {},
                    "period": period
                }
            
            with open(metrics_path, 'r') as f:
                metrics = json.load(f)
            
            # Filter by period if needed
            if period != "all":
                # Calculate the cutoff timestamp based on the period
                now = datetime.datetime.now()
                start_date = now.isoformat()  # Default in case none of the conditions match
                
                if period == "day":
                    start_date = (now - datetime.timedelta(days=1)).isoformat()
                elif period == "week":
                    start_date = (now - datetime.timedelta(days=7)).isoformat()
                elif period == "month":
                    start_date = (now - datetime.timedelta(days=30)).isoformat()
                elif period == "year":
                    start_date = (now - datetime.timedelta(days=365)).isoformat()
                
                # Filter metrics for the time period
                # This is simplified - in a real implementation you'd have time-bucketed data
                metrics = self._filter_metrics_by_period(metrics, start_date)
            
            return {
                "total_views": metrics.get("total_views", 0),
                "total_engagements": metrics.get("total_engagements", 0),
                "total_ad_clicks": metrics.get("total_ad_clicks", 0),
                "estimated_revenue": metrics.get("estimated_revenue", 0.0),
                "top_posts": metrics.get("top_posts", [])[:5],
                "top_referrers": metrics.get("top_referrers", [])[:5],
                "traffic_by_country": metrics.get("traffic_by_country", {}),
                "traffic_by_device": metrics.get("traffic_by_device", {}),
                "period": period
            }
            
        except Exception as e:
            logger.error(f"Error getting analytics summary for blog {blog_id}: {str(e)}")
            return {
                "error": str(e),
                "total_views": 0,
                "total_engagements": 0,
                "total_ad_clicks": 0,
                "estimated_revenue": 0.0,
                "period": period
            }
    
    def get_post_analytics(self, blog_id: str, post_id: str) -> Dict[str, Any]:
        """
        Get detailed analytics for a specific post.
        
        Args:
            blog_id: ID of the blog
            post_id: ID of the post
                
        Returns:
            Dict with post analytics data
        """
        try:
            # Get the analytics files
            views_path = self._get_analytics_file_path(blog_id, "views.json")
            engagement_path = self._get_analytics_file_path(blog_id, "engagement.json")
            ad_clicks_path = self._get_analytics_file_path(blog_id, "ad_clicks.json")
            
            # Initialize results
            result = {
                "views": 0,
                "engagements": {
                    "total": 0,
                    "by_type": {}
                },
                "ad_clicks": 0,
                "estimated_revenue": 0.0,
                "view_trend": [],
                "referrers": {},
                "devices": {},
                "countries": {}
            }
            
            # Process views
            if os.path.exists(views_path):
                with open(views_path, 'r') as f:
                    views_data = json.load(f)
                
                post_views = [v for v in views_data.get("views", []) if v.get("post_id") == post_id]
                result["views"] = len(post_views)
                
                # Process view details
                referrers = defaultdict(int)
                devices = defaultdict(int)
                countries = defaultdict(int)
                
                for view in post_views:
                    referrer = view.get("referrer", "direct")
                    referrers[referrer] += 1
                    
                    device = view.get("device_type", "unknown")
                    devices[device] += 1
                    
                    country = view.get("country", "unknown")
                    countries[country] += 1
                
                result["referrers"] = dict(referrers)
                result["devices"] = dict(devices)
                result["countries"] = dict(countries)
            
            # Process engagements
            if os.path.exists(engagement_path):
                with open(engagement_path, 'r') as f:
                    engagement_data = json.load(f)
                
                post_engagements = [e for e in engagement_data.get("engagements", []) if e.get("post_id") == post_id]
                result["engagements"]["total"] = len(post_engagements)
                
                # Count engagements by type
                engagement_types = defaultdict(int)
                for engagement in post_engagements:
                    eng_type = engagement.get("type", "unknown")
                    engagement_types[eng_type] += 1
                
                result["engagements"]["by_type"] = dict(engagement_types)
            
            # Process ad clicks
            if os.path.exists(ad_clicks_path):
                with open(ad_clicks_path, 'r') as f:
                    ad_clicks_data = json.load(f)
                
                post_ad_clicks = [a for a in ad_clicks_data.get("ad_clicks", []) if a.get("post_id") == post_id]
                result["ad_clicks"] = len(post_ad_clicks)
                
                # Calculate estimated revenue
                total_revenue = sum(float(click.get("ad_revenue", 0)) for click in post_ad_clicks)
                result["estimated_revenue"] = total_revenue
            
            return result
            
        except Exception as e:
            logger.error(f"Error getting post analytics for blog {blog_id}, post {post_id}: {str(e)}")
            return {
                "error": str(e),
                "views": 0,
                "engagements": {"total": 0, "by_type": {}},
                "ad_clicks": 0,
                "estimated_revenue": 0.0
            }
    
    def get_topic_performance(self, blog_id: str = None) -> Dict[str, Any]:
        """
        Get performance metrics by topic across all blogs or for a specific blog.
        
        Args:
            blog_id: Optional ID of a specific blog (or None for all blogs)
                
        Returns:
            Dict with topic performance data
        """
        try:
            blog_ids = [blog_id] if blog_id else self._get_all_blog_ids()
            
            # Initialize results
            topics_performance = defaultdict(lambda: {
                "posts": 0,
                "views": 0,
                "engagements": 0,
                "ad_clicks": 0,
                "estimated_revenue": 0.0,
                "avg_time_on_page": 0.0
            })
            
            # Get post metadata to map posts to topics
            post_topics = {}  # post_id -> list of topics
            
            for bid in blog_ids:
                # Get all posts for this blog and their topics
                posts_path = os.path.join("data/blogs", bid, "posts.json")
                if os.path.exists(posts_path):
                    with open(posts_path, 'r') as f:
                        posts_data = json.load(f)
                    
                    for post in posts_data.get("posts", []):
                        post_id = post.get("id")
                        topics = post.get("topics", [])
                        post_topics[post_id] = topics
                        
                        # Increment post count for each topic
                        for topic in topics:
                            topics_performance[topic]["posts"] += 1
                
                # Get analytics data for this blog
                blog_analytics = self.get_analytics_summary(bid)
                
                # Aggregate top posts by topic
                for post in blog_analytics.get("top_posts", []):
                    post_id = post.get("id")
                    if post_id in post_topics:
                        for topic in post_topics[post_id]:
                            # Aggregate metrics
                            topics_performance[topic]["views"] += post.get("views", 0)
                            topics_performance[topic]["engagements"] += post.get("engagements", 0)
                            topics_performance[topic]["ad_clicks"] += post.get("ad_clicks", 0)
                            topics_performance[topic]["estimated_revenue"] += post.get("revenue", 0.0)
            
            # Calculate averages
            for topic, data in topics_performance.items():
                if data["posts"] > 0:
                    data["avg_views_per_post"] = data["views"] / data["posts"]
                    data["avg_revenue_per_post"] = data["estimated_revenue"] / data["posts"]
                else:
                    data["avg_views_per_post"] = 0
                    data["avg_revenue_per_post"] = 0
            
            # Convert to regular dict for JSON serialization
            return {topic: dict(data) for topic, data in topics_performance.items()}
            
        except Exception as e:
            logger.error(f"Error getting topic performance: {str(e)}")
            return {"error": str(e)}
    
    def get_seo_insights(self, blog_id: str = None) -> Dict[str, Any]:
        """
        Get SEO insights based on analytics data.
        
        Args:
            blog_id: Optional ID of a specific blog (or None for all blogs)
                
        Returns:
            Dict with SEO insights
        """
        try:
            blog_ids = [blog_id] if blog_id else self._get_all_blog_ids()
            
            insights = {
                "top_performing_keywords": [],
                "search_traffic_percentage": 0,
                "organic_traffic_growth": 0,
                "top_ranking_pages": [],
                "keyword_opportunities": [],
                "content_gaps": []
            }
            
            # This is a simplified implementation that would be augmented with real data
            # In a production environment, you'd integrate with Google Search Console API 
            # or similar to get actual SEO data
            
            # Collect search referrers from views data
            search_traffic = 0
            total_traffic = 0
            search_refs = defaultdict(int)
            
            for bid in blog_ids:
                # Get views for this blog
                views_path = self._get_analytics_file_path(bid, "views.json")
                if os.path.exists(views_path):
                    with open(views_path, 'r') as f:
                        views_data = json.load(f)
                    
                    for view in views_data.get("views", []):
                        total_traffic += 1
                        referrer = view.get("referrer", "").lower()
                        
                        # Identify search engine referrers
                        search_engines = ["google.", "bing.", "yahoo.", "duckduckgo.", "yandex.", "baidu."]
                        if any(se in referrer for se in search_engines):
                            search_traffic += 1
                            search_refs[referrer] += 1
            
            # Calculate search traffic percentage
            if total_traffic > 0:
                insights["search_traffic_percentage"] = (search_traffic / total_traffic) * 100
            
            # Get top search referrers
            insights["top_performing_keywords"] = [
                {"keyword": ref, "traffic": count} 
                for ref, count in sorted(search_refs.items(), key=lambda x: x[1], reverse=True)[:10]
            ]
            
            # In a real implementation, you would pull data from WordPress or Google Analytics
            # to populate the other insights fields
            
            return insights
            
        except Exception as e:
            logger.error(f"Error getting SEO insights: {str(e)}")
            return {"error": str(e)}
        
    def _update_aggregate_metrics(self, blog_id: str) -> None:
        """
        Update the aggregate metrics file for a blog.
        This is called after recording new analytics events.
        
        Args:
            blog_id: ID of the blog
        """
        try:
            # Get the analytics files
            views_path = self._get_analytics_file_path(blog_id, "views.json")
            engagement_path = self._get_analytics_file_path(blog_id, "engagement.json")
            ad_clicks_path = self._get_analytics_file_path(blog_id, "ad_clicks.json")
            
            # Initialize metrics
            metrics = {
                "total_views": 0,
                "total_engagements": 0,
                "total_ad_clicks": 0,
                "estimated_revenue": 0.0,
                "top_posts": [],
                "top_referrers": [],
                "traffic_by_country": {},
                "traffic_by_device": {},
                "last_updated": datetime.datetime.now().isoformat()
            }
            
            # Process views
            post_view_counts = defaultdict(int)
            referrer_counts = defaultdict(int)
            country_counts = defaultdict(int)
            device_counts = defaultdict(int)
            
            if os.path.exists(views_path):
                with open(views_path, 'r') as f:
                    views_data = json.load(f)
                
                for view in views_data.get("views", []):
                    metrics["total_views"] += 1
                    
                    post_id = view.get("post_id")
                    referrer = view.get("referrer", "direct")
                    country = view.get("country", "unknown")
                    device = view.get("device_type", "unknown")
                    
                    post_view_counts[post_id] += 1
                    referrer_counts[referrer] += 1
                    country_counts[country] += 1
                    device_counts[device] += 1
            
            # Process engagements
            post_engagement_counts = defaultdict(int)
            
            if os.path.exists(engagement_path):
                with open(engagement_path, 'r') as f:
                    engagement_data = json.load(f)
                
                for engagement in engagement_data.get("engagements", []):
                    metrics["total_engagements"] += 1
                    
                    post_id = engagement.get("post_id")
                    post_engagement_counts[post_id] += 1
            
            # Process ad clicks
            post_ad_click_counts = defaultdict(int)
            post_ad_revenue = defaultdict(float)
            
            if os.path.exists(ad_clicks_path):
                with open(ad_clicks_path, 'r') as f:
                    ad_clicks_data = json.load(f)
                
                for click in ad_clicks_data.get("ad_clicks", []):
                    metrics["total_ad_clicks"] += 1
                    
                    post_id = click.get("post_id")
                    revenue = float(click.get("ad_revenue", 0))
                    
                    post_ad_click_counts[post_id] += 1
                    post_ad_revenue[post_id] += revenue
                    metrics["estimated_revenue"] += revenue
            
            # Generate top posts list
            top_posts = []
            
            for post_id in set(list(post_view_counts.keys()) + list(post_engagement_counts.keys()) + list(post_ad_click_counts.keys())):
                top_posts.append({
                    "id": post_id,
                    "views": post_view_counts.get(post_id, 0),
                    "engagements": post_engagement_counts.get(post_id, 0),
                    "ad_clicks": post_ad_click_counts.get(post_id, 0),
                    "revenue": post_ad_revenue.get(post_id, 0.0)
                })
            
            # Sort by views
            top_posts.sort(key=lambda x: x["views"], reverse=True)
            metrics["top_posts"] = top_posts
            
            # Generate top referrers list
            top_referrers = [{"referrer": ref, "count": count} for ref, count in referrer_counts.items()]
            top_referrers.sort(key=lambda x: x["count"], reverse=True)
            metrics["top_referrers"] = top_referrers
            
            # Add traffic by country and device
            metrics["traffic_by_country"] = dict(country_counts)
            metrics["traffic_by_device"] = dict(device_counts)
            
            # Save the aggregate metrics
            metrics_path = self._get_analytics_file_path(blog_id, "aggregate_metrics.json")
            with open(metrics_path, 'w') as f:
                json.dump(metrics, f, indent=2)
                
        except Exception as e:
            logger.error(f"Error updating aggregate metrics for blog {blog_id}: {str(e)}")
    
    def _get_analytics_file_path(self, blog_id: str, filename: str) -> str:
        """
        Get the path to an analytics data file for a blog.
        
        Args:
            blog_id: ID of the blog
            filename: Name of the analytics file
                
        Returns:
            str: Path to the analytics file
        """
        # Create analytics directory if it doesn't exist
        analytics_dir = os.path.join("data/blogs", blog_id, "analytics")
        os.makedirs(analytics_dir, exist_ok=True)
        
        return os.path.join(analytics_dir, filename)
    
    def _get_all_blog_ids(self) -> List[str]:
        """
        Get IDs of all blogs in the system.
                
        Returns:
            List[str]: List of blog IDs
        """
        blog_ids = []
        blogs_dir = "data/blogs"
        
        if os.path.exists(blogs_dir):
            # List all directories in the blogs directory
            for item in os.listdir(blogs_dir):
                if os.path.isdir(os.path.join(blogs_dir, item)):
                    blog_ids.append(item)
        
        return blog_ids
    
    def get_google_analytics_data(self, blog_id: str, period: str = "month") -> Dict[str, Any]:
        """
        Retrieve data from Google Analytics for a specific blog.
        
        Args:
            blog_id: ID of the blog
            period: Time period for the data (day, week, month, year)
                
        Returns:
            Dict with Google Analytics data
        """
        if not self.ga_integration_enabled:
            logger.warning("Google Analytics integration not enabled")
            return {"error": "Google Analytics integration not enabled"}
        
        try:
            # In a real implementation, this would use the Google Analytics API
            # with the google-analytics-data package
            # https://developers.google.com/analytics/devguides/reporting/data/v1/quickstart-client-libraries
            
            # For this placeholder, we will return a simulated response
            ga_config = self._get_blog_ga_config(blog_id)
            
            if not ga_config:
                return {
                    "error": "Google Analytics not configured for this blog",
                    "enabled": False
                }
            
            # Placeholder for Google Analytics API call
            # In a production environment, you would make a real API call here
            property_id = ga_config.get("property_id")
            
            # Simulate data retrieval
            # In a real implementation, this data would come from the Google Analytics API
            return {
                "enabled": True,
                "property_id": property_id,
                "period": period,
                "metrics": {
                    "users": 1200,
                    "new_users": 450,
                    "sessions": 1800,
                    "bounce_rate": 42.5,
                    "avg_session_duration": 125,
                    "pages_per_session": 2.3,
                    "goal_completions": 85
                },
                "top_pages": [
                    {"path": "/sample-post-1", "pageviews": 350, "unique_pageviews": 280},
                    {"path": "/sample-post-2", "pageviews": 220, "unique_pageviews": 180},
                    {"path": "/sample-post-3", "pageviews": 180, "unique_pageviews": 150}
                ],
                "demographics": {
                    "age": {
                        "18-24": 15,
                        "25-34": 30,
                        "35-44": 25,
                        "45-54": 15,
                        "55-64": 10,
                        "65+": 5
                    },
                    "gender": {
                        "male": 55,
                        "female": 45
                    }
                },
                "traffic_sources": {
                    "organic": 45,
                    "direct": 30,
                    "referral": 15,
                    "social": 8,
                    "email": 2
                },
                "devices": {
                    "mobile": 60,
                    "desktop": 35,
                    "tablet": 5
                }
            }
            
        except Exception as e:
            logger.error(f"Error getting Google Analytics data for blog {blog_id}: {str(e)}")
            return {"error": str(e), "enabled": self.ga_integration_enabled}
    
    def get_adsense_data(self, blog_id: str, period: str = "month") -> Dict[str, Any]:
        """
        Retrieve data from Google AdSense for a specific blog.
        
        Args:
            blog_id: ID of the blog
            period: Time period for the data (day, week, month, year)
                
        Returns:
            Dict with AdSense data
        """
        if not self.adsense_integration_enabled:
            logger.warning("Google AdSense integration not enabled")
            return {"error": "Google AdSense integration not enabled"}
        
        try:
            # In a real implementation, this would use the Google AdSense API
            # with the googleapis package
            # https://developers.google.com/adsense/management/v1.4/reference
            
            # For this placeholder, we will return a simulated response
            adsense_config = self._get_blog_adsense_config(blog_id)
            
            if not adsense_config:
                return {
                    "error": "AdSense not configured for this blog",
                    "enabled": False
                }
            
            # Placeholder for AdSense API call
            # In a production environment, you would make a real API call here
            client_id = adsense_config.get("client_id")
            
            # Simulate data retrieval
            # In a real implementation, this data would come from the AdSense API
            return {
                "enabled": True,
                "client_id": client_id,
                "period": period,
                "metrics": {
                    "page_impressions": 15000,
                    "ad_impressions": 45000,
                    "clicks": 350,
                    "ctr": 0.78,
                    "cpm": 2.25,
                    "revenue": 101.25
                },
                "top_performing_ads": [
                    {"ad_unit": "sidebar-top", "impressions": 15000, "clicks": 150, "ctr": 1.0, "revenue": 42.50},
                    {"ad_unit": "in-content", "impressions": 12000, "clicks": 120, "ctr": 1.0, "revenue": 36.25},
                    {"ad_unit": "below-post", "impressions": 8000, "clicks": 80, "ctr": 1.0, "revenue": 22.50}
                ],
                "top_performing_pages": [
                    {"path": "/sample-post-1", "impressions": 5000, "clicks": 60, "revenue": 22.25},
                    {"path": "/sample-post-2", "impressions": 4000, "clicks": 50, "revenue": 18.75},
                    {"path": "/sample-post-3", "impressions": 3000, "clicks": 40, "revenue": 15.00}
                ],
                "daily_performance": [
                    {"date": "2025-04-01", "impressions": 1500, "clicks": 12, "revenue": 3.45},
                    {"date": "2025-04-02", "impressions": 1450, "clicks": 11, "revenue": 3.25},
                    {"date": "2025-04-03", "impressions": 1600, "clicks": 14, "revenue": 3.75}
                    # Additional days would be included here
                ],
                "devices": {
                    "mobile": {"impressions": 27000, "clicks": 210, "revenue": 60.75},
                    "desktop": {"impressions": 15750, "clicks": 122, "revenue": 35.45},
                    "tablet": {"impressions": 2250, "clicks": 18, "revenue": 5.05}
                }
            }
            
        except Exception as e:
            logger.error(f"Error getting AdSense data for blog {blog_id}: {str(e)}")
            return {"error": str(e), "enabled": self.adsense_integration_enabled}
    
    def get_search_console_data(self, blog_id: str, period: str = "month") -> Dict[str, Any]:
        """
        Retrieve data from Google Search Console for a specific blog.
        
        Args:
            blog_id: ID of the blog
            period: Time period for the data (day, week, month, year)
                
        Returns:
            Dict with Search Console data
        """
        if not self.search_console_integration_enabled:
            logger.warning("Google Search Console integration not enabled")
            return {"error": "Google Search Console integration not enabled"}
        
        try:
            # In a real implementation, this would use the Google Search Console API
            # with the googleapis package
            # https://developers.google.com/webmaster-tools/search-console-api-original/v3/how-tos/search_analytics
            
            # For this placeholder, we will return a simulated response
            search_console_config = self._get_blog_search_console_config(blog_id)
            
            if not search_console_config:
                return {
                    "error": "Search Console not configured for this blog",
                    "enabled": False
                }
            
            # Placeholder for Search Console API call
            # In a production environment, you would make a real API call here
            site_url = search_console_config.get("site_url")
            
            # Simulate data retrieval
            # In a real implementation, this data would come from the Search Console API
            return {
                "enabled": True,
                "site_url": site_url,
                "period": period,
                "metrics": {
                    "total_clicks": 3200,
                    "total_impressions": 95000,
                    "average_ctr": 3.37,
                    "average_position": 22.4
                },
                "top_queries": [
                    {"query": "sample search term 1", "clicks": 250, "impressions": 3500, "ctr": 7.14, "position": 3.2},
                    {"query": "sample search term 2", "clicks": 180, "impressions": 2700, "ctr": 6.67, "position": 4.5},
                    {"query": "sample search term 3", "clicks": 150, "impressions": 2300, "ctr": 6.52, "position": 5.1}
                ],
                "top_pages": [
                    {"page": "/sample-post-1", "clicks": 350, "impressions": 5200, "ctr": 6.73, "position": 4.2},
                    {"page": "/sample-post-2", "clicks": 280, "impressions": 4300, "ctr": 6.51, "position": 5.3},
                    {"page": "/sample-post-3", "clicks": 210, "impressions": 3400, "ctr": 6.18, "position": 6.1}
                ],
                "devices": {
                    "mobile": {"clicks": 1920, "impressions": 57000, "ctr": 3.37, "position": 22.5},
                    "desktop": {"clicks": 1120, "impressions": 33250, "ctr": 3.37, "position": 22.2},
                    "tablet": {"clicks": 160, "impressions": 4750, "ctr": 3.37, "position": 22.8}
                },
                "countries": {
                    "us": {"clicks": 1600, "impressions": 47500, "ctr": 3.37, "position": 21.5},
                    "uk": {"clicks": 480, "impressions": 14250, "ctr": 3.37, "position": 23.2},
                    "ca": {"clicks": 320, "impressions": 9500, "ctr": 3.37, "position": 22.8},
                    "au": {"clicks": 192, "impressions": 5700, "ctr": 3.37, "position": 24.1},
                    "other": {"clicks": 608, "impressions": 18050, "ctr": 3.37, "position": 22.7}
                }
            }
            
        except Exception as e:
            logger.error(f"Error getting Search Console data for blog {blog_id}: {str(e)}")
            return {"error": str(e), "enabled": self.search_console_integration_enabled}
    
    def get_wordpress_analytics(self, blog_id: str) -> Dict[str, Any]:
        """
        Retrieve analytics data from WordPress plugins (Jetpack/MonsterInsights).
        
        Args:
            blog_id: ID of the blog
                
        Returns:
            Dict with WordPress analytics data
        """
        if not self.wordpress_analytics_enabled:
            logger.warning("WordPress Analytics integration not enabled")
            return {"error": "WordPress Analytics integration not enabled"}
        
        try:
            # In a real implementation, this would use the WordPress REST API
            # with the appropriate authentication to access Jetpack or MonsterInsights data
            
            # For this placeholder, we will return a simulated response
            wordpress_config = self._get_blog_wordpress_config(blog_id)
            
            if not wordpress_config:
                return {
                    "error": "WordPress not configured for this blog",
                    "enabled": False
                }
            
            # Placeholder for WordPress API call
            # In a production environment, you would make a real API call here
            site_url = wordpress_config.get("url")
            plugin = wordpress_config.get("analytics_plugin", "jetpack")
            
            # Simulate data retrieval
            # In a real implementation, this data would come from the WordPress REST API
            return {
                "enabled": True,
                "site_url": site_url,
                "plugin": plugin,
                "metrics": {
                    "views": 8500,
                    "visitors": 3200,
                    "comments": 120,
                    "likes": 350,
                    "shares": 180
                },
                "top_posts": [
                    {"title": "Sample Post 1", "views": 1200, "comments": 25, "likes": 45, "shares": 30},
                    {"title": "Sample Post 2", "views": 950, "comments": 18, "likes": 38, "shares": 25},
                    {"title": "Sample Post 3", "views": 750, "comments": 15, "likes": 32, "shares": 20}
                ],
                "referrers": {
                    "search": 3400,
                    "social": 2100,
                    "links": 1700,
                    "direct": 1300
                },
                "countries": {
                    "us": 4250,
                    "uk": 1275,
                    "ca": 850,
                    "au": 510,
                    "other": 1615
                }
            }
            
        except Exception as e:
            logger.error(f"Error getting WordPress analytics for blog {blog_id}: {str(e)}")
            return {"error": str(e), "enabled": self.wordpress_analytics_enabled}
    
    def configure_google_analytics(self, blog_id: str, property_id: str, measurement_id: str = None) -> bool:
        """
        Configure Google Analytics for a specific blog.
        
        Args:
            blog_id: ID of the blog
            property_id: Google Analytics 4 property ID
            measurement_id: Optional Google Analytics 4 measurement ID
                
        Returns:
            bool: True if configuration was successful, False otherwise
        """
        try:
            ga_config = {
                "property_id": property_id,
                "measurement_id": measurement_id
            }
            
            # Save the GA configuration
            config_path = self._get_analytics_file_path(blog_id, "ga_config.json")
            with open(config_path, 'w') as f:
                json.dump(ga_config, f, indent=2)
            
            return True
            
        except Exception as e:
            logger.error(f"Error configuring Google Analytics for blog {blog_id}: {str(e)}")
            return False
    
    def configure_adsense(self, blog_id: str, client_id: str, ad_units: List[Dict[str, str]] = None) -> bool:
        """
        Configure Google AdSense for a specific blog.
        
        Args:
            blog_id: ID of the blog
            client_id: AdSense client ID
            ad_units: Optional list of ad unit configurations
                
        Returns:
            bool: True if configuration was successful, False otherwise
        """
        try:
            adsense_config = {
                "client_id": client_id,
                "ad_units": ad_units or []
            }
            
            # Save the AdSense configuration
            config_path = self._get_analytics_file_path(blog_id, "adsense_config.json")
            with open(config_path, 'w') as f:
                json.dump(adsense_config, f, indent=2)
            
            return True
            
        except Exception as e:
            logger.error(f"Error configuring AdSense for blog {blog_id}: {str(e)}")
            return False
    
    def configure_search_console(self, blog_id: str, site_url: str) -> bool:
        """
        Configure Google Search Console for a specific blog.
        
        Args:
            blog_id: ID of the blog
            site_url: Verified site URL in Search Console
                
        Returns:
            bool: True if configuration was successful, False otherwise
        """
        try:
            search_console_config = {
                "site_url": site_url
            }
            
            # Save the Search Console configuration
            config_path = self._get_analytics_file_path(blog_id, "search_console_config.json")
            with open(config_path, 'w') as f:
                json.dump(search_console_config, f, indent=2)
            
            return True
            
        except Exception as e:
            logger.error(f"Error configuring Search Console for blog {blog_id}: {str(e)}")
            return False
    
    def _get_blog_ga_config(self, blog_id: str) -> Dict[str, Any]:
        """Get Google Analytics configuration for a blog"""
        config_path = self._get_analytics_file_path(blog_id, "ga_config.json")
        if os.path.exists(config_path):
            with open(config_path, 'r') as f:
                return json.load(f)
        return None
    
    def _get_blog_adsense_config(self, blog_id: str) -> Dict[str, Any]:
        """Get AdSense configuration for a blog"""
        config_path = self._get_analytics_file_path(blog_id, "adsense_config.json")
        if os.path.exists(config_path):
            with open(config_path, 'r') as f:
                return json.load(f)
        return None
    
    def _get_blog_search_console_config(self, blog_id: str) -> Dict[str, Any]:
        """Get Search Console configuration for a blog"""
        config_path = self._get_analytics_file_path(blog_id, "search_console_config.json")
        if os.path.exists(config_path):
            with open(config_path, 'r') as f:
                return json.load(f)
        return None
    
    def _get_blog_wordpress_config(self, blog_id: str) -> Dict[str, Any]:
        """Get WordPress configuration for a blog"""
        # First check for a specific WordPress analytics config
        config_path = self._get_analytics_file_path(blog_id, "wordpress_analytics_config.json")
        if os.path.exists(config_path):
            with open(config_path, 'r') as f:
                return json.load(f)
        
        # Fall back to the general WordPress config
        config_path = os.path.join("data/blogs", blog_id, "config.json")
        if os.path.exists(config_path):
            with open(config_path, 'r') as f:
                config = json.load(f)
                return config.get("wordpress", {})
        
        return None
    
    def _filter_metrics_by_period(self, metrics: Dict[str, Any], start_date: str) -> Dict[str, Any]:
        """
        Filter metrics by time period.
        This is a simplified implementation - in a real system, you'd have time-bucketed data.
        
        Args:
            metrics: The metrics dictionary
            start_date: Start date in ISO format
                
        Returns:
            Dict: Filtered metrics
        """
        # For a real implementation, this would involve going back to the raw data
        # and filtering by timestamp. This is a placeholder.
        return metrics

# JavaScript snippet to add to WordPress for tracking
WORDPRESS_TRACKING_CODE = """
<!-- Analytics Tracking Code -->
<script type="text/javascript">
(function() {
    // Blog ID and post ID should be dynamically inserted by the Publisher
    var blogId = '{{blog_id}}';
    var postId = '{{post_id}}';
    
    // Basic analytics data
    var analyticsData = {
        referrer: document.referrer || 'direct',
        userAgent: navigator.userAgent,
        timestamp: new Date().toISOString(),
        sessionId: generateSessionId(),
        url: window.location.href
    };
    
    // Generate or retrieve session ID
    function generateSessionId() {
        var sessionId = localStorage.getItem('blog_session_id');
        if (!sessionId) {
            sessionId = 'sess_' + Math.random().toString(36).substring(2, 15);
            localStorage.setItem('blog_session_id', sessionId);
        }
        return sessionId;
    }
    
    // Record page view
    function recordPageView() {
        fetch('/api/analytics/page_view', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                blog_id: blogId,
                post_id: postId,
                data: analyticsData
            })
        }).catch(function(error) {
            console.error('Analytics error:', error);
        });
    }
    
    // Record engagement (comments, shares, etc.)
    function recordEngagement(type, metadata) {
        fetch('/api/analytics/engagement', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                blog_id: blogId,
                post_id: postId,
                type: type,
                data: Object.assign({}, analyticsData, { metadata: metadata })
            })
        }).catch(function(error) {
            console.error('Analytics error:', error);
        });
    }
    
    // Record ad clicks
    function recordAdClick(adData) {
        fetch('/api/analytics/ad_click', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                blog_id: blogId,
                post_id: postId,
                data: Object.assign({}, analyticsData, adData)
            })
        }).catch(function(error) {
            console.error('Analytics error:', error);
        });
    }
    
    // Record the page view when the page loads
    window.addEventListener('load', recordPageView);
    
    // Add event listeners for engagement
    document.addEventListener('click', function(e) {
        // Track social share clicks
        if (e.target.matches('.share-button, .share-button *')) {
            var platform = e.target.closest('.share-button').dataset.platform;
            recordEngagement('share', { platform: platform });
        }
        
        // Track comment form submissions
        if (e.target.matches('#comment-submit')) {
            recordEngagement('comment', { });
        }
        
        // Track ad clicks (simplified - would be integrated with ad provider callbacks)
        if (e.target.matches('.adsense-container, .adsense-container *')) {
            var adContainer = e.target.closest('.adsense-container');
            recordAdClick({
                ad_id: adContainer.dataset.adId || 'unknown',
                ad_position: adContainer.dataset.position || 'unknown',
                ad_network: 'adsense'
            });
        }
    });
    
    // Expose the analytics functions globally
    window.blogAnalytics = {
        recordEngagement: recordEngagement,
        recordAdClick: recordAdClick
    };
})();
</script>
<!-- End Analytics Tracking Code -->
"""