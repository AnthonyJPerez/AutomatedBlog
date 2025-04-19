"""
Backlink Monitoring Service

This service handles monitoring, tracking, and analysis of backlinks for blogs in the platform.
It provides capabilities to discover new backlinks, analyze their quality, and track changes
over time.
"""

import os
import json
import logging
import time
import datetime
import requests
from typing import Dict, List, Optional, Tuple, Any
from urllib.parse import urlparse

# Set up logging
logger = logging.getLogger(__name__)

# Constants
DEFAULT_USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
DEFAULT_HEADERS = {
    "User-Agent": DEFAULT_USER_AGENT,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1"
}

class BacklinkService:
    """
    Service for monitoring, analyzing, and tracking backlinks to blog content.
    """
    
    def __init__(self, storage_service=None, analytics_service=None):
        """
        Initialize the backlink monitoring service.
        
        Args:
            storage_service: Service for storing backlink data
            analytics_service: Service for analytics integration
        """
        self.storage_service = storage_service
        self.analytics_service = analytics_service
        self.api_key = os.environ.get("BACKLINK_API_KEY")
        self.use_external_api = bool(self.api_key)
        
        # Set up data directories
        if self.storage_service:
            self.storage_service.ensure_local_directory("data/backlinks")
        
        logger.info(f"Backlink Service initialized. Using external API: {self.use_external_api}")
    
    def discover_backlinks(self, blog_id: str, blog_url: str) -> Dict[str, Any]:
        """
        Discover new backlinks for a specific blog.
        
        Args:
            blog_id: The ID of the blog to check
            blog_url: The URL of the blog to analyze
            
        Returns:
            Dictionary with discovered backlinks and metadata
        """
        logger.info(f"Discovering backlinks for blog {blog_id} at URL {blog_url}")
        
        if self.use_external_api:
            return self._discover_backlinks_api(blog_url)
        else:
            return self._discover_backlinks_local(blog_id, blog_url)
    
    def _discover_backlinks_api(self, blog_url: str) -> Dict[str, Any]:
        """
        Use external API to discover backlinks (when API key is available).
        
        Args:
            blog_url: The URL to check for backlinks
            
        Returns:
            Dictionary with discovered backlinks from API
        """
        if not self.api_key:
            logger.warning("Cannot use API for backlink discovery: Missing API key")
            return {"success": False, "error": "Missing API key", "backlinks": []}
        
        try:
            # This is a placeholder for actual API implementation
            # In a real scenario, you would use services like Ahrefs, Moz, SEMrush, or Majestic
            logger.info(f"Querying external backlink API for {blog_url}")
            
            # Simulated API response for demonstration
            # In production, replace with actual API call
            api_url = "https://api.backlinkprovider.com/v1/backlinks"
            params = {
                "target": blog_url,
                "limit": 100,
                "apikey": self.api_key
            }
            
            response = requests.get(api_url, params=params, headers=DEFAULT_HEADERS)
            
            if response.status_code == 200:
                try:
                    data = response.json()
                    return {
                        "success": True,
                        "source": "api",
                        "backlinks": data.get("backlinks", []),
                        "total_count": data.get("total_count", 0),
                        "metrics": data.get("metrics", {}),
                        "timestamp": datetime.datetime.now().isoformat()
                    }
                except Exception as e:
                    logger.error(f"Error parsing API response: {str(e)}")
                    return {"success": False, "error": f"Error parsing API response: {str(e)}", "backlinks": []}
            else:
                logger.error(f"API error: {response.status_code} - {response.text}")
                return {"success": False, "error": f"API error: {response.status_code}", "backlinks": []}
                
        except Exception as e:
            logger.error(f"Error during API backlink discovery: {str(e)}")
            return {"success": False, "error": str(e), "backlinks": []}
    
    def _discover_backlinks_local(self, blog_id: str, blog_url: str) -> Dict[str, Any]:
        """
        Use local discovery for backlinks (when no API key is available).
        This implementation monitors referrer headers from your site's traffic.
        
        Args:
            blog_id: The ID of the blog to check
            blog_url: The URL of the blog to analyze
            
        Returns:
            Dictionary with discovered backlinks from local monitoring
        """
        logger.info(f"Using local backlink discovery for {blog_id}")
        
        # Get existing backlinks file or create if not exists
        backlinks_path = os.path.join("data/backlinks", f"{blog_id}_backlinks.json")
        existing_backlinks = []
        
        if os.path.exists(backlinks_path):
            try:
                with open(backlinks_path, 'r') as f:
                    existing_data = json.load(f)
                    existing_backlinks = existing_data.get("backlinks", [])
            except Exception as e:
                logger.error(f"Error reading existing backlinks: {str(e)}")
        
        # Check analytics service for referrers if available
        new_backlinks = []
        if self.analytics_service:
            try:
                # Get referrers from analytics
                referrers = self.analytics_service.get_top_referrers(blog_id, days=30, limit=100)
                
                # Process and normalize referrers
                for referrer in referrers:
                    source_url = referrer.get("source_url", "")
                    if not source_url or source_url == "direct" or blog_url in source_url:
                        continue
                        
                    parsed_url = urlparse(source_url)
                    domain = parsed_url.netloc
                    
                    # Check if this is already in our list
                    if not any(b.get("domain") == domain for b in existing_backlinks):
                        new_backlinks.append({
                            "source_url": source_url,
                            "domain": domain,
                            "first_seen": datetime.datetime.now().isoformat(),
                            "last_seen": datetime.datetime.now().isoformat(),
                            "visits": referrer.get("sessions", 0),
                            "discovery_method": "analytics"
                        })
                    else:
                        # Update existing backlink
                        for backlink in existing_backlinks:
                            if backlink.get("domain") == domain:
                                backlink["last_seen"] = datetime.datetime.now().isoformat()
                                backlink["visits"] = backlink.get("visits", 0) + referrer.get("sessions", 0)
                                break
            except Exception as e:
                logger.error(f"Error getting referrers from analytics: {str(e)}")
        
        # Combine existing and new backlinks
        all_backlinks = existing_backlinks + new_backlinks
        
        # Save updated backlinks
        try:
            result_data = {
                "blog_id": blog_id,
                "blog_url": blog_url,
                "backlinks": all_backlinks,
                "last_updated": datetime.datetime.now().isoformat(),
                "total_count": len(all_backlinks)
            }
            
            with open(backlinks_path, 'w') as f:
                json.dump(result_data, f, indent=2)
                
            return {
                "success": True,
                "source": "local",
                "backlinks": all_backlinks,
                "new_backlinks": new_backlinks,
                "total_count": len(all_backlinks),
                "timestamp": datetime.datetime.now().isoformat()
            }
        except Exception as e:
            logger.error(f"Error saving backlinks data: {str(e)}")
            return {
                "success": False,
                "error": f"Error saving backlinks data: {str(e)}",
                "backlinks": all_backlinks
            }
    
    def analyze_backlink_quality(self, backlinks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Analyze the quality and value of backlinks.
        
        Args:
            backlinks: List of backlink dictionaries to analyze
            
        Returns:
            List of backlinks with quality metrics added
        """
        analyzed_backlinks = []
        
        for backlink in backlinks:
            source_url = backlink.get("source_url", "")
            if not source_url:
                continue
                
            quality_score = 0  # Default score
            domain_authority = 0  # Default domain authority
            spam_score = 0  # Default spam score
            
            # If we have an API key, get quality metrics
            if self.use_external_api:
                try:
                    metrics = self._get_domain_metrics(source_url)
                    domain_authority = metrics.get("domain_authority", 0)
                    spam_score = metrics.get("spam_score", 0)
                except Exception as e:
                    logger.error(f"Error getting domain metrics: {str(e)}")
            
            # Calculate quality score (simplified algorithm)
            # In a real implementation, this would be more sophisticated
            quality_score = max(0, min(100, (domain_authority * 10) - (spam_score * 5)))
            
            # Add metrics to backlink
            analyzed_backlink = backlink.copy()
            analyzed_backlink.update({
                "quality_score": quality_score,
                "domain_authority": domain_authority,
                "spam_score": spam_score,
                "analyzed_at": datetime.datetime.now().isoformat()
            })
            
            analyzed_backlinks.append(analyzed_backlink)
        
        return analyzed_backlinks
    
    def _get_domain_metrics(self, url: str) -> Dict[str, Any]:
        """
        Get authority metrics for a domain using external API.
        
        Args:
            url: URL to get metrics for
            
        Returns:
            Dictionary with domain metrics
        """
        if not self.api_key:
            return {"domain_authority": 0, "spam_score": 0}
            
        try:
            # Placeholder for actual API call to a service like Moz, Majestic, or Ahrefs
            # In production, replace with actual implementation
            
            parsed_url = urlparse(url)
            domain = parsed_url.netloc
            
            api_url = "https://api.domainauthority.com/v1/metrics"
            params = {
                "domain": domain,
                "apikey": self.api_key
            }
            
            response = requests.get(api_url, params=params, headers=DEFAULT_HEADERS)
            
            if response.status_code == 200:
                data = response.json()
                return {
                    "domain_authority": data.get("domain_authority", 0),
                    "page_authority": data.get("page_authority", 0),
                    "spam_score": data.get("spam_score", 0),
                    "trust_flow": data.get("trust_flow", 0),
                    "citation_flow": data.get("citation_flow", 0)
                }
            else:
                logger.error(f"API error getting domain metrics: {response.status_code}")
                return {"domain_authority": 0, "spam_score": 0}
                
        except Exception as e:
            logger.error(f"Error getting domain metrics: {str(e)}")
            return {"domain_authority": 0, "spam_score": 0}
    
    def track_backlink_changes(self, blog_id: str) -> Dict[str, Any]:
        """
        Track changes in backlinks over time.
        
        Args:
            blog_id: Blog ID to track backlinks for
            
        Returns:
            Dictionary with backlink change metrics
        """
        # Get current backlinks file
        backlinks_path = os.path.join("data/backlinks", f"{blog_id}_backlinks.json")
        if not os.path.exists(backlinks_path):
            return {"success": False, "error": "No backlinks data found", "changes": {}}
            
        # Get history file
        history_path = os.path.join("data/backlinks", f"{blog_id}_history.json")
        history = []
        
        if os.path.exists(history_path):
            try:
                with open(history_path, 'r') as f:
                    history_data = json.load(f)
                    history = history_data.get("history", [])
            except Exception as e:
                logger.error(f"Error reading backlink history: {str(e)}")
        
        # Get current backlinks
        try:
            with open(backlinks_path, 'r') as f:
                current_data = json.load(f)
                current_backlinks = current_data.get("backlinks", [])
                blog_url = current_data.get("blog_url", "")
        except Exception as e:
            logger.error(f"Error reading current backlinks: {str(e)}")
            return {"success": False, "error": f"Error reading current backlinks: {str(e)}", "changes": {}}
        
        # Get previous snapshot
        previous_backlinks = []
        if history:
            previous_snapshot = history[-1]
            previous_backlinks = previous_snapshot.get("backlinks", [])
        
        # Calculate changes
        current_domains = {b.get("domain") for b in current_backlinks if b.get("domain")}
        previous_domains = {b.get("domain") for b in previous_backlinks if b.get("domain")}
        
        new_domains = current_domains - previous_domains
        lost_domains = previous_domains - current_domains
        
        new_backlinks = [b for b in current_backlinks if b.get("domain") in new_domains]
        lost_backlinks = [b for b in previous_backlinks if b.get("domain") in lost_domains]
        
        # Create snapshot for history
        snapshot = {
            "timestamp": datetime.datetime.now().isoformat(),
            "total_backlinks": len(current_backlinks),
            "backlinks": current_backlinks,
            "new_count": len(new_backlinks),
            "lost_count": len(lost_backlinks)
        }
        
        # Add to history (keep last 30 snapshots max)
        history.append(snapshot)
        if len(history) > 30:
            history = history[-30:]
        
        # Save history
        try:
            history_data = {
                "blog_id": blog_id,
                "blog_url": blog_url,
                "last_updated": datetime.datetime.now().isoformat(),
                "history": history
            }
            
            with open(history_path, 'w') as f:
                json.dump(history_data, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving backlink history: {str(e)}")
        
        # Return changes report
        return {
            "success": True,
            "timestamp": datetime.datetime.now().isoformat(),
            "total_backlinks": len(current_backlinks),
            "new_backlinks": {
                "count": len(new_backlinks),
                "domains": list(new_domains),
                "details": new_backlinks
            },
            "lost_backlinks": {
                "count": len(lost_backlinks),
                "domains": list(lost_domains),
                "details": lost_backlinks
            },
            "change_rate": {
                "new_rate": len(new_backlinks) / max(1, len(previous_backlinks)) if previous_backlinks else 0,
                "lost_rate": len(lost_backlinks) / max(1, len(previous_backlinks)) if previous_backlinks else 0
            }
        }
    
    def get_backlink_report(self, blog_id: str) -> Dict[str, Any]:
        """
        Generate a comprehensive backlink report for a blog.
        
        Args:
            blog_id: Blog ID to generate report for
            
        Returns:
            Dictionary with backlink report data
        """
        backlinks_path = os.path.join("data/backlinks", f"{blog_id}_backlinks.json")
        history_path = os.path.join("data/backlinks", f"{blog_id}_history.json")
        
        if not os.path.exists(backlinks_path):
            return {"success": False, "error": "No backlinks data found"}
        
        try:
            # Load current backlinks
            with open(backlinks_path, 'r') as f:
                current_data = json.load(f)
                
            backlinks = current_data.get("backlinks", [])
            blog_url = current_data.get("blog_url", "")
            
            # Load history if available
            history = []
            if os.path.exists(history_path):
                try:
                    with open(history_path, 'r') as f:
                        history_data = json.load(f)
                        history = history_data.get("history", [])
                except Exception as e:
                    logger.error(f"Error reading backlink history: {str(e)}")
            
            # Calculate trends if history available
            trends = {"available": False}
            if len(history) >= 2:
                earliest = history[0]
                latest = history[-1]
                
                growth_rate = (latest.get("total_backlinks", 0) - earliest.get("total_backlinks", 0)) / max(1, earliest.get("total_backlinks", 1))
                
                # Calculate average change rates
                new_rates = [snapshot.get("new_count", 0) / max(1, snapshot.get("total_backlinks", 1)) for snapshot in history[1:]]
                lost_rates = [snapshot.get("lost_count", 0) / max(1, snapshot.get("total_backlinks", 1)) for snapshot in history[1:]]
                
                avg_new_rate = sum(new_rates) / max(1, len(new_rates)) if new_rates else 0
                avg_lost_rate = sum(lost_rates) / max(1, len(lost_rates)) if lost_rates else 0
                
                trends = {
                    "available": True,
                    "period_start": earliest.get("timestamp"),
                    "period_end": latest.get("timestamp"),
                    "growth_rate": growth_rate,
                    "avg_new_rate": avg_new_rate,
                    "avg_lost_rate": avg_lost_rate
                }
            
            # Group backlinks by domain quality
            quality_groups = {"high": [], "medium": [], "low": []}
            for backlink in backlinks:
                quality_score = backlink.get("quality_score", 0)
                if quality_score >= 70:
                    quality_groups["high"].append(backlink)
                elif quality_score >= 40:
                    quality_groups["medium"].append(backlink)
                else:
                    quality_groups["low"].append(backlink)
            
            # Generate report
            report = {
                "success": True,
                "blog_id": blog_id,
                "blog_url": blog_url,
                "timestamp": datetime.datetime.now().isoformat(),
                "summary": {
                    "total_backlinks": len(backlinks),
                    "referring_domains": len({b.get("domain") for b in backlinks if b.get("domain")}),
                    "quality_distribution": {
                        "high": len(quality_groups["high"]),
                        "medium": len(quality_groups["medium"]),
                        "low": len(quality_groups["low"])
                    }
                },
                "trends": trends,
                "top_backlinks": sorted(
                    [b for b in backlinks if b.get("quality_score", 0) > 0],
                    key=lambda x: x.get("quality_score", 0),
                    reverse=True
                )[:10],
                "recent_backlinks": sorted(
                    backlinks,
                    key=lambda x: x.get("first_seen", ""),
                    reverse=True
                )[:10]
            }
            
            return report
            
        except Exception as e:
            logger.error(f"Error generating backlink report: {str(e)}")
            return {"success": False, "error": f"Error generating backlink report: {str(e)}"}
    
    def monitor_competitors_backlinks(self, blog_id: str, competitor_urls: List[str]) -> Dict[str, Any]:
        """
        Monitor and compare backlinks from competitor websites.
        
        Args:
            blog_id: Blog ID to compare with
            competitor_urls: List of competitor URLs to monitor
            
        Returns:
            Dictionary with competitor backlink comparison
        """
        if not competitor_urls:
            return {"success": False, "error": "No competitor URLs provided"}
            
        # Get blog backlinks
        backlinks_path = os.path.join("data/backlinks", f"{blog_id}_backlinks.json")
        if not os.path.exists(backlinks_path):
            return {"success": False, "error": "No backlinks data found for blog"}
            
        try:
            with open(backlinks_path, 'r') as f:
                blog_data = json.load(f)
                blog_backlinks = blog_data.get("backlinks", [])
                blog_url = blog_data.get("blog_url", "")
        except Exception as e:
            logger.error(f"Error reading blog backlinks: {str(e)}")
            return {"success": False, "error": f"Error reading blog backlinks: {str(e)}"}
            
        # Get competitor backlinks
        competitor_data = []
        for competitor_url in competitor_urls:
            try:
                # Use API if available
                if self.use_external_api:
                    competitor_backlinks = self._discover_backlinks_api(competitor_url)
                    
                    if competitor_backlinks.get("success"):
                        competitor_data.append({
                            "url": competitor_url,
                            "domain": urlparse(competitor_url).netloc,
                            "backlinks": competitor_backlinks.get("backlinks", []),
                            "total_count": competitor_backlinks.get("total_count", 0)
                        })
                else:
                    # For demo purposes, we'll simulate competitor data
                    # In a real implementation, you would need a service like Ahrefs, Moz, etc.
                    logger.warning(f"Using simulated competitor data for {competitor_url} (API key required for real data)")
                    
                    # Create simplified report
                    competitor_data.append({
                        "url": competitor_url,
                        "domain": urlparse(competitor_url).netloc,
                        "backlinks": [],
                        "total_count": 0,
                        "simulated": True
                    })
            except Exception as e:
                logger.error(f"Error getting competitor backlinks for {competitor_url}: {str(e)}")
        
        # Compare backlinks
        blog_domains = {b.get("domain") for b in blog_backlinks if b.get("domain")}
        
        comparison = []
        for competitor in competitor_data:
            competitor_domains = {b.get("domain") for b in competitor.get("backlinks", []) if b.get("domain")}
            
            # Find shared and unique domains
            shared_domains = blog_domains.intersection(competitor_domains)
            competitor_unique = competitor_domains - blog_domains
            blog_unique = blog_domains - competitor_domains
            
            comparison.append({
                "competitor_url": competitor.get("url"),
                "competitor_domain": competitor.get("domain"),
                "total_backlinks": competitor.get("total_count", 0),
                "shared_domains": {
                    "count": len(shared_domains),
                    "domains": list(shared_domains)
                },
                "competitor_unique": {
                    "count": len(competitor_unique),
                    "domains": list(competitor_unique)
                },
                "blog_unique": {
                    "count": len(blog_unique),
                    "domains": list(blog_unique)
                },
                "simulated": competitor.get("simulated", False)
            })
        
        # Generate opportunities
        opportunities = []
        for competitor in competitor_data:
            competitor_backlinks = competitor.get("backlinks", [])
            competitor_domains = {b.get("domain") for b in competitor_backlinks if b.get("domain")}
            
            # Find domains that link to competitor but not to blog
            opportunity_domains = competitor_domains - blog_domains
            
            # Get high-quality opportunity backlinks
            for backlink in competitor_backlinks:
                if backlink.get("domain") in opportunity_domains:
                    quality_score = backlink.get("quality_score", 0)
                    if quality_score >= 40:  # Medium quality or better
                        opportunities.append({
                            "source_url": backlink.get("source_url"),
                            "domain": backlink.get("domain"),
                            "quality_score": quality_score,
                            "competitor": competitor.get("domain"),
                            "opportunity_type": "competitor_backlink"
                        })
        
        # Sort opportunities by quality
        opportunities.sort(key=lambda x: x.get("quality_score", 0), reverse=True)
        
        return {
            "success": True,
            "blog_id": blog_id,
            "blog_url": blog_url,
            "timestamp": datetime.datetime.now().isoformat(),
            "blog_backlinks_count": len(blog_backlinks),
            "competitor_comparison": comparison,
            "backlink_opportunities": opportunities[:10]  # Top 10 opportunities
        }