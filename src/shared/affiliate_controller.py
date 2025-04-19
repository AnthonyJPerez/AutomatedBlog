"""
Affiliate Marketing Controller for Multi-Blog Platform

This controller handles all affiliate-related API and UI operations including:
- Link management
- Network configuration
- Reporting
- Link placement suggestions
"""

import json
import os
import logging
import datetime
from urllib.parse import urlparse
import re

# Set up logger
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

class AffiliateController:
    """Controller for managing affiliate marketing operations"""
    
    def __init__(self, affiliate_service=None, storage_service=None, notification_service=None):
        """
        Initialize the Affiliate Marketing Controller
        
        Args:
            affiliate_service: Service for managing affiliate links and networks
            storage_service: Service for storing and retrieving data
            notification_service: Service for sending notifications
        """
        self.affiliate_service = affiliate_service
        self.storage_service = storage_service
        self.notification_service = notification_service
        
        logger.info("Affiliate Controller initialized")
    
    # ===========================================================================
    # Link Management Methods
    # ===========================================================================
    
    def create_link(self, blog_id, product_url, product_name, network, custom_id=None):
        """
        Create an affiliate link
        
        Args:
            blog_id (str): ID of the blog
            product_url (str): Original product URL
            product_name (str): Name of the product
            network (str): Affiliate network (amazon, commission_junction, etc.)
            custom_id (str, optional): Custom identifier for this link
            
        Returns:
            dict: Operation result
        """
        if not self.affiliate_service:
            return {
                "success": False,
                "error": "Affiliate service is not available"
            }
            
        try:
            # Validate URL
            if not self._validate_url(product_url):
                return {
                    "success": False,
                    "error": "Invalid product URL"
                }
            
            # Validate product name
            if not product_name or len(product_name.strip()) == 0:
                return {
                    "success": False,
                    "error": "Product name is required"
                }
                
            # Get blog details
            blog = self._get_blog_by_id(blog_id)
            if not blog:
                return {
                    "success": False,
                    "error": f"Blog not found with ID: {blog_id}"
                }
            
            # Create the affiliate link
            result = self.affiliate_service.create_affiliate_link(
                blog_id=blog_id,
                product_url=product_url,
                product_name=product_name,
                network=network,
                custom_id=custom_id
            )
            
            if result["success"]:
                # If notification service is available, send email to blog owner
                if self.notification_service:
                    # Check if blog has an email address
                    if blog.get("owner_email"):
                        self.notification_service.send_template_email(
                            to_email=blog["owner_email"],
                            template_name="affiliate_link_created",
                            template_data={
                                "blog_name": blog.get("name", "Your blog"),
                                "product_name": product_name,
                                "product_url": product_url,
                                "network": network,
                                "affiliate_url": result["affiliate_url"],
                                "date": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                            }
                        )
            
            return result
        except Exception as e:
            logger.error(f"Error creating affiliate link: {str(e)}")
            return {
                "success": False,
                "error": f"Error creating affiliate link: {str(e)}"
            }
    
    def get_links(self, blog_id):
        """
        Get all affiliate links for a blog
        
        Args:
            blog_id (str): ID of the blog
            
        Returns:
            dict: Operation result
        """
        if not self.affiliate_service:
            return {
                "success": False,
                "error": "Affiliate service is not available"
            }
            
        try:
            # Validate blog
            blog = self._get_blog_by_id(blog_id)
            if not blog:
                return {
                    "success": False,
                    "error": f"Blog not found with ID: {blog_id}"
                }
            
            # Get affiliate links
            return self.affiliate_service.get_blog_affiliate_links(blog_id)
        except Exception as e:
            logger.error(f"Error getting affiliate links: {str(e)}")
            return {
                "success": False,
                "error": f"Error getting affiliate links: {str(e)}"
            }
    
    def get_link(self, link_id):
        """
        Get an affiliate link by ID
        
        Args:
            link_id (str): ID of the affiliate link
            
        Returns:
            dict: Operation result
        """
        if not self.affiliate_service:
            return {
                "success": False,
                "error": "Affiliate service is not available"
            }
            
        try:
            return self.affiliate_service.get_link_by_id(link_id)
        except Exception as e:
            logger.error(f"Error getting affiliate link: {str(e)}")
            return {
                "success": False,
                "error": f"Error getting affiliate link: {str(e)}"
            }
    
    def update_link(self, link_id, updates):
        """
        Update an affiliate link
        
        Args:
            link_id (str): ID of the affiliate link
            updates (dict): Fields to update
            
        Returns:
            dict: Operation result
        """
        if not self.affiliate_service:
            return {
                "success": False,
                "error": "Affiliate service is not available"
            }
            
        try:
            # Validate updates
            if "product_name" in updates and (not updates["product_name"] or len(updates["product_name"].strip()) == 0):
                return {
                    "success": False,
                    "error": "Product name cannot be empty"
                }
                
            if "product_url" in updates and not self._validate_url(updates["product_url"]):
                return {
                    "success": False,
                    "error": "Invalid product URL"
                }
            
            # Get current link data to check blog_id
            result = self.affiliate_service.get_link_by_id(link_id)
            if not result["success"]:
                return result
                
            # Update the link
            return self.affiliate_service.update_link(link_id, updates)
        except Exception as e:
            logger.error(f"Error updating affiliate link: {str(e)}")
            return {
                "success": False,
                "error": f"Error updating affiliate link: {str(e)}"
            }
    
    def delete_link(self, link_id):
        """
        Delete an affiliate link
        
        Args:
            link_id (str): ID of the affiliate link
            
        Returns:
            dict: Operation result
        """
        if not self.affiliate_service:
            return {
                "success": False,
                "error": "Affiliate service is not available"
            }
            
        try:
            return self.affiliate_service.delete_link(link_id)
        except Exception as e:
            logger.error(f"Error deleting affiliate link: {str(e)}")
            return {
                "success": False,
                "error": f"Error deleting affiliate link: {str(e)}"
            }
    
    def record_click(self, link_id):
        """
        Record a click on an affiliate link
        
        Args:
            link_id (str): ID of the affiliate link
            
        Returns:
            dict: Operation result
        """
        if not self.affiliate_service:
            return {
                "success": False,
                "error": "Affiliate service is not available"
            }
            
        try:
            return self.affiliate_service.record_link_click(link_id)
        except Exception as e:
            logger.error(f"Error recording affiliate link click: {str(e)}")
            return {
                "success": False,
                "error": f"Error recording affiliate link click: {str(e)}"
            }
    
    def record_conversion(self, link_id, order_id, amount):
        """
        Record a conversion (purchase) from an affiliate link
        
        Args:
            link_id (str): ID of the affiliate link
            order_id (str): Order or transaction ID
            amount (float): Purchase amount
            
        Returns:
            dict: Operation result
        """
        if not self.affiliate_service:
            return {
                "success": False,
                "error": "Affiliate service is not available"
            }
            
        try:
            # Record the conversion
            result = self.affiliate_service.record_conversion(link_id, order_id, amount)
            
            # If successful and notification service is available, send email
            if result["success"] and self.notification_service:
                # Get link details
                link_result = self.affiliate_service.get_link_by_id(link_id)
                if link_result["success"]:
                    link_data = link_result["link"]
                    blog_id = link_data["blog_id"]
                    
                    # Get blog details
                    blog = self._get_blog_by_id(blog_id)
                    if blog and blog.get("owner_email"):
                        # Send conversion notification
                        self.notification_service.notify_affiliate_conversion(
                            to_email=blog["owner_email"],
                            conversion_data={
                                "blog_name": blog.get("name", "Your blog"),
                                "product_name": link_data["product_name"],
                                "network": link_data["network"],
                                "order_id": order_id,
                                "amount": amount,
                                "timestamp": datetime.datetime.now().isoformat()
                            }
                        )
            
            return result
        except Exception as e:
            logger.error(f"Error recording affiliate conversion: {str(e)}")
            return {
                "success": False,
                "error": f"Error recording affiliate conversion: {str(e)}"
            }
    
    # ===========================================================================
    # Network Configuration Methods
    # ===========================================================================
    
    def get_networks_status(self):
        """
        Get status of all affiliate networks
        
        Returns:
            dict: Operation result
        """
        if not self.affiliate_service:
            return {
                "success": False,
                "error": "Affiliate service is not available"
            }
            
        try:
            return self.affiliate_service.get_networks_status()
        except Exception as e:
            logger.error(f"Error getting affiliate networks status: {str(e)}")
            return {
                "success": False,
                "error": f"Error getting affiliate networks status: {str(e)}"
            }
    
    def update_network_config(self, network, config_data):
        """
        Update configuration for an affiliate network
        
        Args:
            network (str): Name of the affiliate network
            config_data (dict): Configuration data for the network
            
        Returns:
            dict: Operation result
        """
        if not self.affiliate_service:
            return {
                "success": False,
                "error": "Affiliate service is not available"
            }
            
        try:
            return self.affiliate_service.update_network_config(network, config_data)
        except Exception as e:
            logger.error(f"Error updating affiliate network configuration: {str(e)}")
            return {
                "success": False,
                "error": f"Error updating affiliate network configuration: {str(e)}"
            }
    
    def test_network_connection(self, network):
        """
        Test connection to an affiliate network
        
        Args:
            network (str): Name of the affiliate network
            
        Returns:
            dict: Operation result
        """
        if not self.affiliate_service:
            return {
                "success": False,
                "error": "Affiliate service is not available"
            }
            
        try:
            return self.affiliate_service.test_network_connection(network)
        except Exception as e:
            logger.error(f"Error testing affiliate network connection: {str(e)}")
            return {
                "success": False,
                "error": f"Error testing affiliate network connection: {str(e)}"
            }
    
    # ===========================================================================
    # Reporting Methods
    # ===========================================================================
    
    def generate_report(self, blog_id, start_date=None, end_date=None):
        """
        Generate an affiliate performance report for a blog
        
        Args:
            blog_id (str): ID of the blog
            start_date (str, optional): Start date for the report (ISO format)
            end_date (str, optional): End date for the report (ISO format)
            
        Returns:
            dict: Operation result
        """
        if not self.affiliate_service:
            return {
                "success": False,
                "error": "Affiliate service is not available"
            }
            
        try:
            # Validate blog
            blog = self._get_blog_by_id(blog_id)
            if not blog:
                return {
                    "success": False,
                    "error": f"Blog not found with ID: {blog_id}"
                }
            
            # Generate the report
            return self.affiliate_service.generate_affiliate_report(blog_id, start_date, end_date)
        except Exception as e:
            logger.error(f"Error generating affiliate report: {str(e)}")
            return {
                "success": False,
                "error": f"Error generating affiliate report: {str(e)}"
            }
    
    # ===========================================================================
    # Link Suggestion Methods
    # ===========================================================================
    
    def suggest_links_for_content(self, blog_id, content):
        """
        Suggest affiliate links for blog content
        
        Args:
            blog_id (str): ID of the blog
            content (str): Blog content to analyze
            
        Returns:
            dict: Operation result with link suggestions
        """
        if not self.affiliate_service:
            return {
                "success": False,
                "error": "Affiliate service is not available"
            }
            
        try:
            # Get all affiliate links for the blog
            links_result = self.affiliate_service.get_blog_affiliate_links(blog_id)
            if not links_result["success"]:
                return links_result
                
            links = links_result["links"]
            
            # If no links, return empty suggestions
            if not links:
                return {
                    "success": True,
                    "suggestions": [],
                    "message": "No affiliate links available for this blog"
                }
            
            # Simple keyword matching for now
            # In a real implementation, this would use more sophisticated NLP
            suggestions = []
            
            for link in links:
                product_name = link["product_name"].lower()
                product_keywords = self._extract_keywords(product_name)
                
                # Check if any product keywords appear in content
                for keyword in product_keywords:
                    if keyword and len(keyword) > 3 and keyword.lower() in content.lower():
                        # Found a match
                        suggestion = {
                            "link_id": link["id"],
                            "product_name": link["product_name"],
                            "network": link["network"],
                            "affiliate_url": link["affiliate_url"],
                            "keyword": keyword,
                            "relevance": "medium"  # Simple relevance score
                        }
                        
                        # Check for exact product name match (higher relevance)
                        if product_name.lower() in content.lower():
                            suggestion["relevance"] = "high"
                            
                        suggestions.append(suggestion)
                        break  # Only add one suggestion per link
            
            # Remove duplicates and sort by relevance
            unique_suggestions = {}
            for suggestion in suggestions:
                link_id = suggestion["link_id"]
                if link_id not in unique_suggestions or suggestion["relevance"] == "high":
                    unique_suggestions[link_id] = suggestion
                    
            sorted_suggestions = list(unique_suggestions.values())
            sorted_suggestions.sort(key=lambda x: 0 if x["relevance"] == "high" else 1)
            
            return {
                "success": True,
                "suggestions": sorted_suggestions,
                "count": len(sorted_suggestions)
            }
        except Exception as e:
            logger.error(f"Error suggesting affiliate links: {str(e)}")
            return {
                "success": False,
                "error": f"Error suggesting affiliate links: {str(e)}"
            }
    
    def suggest_product_placement(self, blog_id, product_type=None):
        """
        Suggest products to promote on a blog based on content and audience
        
        Args:
            blog_id (str): ID of the blog
            product_type (str, optional): Type of product to suggest
            
        Returns:
            dict: Operation result with product suggestions
        """
        if not self.affiliate_service:
            return {
                "success": False,
                "error": "Affiliate service is not available"
            }
            
        try:
            # Get blog details
            blog = self._get_blog_by_id(blog_id)
            if not blog:
                return {
                    "success": False,
                    "error": f"Blog not found with ID: {blog_id}"
                }
            
            # Get blog theme and topics
            theme = blog.get("theme", "")
            topics = blog.get("topics", [])
            
            # In a real implementation, this would use more sophisticated
            # matching algorithms and product databases or API calls to networks
            
            # For now, provide some generic suggestions based on theme
            suggestions = []
            
            if "tech" in theme.lower() or any("tech" in topic.lower() for topic in topics):
                suggestions.append({
                    "product_type": "Electronics",
                    "product_examples": ["Laptops", "Smartphones", "Headphones"],
                    "recommended_networks": ["amazon", "commission_junction"],
                    "relevance": "high"
                })
                
            if "food" in theme.lower() or "cook" in theme.lower() or any(t in [topic.lower() for topic in topics] for t in ["food", "cook", "recipe"]):
                suggestions.append({
                    "product_type": "Kitchen",
                    "product_examples": ["Cookware", "Appliances", "Meal Kits"],
                    "recommended_networks": ["amazon", "shareasale"],
                    "relevance": "high"
                })
                
            if "travel" in theme.lower() or any("travel" in topic.lower() for topic in topics):
                suggestions.append({
                    "product_type": "Travel",
                    "product_examples": ["Luggage", "Hotel Bookings", "Travel Insurance"],
                    "recommended_networks": ["commission_junction", "awin"],
                    "relevance": "high"
                })
                
            if "fashion" in theme.lower() or "style" in theme.lower() or any(t in [topic.lower() for topic in topics] for t in ["fashion", "clothing", "style"]):
                suggestions.append({
                    "product_type": "Fashion",
                    "product_examples": ["Clothing", "Accessories", "Shoes"],
                    "recommended_networks": ["amazon", "awin", "shareasale"],
                    "relevance": "high"
                })
                
            # Add some generic suggestions if no specific ones found
            if not suggestions:
                suggestions.append({
                    "product_type": "Books",
                    "product_examples": ["Books related to blog topics", "E-books", "Audiobooks"],
                    "recommended_networks": ["amazon"],
                    "relevance": "medium"
                })
                
                suggestions.append({
                    "product_type": "Software",
                    "product_examples": ["Productivity Apps", "Subscription Services", "Tools"],
                    "recommended_networks": ["shareasale", "impact_radius"],
                    "relevance": "medium"
                })
            
            # Filter by product type if specified
            if product_type:
                suggestions = [s for s in suggestions if product_type.lower() in s["product_type"].lower()]
            
            return {
                "success": True,
                "blog_id": blog_id,
                "blog_name": blog.get("name", ""),
                "theme": theme,
                "topics": topics,
                "suggestions": suggestions,
                "count": len(suggestions)
            }
        except Exception as e:
            logger.error(f"Error suggesting product placement: {str(e)}")
            return {
                "success": False,
                "error": f"Error suggesting product placement: {str(e)}"
            }
    
    # ===========================================================================
    # Helper Methods
    # ===========================================================================
    
    def _validate_url(self, url):
        """Validate a URL"""
        try:
            result = urlparse(url)
            return all([result.scheme, result.netloc])
        except:
            return False
    
    def _extract_keywords(self, text):
        """Extract keywords from text"""
        # Remove non-alphanumeric characters
        clean_text = re.sub(r'[^\w\s]', ' ', text)
        
        # Split into words
        words = clean_text.split()
        
        # Remove duplicates and short words
        keywords = set(word for word in words if len(word) > 3)
        
        return list(keywords)
    
    def _get_blog_by_id(self, blog_id):
        """
        Get blog details by ID
        
        Args:
            blog_id (str): ID of the blog
            
        Returns:
            dict: Blog details or None if not found
        """
        try:
            if self.storage_service:
                # Try to load blog config from storage
                blog_config_path = f"data/blogs/{blog_id}/config.json"
                
                if self.storage_service.file_exists(blog_config_path):
                    blog_config = self.storage_service.get_local_json(blog_config_path)
                    blog_config["id"] = blog_id
                    return blog_config
            else:
                # Fallback to direct file access
                blog_config_path = f"data/blogs/{blog_id}/config.json"
                
                if os.path.exists(blog_config_path):
                    with open(blog_config_path, 'r') as f:
                        blog_config = json.load(f)
                        blog_config["id"] = blog_id
                        return blog_config
            
            logger.warning(f"Blog config not found for ID: {blog_id}")
            return None
        except Exception as e:
            logger.error(f"Error loading blog config: {str(e)}")
            return None