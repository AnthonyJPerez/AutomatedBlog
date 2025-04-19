"""
Content visualization utilities for content analysis
This module provides functions for generating visualizations such as
word clouds, sentiment analysis charts, and keyword frequency graphs.
"""

import os
import base64
import logging
from io import BytesIO
import matplotlib.pyplot as plt
import seaborn as sns
from wordcloud import WordCloud
import pandas as pd
import numpy as np

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ContentVisualizer:
    """Generate visualizations for content analysis"""
    
    def __init__(self, width=800, height=400, dpi=100):
        """
        Initialize the ContentVisualizer
        
        Args:
            width (int, optional): Width of visualizations in pixels
            height (int, optional): Height of visualizations in pixels
            dpi (int, optional): DPI for visualizations
        """
        self.width = width
        self.height = height
        self.dpi = dpi
        
        # Set default style for charts
        sns.set_style("darkgrid")
        
    def generate_wordcloud(self, text, mask=None, background_color='black', colormap='viridis', max_words=200):
        """
        Generate a word cloud from text
        
        Args:
            text (str): Text to visualize
            mask (numpy.ndarray, optional): Image mask for word cloud
            background_color (str, optional): Background color
            colormap (str, optional): Matplotlib colormap name
            max_words (int, optional): Maximum number of words
            
        Returns:
            str: Base64 encoded PNG image
        """
        try:
            # Create word cloud
            wordcloud = WordCloud(
                width=self.width, 
                height=self.height,
                background_color=background_color,
                colormap=colormap,
                max_words=max_words,
                mask=mask,
                contour_width=1,
                contour_color='steelblue'
            ).generate(text)
            
            # Generate image
            plt.figure(figsize=(self.width/self.dpi, self.height/self.dpi), dpi=self.dpi)
            plt.imshow(wordcloud, interpolation='bilinear')
            plt.axis("off")
            plt.tight_layout(pad=0)
            
            # Convert to base64
            buffer = BytesIO()
            plt.savefig(buffer, format='png')
            plt.close()
            
            # Encode
            buffer.seek(0)
            image_data = base64.b64encode(buffer.getvalue()).decode('utf-8')
            return image_data
            
        except Exception as e:
            logger.error(f"Error generating word cloud: {str(e)}")
            return None
    
    def visualize_keyword_frequency(self, keywords, title="Keyword Frequency"):
        """
        Create a bar chart of keyword frequencies
        
        Args:
            keywords (list): List of (keyword, count) tuples
            title (str, optional): Chart title
            
        Returns:
            str: Base64 encoded PNG image
        """
        try:
            # Convert keywords to DataFrame
            if not keywords:
                return None
                
            data = pd.DataFrame(keywords, columns=['Keyword', 'Frequency'])
            
            # Sort by frequency
            data = data.sort_values('Frequency', ascending=False)
            
            # Create figure
            plt.figure(figsize=(self.width/self.dpi, self.height/self.dpi), dpi=self.dpi)
            
            # Create bar chart
            ax = sns.barplot(x='Frequency', y='Keyword', data=data, palette='viridis')
            
            # Customize chart
            plt.title(title, fontsize=16)
            plt.xlabel('Frequency', fontsize=12)
            plt.ylabel('Keyword', fontsize=12)
            plt.tight_layout()
            
            # Convert to base64
            buffer = BytesIO()
            plt.savefig(buffer, format='png')
            plt.close()
            
            # Encode
            buffer.seek(0)
            image_data = base64.b64encode(buffer.getvalue()).decode('utf-8')
            return image_data
            
        except Exception as e:
            logger.error(f"Error generating keyword frequency chart: {str(e)}")
            return None
    
    def visualize_sentiment_analysis(self, sentiment_data, title="Sentiment Analysis"):
        """
        Create a gauge chart for sentiment analysis
        
        Args:
            sentiment_data (dict): Sentiment data with 'polarity' and 'subjectivity'
            title (str, optional): Chart title
            
        Returns:
            str: Base64 encoded PNG image
        """
        try:
            # Extract values
            polarity = sentiment_data.get('polarity', 0)
            subjectivity = sentiment_data.get('subjectivity', 0)
            
            # Create a gauge chart for sentiment
            plt.figure(figsize=(self.width/self.dpi, self.height/self.dpi), dpi=self.dpi)
            
            # Create a half-circle gauge for polarity
            ax = plt.subplot(1, 2, 1, polar=True)
            
            # Set the gauge range from -1 to 1 (polarity range)
            theta = np.linspace(0, np.pi, 100)
            
            # Draw the background gradient
            ax.barbs([0], [0], width=0.1)
            
            # Draw the gauge 
            polarity_normalized = (polarity + 1) / 2  # Normalize to 0-1 range
            polarity_color = plt.cm.RdYlGn(polarity_normalized)
            
            ax.bar(np.pi/2, 0.9, width=np.pi, bottom=0.1, color='lightgray', alpha=0.3)
            ax.bar(np.pi/2, 0.9 * polarity_normalized, width=np.pi, bottom=0.1, color=polarity_color)
            
            # Add labels
            ax.text(0, 0.1, "Negative", ha='center', va='bottom', size=12)
            ax.text(np.pi, 0.1, "Positive", ha='center', va='bottom', size=12)
            ax.text(np.pi/2, 0.6, f"{polarity:.2f}", ha='center', va='center', size=18, fontweight='bold')
            ax.text(np.pi/2, 0.3, "Polarity", ha='center', va='center', size=14)
            
            # Remove unnecessary elements
            ax.set_yticks([])
            ax.set_xticks([])
            ax.spines['polar'].set_visible(False)
            
            # Create a gauge for subjectivity
            ax2 = plt.subplot(1, 2, 2, polar=True)
            
            # Draw the background for subjectivity gauge (0 to 1 range)
            subjectivity_color = plt.cm.Blues(subjectivity)
            
            ax2.bar(np.pi/2, 0.9, width=np.pi, bottom=0.1, color='lightgray', alpha=0.3)
            ax2.bar(np.pi/2, 0.9 * subjectivity, width=np.pi, bottom=0.1, color=subjectivity_color)
            
            # Add labels
            ax2.text(0, 0.1, "Objective", ha='center', va='bottom', size=12)
            ax2.text(np.pi, 0.1, "Subjective", ha='center', va='bottom', size=12)
            ax2.text(np.pi/2, 0.6, f"{subjectivity:.2f}", ha='center', va='center', size=18, fontweight='bold')
            ax2.text(np.pi/2, 0.3, "Subjectivity", ha='center', va='center', size=14)
            
            # Remove unnecessary elements
            ax2.set_yticks([])
            ax2.set_xticks([])
            ax2.spines['polar'].set_visible(False)
            
            # Add title
            plt.suptitle(title, fontsize=16, y=0.95)
            plt.tight_layout()
            
            # Convert to base64
            buffer = BytesIO()
            plt.savefig(buffer, format='png')
            plt.close()
            
            # Encode
            buffer.seek(0)
            image_data = base64.b64encode(buffer.getvalue()).decode('utf-8')
            return image_data
            
        except Exception as e:
            logger.error(f"Error generating sentiment visualization: {str(e)}")
            return None
    
    def visualize_topic_distribution(self, topics):
        """
        Create a pie chart of topic distribution
        
        Args:
            topics (dict): Dictionary of topic -> percentage
            
        Returns:
            str: Base64 encoded PNG image
        """
        try:
            # Create figure
            plt.figure(figsize=(self.width/self.dpi, self.height/self.dpi), dpi=self.dpi)
            
            # Create pie chart
            labels = list(topics.keys())
            sizes = list(topics.values())
            
            # Use a custom colormap
            cmap = plt.cm.get_cmap('tab20')
            colors = [cmap(i) for i in np.linspace(0, 1, len(labels))]
            
            # Create pie chart with percentage labels
            plt.pie(sizes, labels=labels, autopct='%1.1f%%', startangle=90, colors=colors, 
                   wedgeprops={'edgecolor': 'w', 'linewidth': 1})
            
            # Equal aspect ratio ensures that pie is drawn as a circle
            plt.axis('equal')
            plt.title('Topic Distribution', fontsize=16)
            plt.tight_layout()
            
            # Convert to base64
            buffer = BytesIO()
            plt.savefig(buffer, format='png')
            plt.close()
            
            # Encode
            buffer.seek(0)
            image_data = base64.b64encode(buffer.getvalue()).decode('utf-8')
            return image_data
            
        except Exception as e:
            logger.error(f"Error generating topic distribution chart: {str(e)}")
            return None

# Simple utility functions
def generate_wordcloud_from_text(text):
    """
    Simple utility function to generate a word cloud from text
    
    Args:
        text (str): Text to visualize
        
    Returns:
        str: Base64 encoded PNG image
    """
    visualizer = ContentVisualizer()
    return visualizer.generate_wordcloud(text)

def generate_sentiment_chart(sentiment_data):
    """
    Simple utility function to generate a sentiment gauge chart
    
    Args:
        sentiment_data (dict): Sentiment data with 'polarity' and 'subjectivity'
        
    Returns:
        str: Base64 encoded PNG image
    """
    visualizer = ContentVisualizer()
    return visualizer.visualize_sentiment_analysis(sentiment_data)