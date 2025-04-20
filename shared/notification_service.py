"""
Notification Service for Multi-Blog Platform

This service handles email notifications for various platform events:
- Affiliate marketing conversions
- New backlinks detected
- Content generation completions
- Blog deployment notifications
"""

import json
import os
import logging
import datetime
import traceback
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail, Email, To, Content, HtmlContent

# Set up logger
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

class NotificationService:
    """Service for sending notifications via email, SMS, etc."""
    
    def __init__(self, storage_service=None):
        """
        Initialize the Notification Service
        
        Args:
            storage_service: Service for storing and retrieving data
        """
        self.storage_service = storage_service
        
        # Initialize email client (SendGrid)
        self.sendgrid_api_key = os.environ.get('SENDGRID_API_KEY')
        self.email_client = None
        
        if self.sendgrid_api_key:
            try:
                self.email_client = SendGridAPIClient(self.sendgrid_api_key)
                logger.info("SendGrid email client initialized")
            except Exception as e:
                logger.warning(f"Could not initialize SendGrid client: {str(e)}")
        else:
            logger.warning("SendGrid API key not provided, email notifications disabled")
        
        # Initialize SMS client (future)
        self.sms_client = None
        
        # Create necessary data directories
        self._setup_directories()
        
        logger.info("Notification Service initialized")
        
    def _setup_directories(self):
        """Create necessary directories for storing notification data"""
        if self.storage_service:
            self.storage_service.ensure_local_directory("data/notifications")
            self.storage_service.ensure_local_directory("data/notifications/templates")
            self.storage_service.ensure_local_directory("data/notifications/logs")
        else:
            # Fallback to direct directory creation
            os.makedirs("data/notifications", exist_ok=True)
            os.makedirs("data/notifications/templates", exist_ok=True)
            os.makedirs("data/notifications/logs", exist_ok=True)
            
        # Create default email templates if they don't exist
        self._create_default_templates()
        
    def _create_default_templates(self):
        """Create default email templates"""
        templates = {
            "affiliate_conversion": {
                "subject": "New Affiliate Conversion: {product_name}",
                "body_html": """
                <h2>New Affiliate Conversion</h2>
                <p>A new conversion has been recorded for your affiliate link.</p>
                <ul>
                    <li><strong>Blog:</strong> {blog_name}</li>
                    <li><strong>Product:</strong> {product_name}</li>
                    <li><strong>Network:</strong> {network}</li>
                    <li><strong>Order ID:</strong> {order_id}</li>
                    <li><strong>Amount:</strong> ${amount}</li>
                    <li><strong>Date:</strong> {date}</li>
                </ul>
                <p>View your affiliate dashboard for more details.</p>
                """
            },
            "new_backlink": {
                "subject": "New Backlink Detected for {blog_name}",
                "body_html": """
                <h2>New Backlink Detected</h2>
                <p>A new backlink has been detected for your blog.</p>
                <ul>
                    <li><strong>Blog:</strong> {blog_name}</li>
                    <li><strong>Source:</strong> {source_url}</li>
                    <li><strong>Target:</strong> {target_url}</li>
                    <li><strong>Anchor Text:</strong> {anchor_text}</li>
                    <li><strong>Detected:</strong> {date}</li>
                </ul>
                <p>View your backlink dashboard for more details.</p>
                """
            },
            "content_generation_complete": {
                "subject": "Content Generation Complete for {blog_name}",
                "body_html": """
                <h2>Content Generation Complete</h2>
                <p>A new content generation run has completed for your blog.</p>
                <ul>
                    <li><strong>Blog:</strong> {blog_name}</li>
                    <li><strong>Topic:</strong> {topic}</li>
                    <li><strong>Run ID:</strong> {run_id}</li>
                    <li><strong>Completed:</strong> {date}</li>
                </ul>
                <p>View and edit the content in your dashboard before publishing.</p>
                """
            },
            "blog_deployment": {
                "subject": "Blog Deployed: {blog_name}",
                "body_html": """
                <h2>Blog Deployment Complete</h2>
                <p>Your blog has been successfully deployed.</p>
                <ul>
                    <li><strong>Blog:</strong> {blog_name}</li>
                    <li><strong>URL:</strong> <a href="{blog_url}">{blog_url}</a></li>
                    <li><strong>Deployed:</strong> {date}</li>
                </ul>
                <p>View your blog dashboard for more details.</p>
                """
            }
        }
        
        for template_name, template_data in templates.items():
            template_path = f"data/notifications/templates/{template_name}.json"
            
            # Check if template exists
            if self.storage_service:
                exists = self.storage_service.file_exists(template_path)
            else:
                exists = os.path.exists(template_path)
                
            if not exists:
                if self.storage_service:
                    self.storage_service.save_local_json(template_path, template_data)
                else:
                    with open(template_path, 'w') as f:
                        json.dump(template_data, f, indent=2)
    
    def get_email_template(self, template_name):
        """
        Get an email template by name
        
        Args:
            template_name (str): Name of the template
            
        Returns:
            dict: Template data or None if not found
        """
        try:
            template_path = f"data/notifications/templates/{template_name}.json"
            
            # Check if template exists
            if self.storage_service:
                exists = self.storage_service.file_exists(template_path)
            else:
                exists = os.path.exists(template_path)
                
            if exists:
                if self.storage_service:
                    return self.storage_service.get_local_json(template_path)
                else:
                    with open(template_path, 'r') as f:
                        return json.load(f)
            else:
                logger.warning(f"Email template not found: {template_name}")
                return None
        except Exception as e:
            logger.error(f"Error getting email template: {str(e)}")
            return None
    
    def update_email_template(self, template_name, template_data):
        """
        Update an email template
        
        Args:
            template_name (str): Name of the template
            template_data (dict): Template data
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            template_path = f"data/notifications/templates/{template_name}.json"
            
            if self.storage_service:
                self.storage_service.save_local_json(template_path, template_data)
            else:
                with open(template_path, 'w') as f:
                    json.dump(template_data, f, indent=2)
                    
            return True
        except Exception as e:
            logger.error(f"Error updating email template: {str(e)}")
            return False
    
    def send_email(self, to_email, subject, html_content, from_email=None):
        """
        Send an email using SendGrid
        
        Args:
            to_email (str): Recipient email address
            subject (str): Email subject
            html_content (str): HTML email content
            from_email (str, optional): Sender email address
            
        Returns:
            dict: Operation result
        """
        if not self.email_client:
            return {
                "success": False,
                "error": "Email client is not initialized"
            }
            
        try:
            # Default from email if not provided
            if not from_email:
                from_email = os.environ.get('DEFAULT_FROM_EMAIL', 'noreply@multiblog.example.com')
                
            # Create message
            message = Mail(
                from_email=from_email,
                to_emails=to_email,
                subject=subject,
                html_content=html_content
            )
            
            # Send email
            response = self.email_client.send(message)
            
            # Log the notification
            self._log_notification("email", {
                "to": to_email,
                "subject": subject,
                "status": response.status_code,
                "timestamp": datetime.datetime.now().isoformat()
            })
            
            return {
                "success": True,
                "message": "Email sent successfully",
                "status_code": response.status_code
            }
        except Exception as e:
            logger.error(f"Error sending email: {str(e)}\n{traceback.format_exc()}")
            
            # Log the failed notification
            self._log_notification("email", {
                "to": to_email,
                "subject": subject,
                "status": "error",
                "error": str(e),
                "timestamp": datetime.datetime.now().isoformat()
            })
            
            return {
                "success": False,
                "error": f"Error sending email: {str(e)}"
            }
    
    def send_template_email(self, to_email, template_name, template_data, from_email=None):
        """
        Send an email using a template
        
        Args:
            to_email (str): Recipient email address
            template_name (str): Name of the template
            template_data (dict): Data to fill the template
            from_email (str, optional): Sender email address
            
        Returns:
            dict: Operation result
        """
        try:
            # Get template
            template = self.get_email_template(template_name)
            if not template:
                return {
                    "success": False,
                    "error": f"Template not found: {template_name}"
                }
                
            # Format subject
            subject = template["subject"].format(**template_data)
            
            # Format body
            html_content = template["body_html"].format(**template_data)
            
            # Send email
            return self.send_email(to_email, subject, html_content, from_email)
        except KeyError as e:
            logger.error(f"Missing template data for key: {str(e)}")
            return {
                "success": False,
                "error": f"Missing template data for key: {str(e)}"
            }
        except Exception as e:
            logger.error(f"Error sending template email: {str(e)}")
            return {
                "success": False,
                "error": f"Error sending template email: {str(e)}"
            }
    
    def notify_affiliate_conversion(self, to_email, conversion_data):
        """
        Send a notification for an affiliate conversion
        
        Args:
            to_email (str): Recipient email address
            conversion_data (dict): Conversion data
            
        Returns:
            dict: Operation result
        """
        try:
            # Ensure date field is in the right format
            if "timestamp" in conversion_data and not "date" in conversion_data:
                try:
                    dt = datetime.datetime.fromisoformat(conversion_data["timestamp"])
                    conversion_data["date"] = dt.strftime("%Y-%m-%d %H:%M:%S")
                except:
                    conversion_data["date"] = conversion_data["timestamp"]
            
            # Send notification
            return self.send_template_email(
                to_email=to_email,
                template_name="affiliate_conversion",
                template_data=conversion_data
            )
        except Exception as e:
            logger.error(f"Error sending affiliate conversion notification: {str(e)}")
            return {
                "success": False,
                "error": f"Error sending affiliate conversion notification: {str(e)}"
            }
    
    def notify_new_backlink(self, to_email, backlink_data):
        """
        Send a notification for a new backlink
        
        Args:
            to_email (str): Recipient email address
            backlink_data (dict): Backlink data
            
        Returns:
            dict: Operation result
        """
        try:
            # Ensure date field is in the right format
            if "detected_at" in backlink_data and not "date" in backlink_data:
                try:
                    dt = datetime.datetime.fromisoformat(backlink_data["detected_at"])
                    backlink_data["date"] = dt.strftime("%Y-%m-%d %H:%M:%S")
                except:
                    backlink_data["date"] = backlink_data["detected_at"]
            
            # Send notification
            return self.send_template_email(
                to_email=to_email,
                template_name="new_backlink",
                template_data=backlink_data
            )
        except Exception as e:
            logger.error(f"Error sending new backlink notification: {str(e)}")
            return {
                "success": False,
                "error": f"Error sending new backlink notification: {str(e)}"
            }
    
    def notify_content_generation_complete(self, to_email, content_data):
        """
        Send a notification for a completed content generation run
        
        Args:
            to_email (str): Recipient email address
            content_data (dict): Content generation data
            
        Returns:
            dict: Operation result
        """
        try:
            # Ensure date field is in the right format
            if "completed_at" in content_data and not "date" in content_data:
                try:
                    dt = datetime.datetime.fromisoformat(content_data["completed_at"])
                    content_data["date"] = dt.strftime("%Y-%m-%d %H:%M:%S")
                except:
                    content_data["date"] = content_data["completed_at"]
            
            # Send notification
            return self.send_template_email(
                to_email=to_email,
                template_name="content_generation_complete",
                template_data=content_data
            )
        except Exception as e:
            logger.error(f"Error sending content generation notification: {str(e)}")
            return {
                "success": False,
                "error": f"Error sending content generation notification: {str(e)}"
            }
    
    def notify_blog_deployment(self, to_email, deployment_data):
        """
        Send a notification for a blog deployment
        
        Args:
            to_email (str): Recipient email address
            deployment_data (dict): Deployment data
            
        Returns:
            dict: Operation result
        """
        try:
            # Ensure date field is in the right format
            if "deployed_at" in deployment_data and not "date" in deployment_data:
                try:
                    dt = datetime.datetime.fromisoformat(deployment_data["deployed_at"])
                    deployment_data["date"] = dt.strftime("%Y-%m-%d %H:%M:%S")
                except:
                    deployment_data["date"] = deployment_data["deployed_at"]
            
            # Send notification
            return self.send_template_email(
                to_email=to_email,
                template_name="blog_deployment",
                template_data=deployment_data
            )
        except Exception as e:
            logger.error(f"Error sending blog deployment notification: {str(e)}")
            return {
                "success": False,
                "error": f"Error sending blog deployment notification: {str(e)}"
            }
    
    def _log_notification(self, notification_type, notification_data):
        """Log a notification to storage"""
        try:
            # Create log entry
            log_entry = {
                "type": notification_type,
                "data": notification_data,
                "timestamp": datetime.datetime.now().isoformat()
            }
            
            # Generate log file name
            log_date = datetime.datetime.now().strftime("%Y%m%d")
            log_file = f"data/notifications/logs/{log_date}.json"
            
            # Load existing log entries
            log_entries = []
            try:
                if self.storage_service:
                    if self.storage_service.file_exists(log_file):
                        log_entries = self.storage_service.get_local_json(log_file)
                else:
                    if os.path.exists(log_file):
                        with open(log_file, 'r') as f:
                            log_entries = json.load(f)
            except:
                # If file doesn't exist or is invalid, start with empty list
                log_entries = []
            
            # Append new log entry
            log_entries.append(log_entry)
            
            # Save updated log entries
            if self.storage_service:
                self.storage_service.save_local_json(log_file, log_entries)
            else:
                with open(log_file, 'w') as f:
                    json.dump(log_entries, f, indent=2)
                    
            return True
        except Exception as e:
            logger.error(f"Error logging notification: {str(e)}")
            return False
    
    def get_notification_logs(self, date=None, notification_type=None, limit=100):
        """
        Get notification logs
        
        Args:
            date (str, optional): Date to get logs for (YYYYMMDD)
            notification_type (str, optional): Type of notification to filter by
            limit (int, optional): Maximum number of logs to return
            
        Returns:
            dict: Notification logs
        """
        try:
            # Determine log file to load
            if date:
                log_files = [f"data/notifications/logs/{date}.json"]
            else:
                # Get all log files, sorted by date (newest first)
                if self.storage_service:
                    log_files = self.storage_service.list_files("data/notifications/logs")
                else:
                    if os.path.exists("data/notifications/logs"):
                        log_files = [os.path.join("data/notifications/logs", f) for f in os.listdir("data/notifications/logs") if f.endswith(".json")]
                    else:
                        log_files = []
                        
                log_files.sort(reverse=True)
            
            # Load log entries
            logs = []
            for log_file in log_files:
                if len(logs) >= limit:
                    break
                    
                try:
                    if self.storage_service:
                        if self.storage_service.file_exists(log_file):
                            file_logs = self.storage_service.get_local_json(log_file)
                            
                            # Filter by notification type if needed
                            if notification_type:
                                file_logs = [log for log in file_logs if log.get("type") == notification_type]
                                
                            logs.extend(file_logs[:limit - len(logs)])
                    else:
                        if os.path.exists(log_file):
                            with open(log_file, 'r') as f:
                                file_logs = json.load(f)
                                
                                # Filter by notification type if needed
                                if notification_type:
                                    file_logs = [log for log in file_logs if log.get("type") == notification_type]
                                    
                                logs.extend(file_logs[:limit - len(logs)])
                except Exception as e:
                    logger.warning(f"Error loading log file {log_file}: {str(e)}")
            
            # Sort logs by timestamp (newest first)
            logs.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
            
            return {
                "success": True,
                "logs": logs[:limit],
                "total_count": len(logs[:limit])
            }
        except Exception as e:
            logger.error(f"Error getting notification logs: {str(e)}")
            return {
                "success": False,
                "error": f"Error getting notification logs: {str(e)}"
            }