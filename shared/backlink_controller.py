"""
Backlink Controller

This module integrates the backlink service with the Flask application,
handling backlink-related routes and API endpoints.
"""

import os
import json
import logging
import datetime
from typing import Dict, List, Optional, Any

# Set up logging
logger = logging.getLogger(__name__)

class BacklinkController:
    """
    Controller for backlink monitoring features in the web application.
    """
    
    def __init__(self, backlink_service=None, storage_service=None):
        """
        Initialize the backlink controller.
        
        Args:
            backlink_service: Service for backlink monitoring
            storage_service: Service for storage operations
        """
        self.backlink_service = backlink_service
        self.storage_service = storage_service
        
        if storage_service:
            self.storage_service.ensure_local_directory("data/backlinks")
            self.storage_service.ensure_local_directory("data/backlinks/reports")
        
        logger.info("Backlink Controller initialized")
    
    def get_backlinks(self, blog_id: str) -> Dict[str, Any]:
        """
        Get backlinks for a specific blog.
        
        Args:
            blog_id: ID of the blog to get backlinks for
            
        Returns:
            Dictionary with backlinks and metadata
        """
        logger.info(f"Getting backlinks for blog {blog_id}")
        
        if not self.backlink_service:
            return {"success": False, "error": "Backlink service is not available"}
        
        backlinks_path = os.path.join("data/backlinks", f"{blog_id}_backlinks.json")
        
        if os.path.exists(backlinks_path):
            try:
                with open(backlinks_path, 'r') as f:
                    data = json.load(f)
                    return {
                        "success": True,
                        "blog_id": blog_id,
                        "backlinks": data.get("backlinks", []),
                        "total_count": data.get("total_count", 0),
                        "last_updated": data.get("last_updated")
                    }
            except Exception as e:
                logger.error(f"Error reading backlinks data: {str(e)}")
                return {"success": False, "error": f"Error reading backlinks data: {str(e)}"}
        else:
            return {"success": False, "error": "No backlinks data found for this blog"}
    
    def refresh_backlinks(self, blog_id: str, blog_url: str) -> Dict[str, Any]:
        """
        Refresh backlinks data for a blog by running discovery.
        
        Args:
            blog_id: ID of the blog
            blog_url: URL of the blog
            
        Returns:
            Dictionary with operation results
        """
        logger.info(f"Refreshing backlinks for blog {blog_id}")
        
        if not self.backlink_service:
            return {"success": False, "error": "Backlink service is not available"}
        
        try:
            # Call discovery process
            result = self.backlink_service.discover_backlinks(blog_id, blog_url)
            
            if result.get("success"):
                # Add quality analysis for new backlinks
                new_backlinks = result.get("new_backlinks", [])
                if new_backlinks:
                    analyzed_backlinks = self.backlink_service.analyze_backlink_quality(new_backlinks)
                    
                    # Update backlinks file with analyzed data
                    backlinks_path = os.path.join("data/backlinks", f"{blog_id}_backlinks.json")
                    if os.path.exists(backlinks_path):
                        try:
                            with open(backlinks_path, 'r') as f:
                                data = json.load(f)
                                
                            # Replace new backlinks with analyzed versions
                            existing_backlinks = data.get("backlinks", [])
                            analyzed_domains = {b.get("domain") for b in analyzed_backlinks if b.get("domain")}
                            
                            # Remove new backlinks from existing list (they'll be replaced with analyzed versions)
                            existing_backlinks = [b for b in existing_backlinks if b.get("domain") not in analyzed_domains]
                            
                            # Add analyzed backlinks
                            all_backlinks = existing_backlinks + analyzed_backlinks
                            
                            # Update data
                            data["backlinks"] = all_backlinks
                            data["total_count"] = len(all_backlinks)
                            data["last_updated"] = datetime.datetime.now().isoformat()
                            
                            with open(backlinks_path, 'w') as f:
                                json.dump(data, f, indent=2)
                        except Exception as e:
                            logger.error(f"Error updating backlinks with quality data: {str(e)}")
                
                # Track backlink changes
                changes = self.backlink_service.track_backlink_changes(blog_id)
                
                return {
                    "success": True,
                    "operation": "refresh_backlinks",
                    "blog_id": blog_id,
                    "discovery_result": result,
                    "changes": changes
                }
            else:
                return {
                    "success": False,
                    "operation": "refresh_backlinks",
                    "error": result.get("error", "Unknown error during backlink discovery")
                }
                
        except Exception as e:
            logger.error(f"Error refreshing backlinks: {str(e)}")
            return {"success": False, "error": f"Error refreshing backlinks: {str(e)}"}
    
    def get_backlink_report(self, blog_id: str) -> Dict[str, Any]:
        """
        Get comprehensive backlink report for a blog.
        
        Args:
            blog_id: ID of the blog to get report for
            
        Returns:
            Dictionary with backlink report data
        """
        logger.info(f"Getting backlink report for blog {blog_id}")
        
        if not self.backlink_service:
            return {"success": False, "error": "Backlink service is not available"}
        
        try:
            return self.backlink_service.get_backlink_report(blog_id)
        except Exception as e:
            logger.error(f"Error getting backlink report: {str(e)}")
            return {"success": False, "error": f"Error getting backlink report: {str(e)}"}
    
    def get_competitor_analysis(self, blog_id: str, competitor_urls: List[str]) -> Dict[str, Any]:
        """
        Get competitor backlink analysis.
        
        Args:
            blog_id: ID of the blog to analyze
            competitor_urls: List of competitor URLs to compare with
            
        Returns:
            Dictionary with competitor analysis data
        """
        logger.info(f"Getting competitor backlink analysis for blog {blog_id}")
        
        if not self.backlink_service:
            return {"success": False, "error": "Backlink service is not available"}
        
        if not competitor_urls:
            return {"success": False, "error": "No competitor URLs provided"}
        
        try:
            return self.backlink_service.monitor_competitors_backlinks(blog_id, competitor_urls)
        except Exception as e:
            logger.error(f"Error performing competitor backlink analysis: {str(e)}")
            return {"success": False, "error": f"Error performing competitor backlink analysis: {str(e)}"}
    
    def save_competitor_list(self, blog_id: str, competitors: List[Dict[str, str]]) -> Dict[str, Any]:
        """
        Save competitor list for a blog.
        
        Args:
            blog_id: ID of the blog
            competitors: List of competitor dictionaries with URL and name
            
        Returns:
            Dictionary with operation results
        """
        logger.info(f"Saving competitor list for blog {blog_id}")
        
        if not self.storage_service:
            return {"success": False, "error": "Storage service is not available"}
        
        try:
            competitors_path = os.path.join("data/backlinks", f"{blog_id}_competitors.json")
            
            data = {
                "blog_id": blog_id,
                "last_updated": datetime.datetime.now().isoformat(),
                "competitors": competitors
            }
            
            with open(competitors_path, 'w') as f:
                json.dump(data, f, indent=2)
                
            return {
                "success": True,
                "operation": "save_competitors",
                "blog_id": blog_id,
                "count": len(competitors)
            }
                
        except Exception as e:
            logger.error(f"Error saving competitor list: {str(e)}")
            return {"success": False, "error": f"Error saving competitor list: {str(e)}"}
    
    def get_competitor_list(self, blog_id: str) -> Dict[str, Any]:
        """
        Get competitor list for a blog.
        
        Args:
            blog_id: ID of the blog
            
        Returns:
            Dictionary with competitor list
        """
        logger.info(f"Getting competitor list for blog {blog_id}")
        
        competitors_path = os.path.join("data/backlinks", f"{blog_id}_competitors.json")
        
        if os.path.exists(competitors_path):
            try:
                with open(competitors_path, 'r') as f:
                    data = json.load(f)
                    return {
                        "success": True,
                        "blog_id": blog_id,
                        "competitors": data.get("competitors", []),
                        "last_updated": data.get("last_updated")
                    }
            except Exception as e:
                logger.error(f"Error reading competitor list: {str(e)}")
                return {"success": False, "error": f"Error reading competitor list: {str(e)}"}
        else:
            return {"success": True, "blog_id": blog_id, "competitors": [], "empty": True}
    
    def add_competitor(self, blog_id: str, competitor_url: str, competitor_name: str) -> Dict[str, Any]:
        """
        Add a competitor to the list for a blog.
        
        Args:
            blog_id: ID of the blog
            competitor_url: URL of the competitor
            competitor_name: Name of the competitor
            
        Returns:
            Dictionary with operation results
        """
        logger.info(f"Adding competitor for blog {blog_id}: {competitor_name} ({competitor_url})")
        
        if not self.storage_service:
            return {"success": False, "error": "Storage service is not available"}
        
        # Get existing competitors
        competitors_data = self.get_competitor_list(blog_id)
        competitors = competitors_data.get("competitors", [])
        
        # Check if competitor already exists
        for comp in competitors:
            if comp.get("url") == competitor_url:
                return {"success": False, "error": "Competitor with this URL already exists"}
        
        # Add new competitor
        competitors.append({
            "url": competitor_url,
            "name": competitor_name,
            "added_at": datetime.datetime.now().isoformat()
        })
        
        # Save updated list
        return self.save_competitor_list(blog_id, competitors)
    
    def remove_competitor(self, blog_id: str, competitor_url: str) -> Dict[str, Any]:
        """
        Remove a competitor from the list for a blog.
        
        Args:
            blog_id: ID of the blog
            competitor_url: URL of the competitor to remove
            
        Returns:
            Dictionary with operation results
        """
        logger.info(f"Removing competitor for blog {blog_id}: {competitor_url}")
        
        if not self.storage_service:
            return {"success": False, "error": "Storage service is not available"}
        
        # Get existing competitors
        competitors_data = self.get_competitor_list(blog_id)
        competitors = competitors_data.get("competitors", [])
        
        # Filter out the competitor to remove
        updated_competitors = [comp for comp in competitors if comp.get("url") != competitor_url]
        
        if len(updated_competitors) == len(competitors):
            return {"success": False, "error": "Competitor not found"}
        
        # Save updated list
        return self.save_competitor_list(blog_id, updated_competitors)
    
    def get_backlink_opportunities(self, blog_id: str) -> Dict[str, Any]:
        """
        Get backlink opportunities for a blog based on competitors and trends.
        
        Args:
            blog_id: ID of the blog
            
        Returns:
            Dictionary with backlink opportunities
        """
        logger.info(f"Getting backlink opportunities for blog {blog_id}")
        
        if not self.backlink_service or not self.storage_service:
            return {"success": False, "error": "Required services are not available"}
        
        # Get competitor list
        competitors_data = self.get_competitor_list(blog_id)
        competitors = competitors_data.get("competitors", [])
        
        if not competitors:
            return {
                "success": True,
                "blog_id": blog_id,
                "opportunities": [],
                "message": "No competitors defined. Add competitors to get backlink opportunities."
            }
        
        # Get competitor URLs
        competitor_urls = [comp.get("url") for comp in competitors if comp.get("url")]
        
        # Get competitor analysis with opportunities
        try:
            analysis = self.backlink_service.monitor_competitors_backlinks(blog_id, competitor_urls)
            
            if analysis.get("success"):
                return {
                    "success": True,
                    "blog_id": blog_id,
                    "opportunities": analysis.get("backlink_opportunities", []),
                    "competitors": competitors,
                    "timestamp": datetime.datetime.now().isoformat()
                }
            else:
                return {
                    "success": False,
                    "error": analysis.get("error", "Error getting competitor analysis")
                }
                
        except Exception as e:
            logger.error(f"Error getting backlink opportunities: {str(e)}")
            return {"success": False, "error": f"Error getting backlink opportunities: {str(e)}"}