import logging
import json
import os
import time
import azure.functions as func
from ..shared.research_service import ResearchService
from ..shared.storage_service import StorageService

def main(inputBlob: func.InputStream, outputBlob: func.Out[str]) -> None:
    """
    Blob trigger that processes a blog task.
    This function is triggered when a new .run file is created in the generated folder.
    It performs research on trending topics related to the blog theme.
    
    Parameters:
        inputBlob: The input blob that triggered this function
        outputBlob: Output binding for the research results
    """
    # Set up logging
    logger = logging.getLogger('ResearchTopic')
    logger.info(f'ResearchTopic function triggered by blob: {inputBlob.name}')
    
    # Initialize services
    storage_service = StorageService()
    research_service = ResearchService()
    
    # Extract runId from the blob name
    try:
        # Path format: generated/{runId}/.run
        path_parts = inputBlob.name.split('/')
        run_id = path_parts[1]
        logger.info(f'Processing run ID: {run_id}')
    except Exception as e:
        logger.error(f'Error extracting run ID from blob name: {str(e)}')
        return
    
    # Check if research.json already exists (idempotency)
    research_path = f'generated/{run_id}/research.json'
    existing_research = storage_service.get_blob('', research_path)
    if existing_research:
        logger.info(f'Research data already exists for run ID: {run_id}, skipping')
        return
    
    # Read topics.json to get the focus topics for the blog
    try:
        topics_data = storage_service.get_blob('', 'topics.json')
        if not topics_data:
            logger.error('topics.json not found')
            return
        topics = json.loads(topics_data)
    except Exception as e:
        logger.error(f'Error reading topics.json: {str(e)}')
        return
    
    # Read theme.json to get the blog's theme
    try:
        theme_data = storage_service.get_blob('', 'theme.json')
        if not theme_data:
            logger.error('theme.json not found')
            return
        theme = json.loads(theme_data)
    except Exception as e:
        logger.error(f'Error reading theme.json: {str(e)}')
        return
    
    # Extract theme and target audience information
    theme_description = theme.get('description', '')
    target_audience = theme.get('target_audience', 'general')
    region = theme.get('region', 'US')
    
    # Research trending topics related to the blog's theme and topics
    max_retries = 3
    results = []
    
    for topic in topics:
        for attempt in range(max_retries):
            try:
                logger.info(f'Researching topic: {topic}')
                research_results = research_service.research_topics(
                    theme=topic,
                    target_audience=target_audience,
                    region=region
                )
                
                if research_results:
                    results.extend(research_results)
                
                # Successful research, break the retry loop
                break
            except Exception as e:
                logger.error(f'Error researching topic {topic} (attempt {attempt+1}/{max_retries}): {str(e)}')
                if attempt < max_retries - 1:
                    # Exponential backoff
                    backoff_time = 0.2 * (2 ** attempt)
                    time.sleep(backoff_time)
                else:
                    logger.error(f'All retries failed for topic: {topic}')
    
    # Combine research results
    research_data = {
        'runId': run_id,
        'topics': topics,
        'theme': theme_description,
        'research_results': results
    }
    
    # Write the research data to the output blob
    outputBlob.set(json.dumps(research_data, indent=2))
    logger.info(f'Research data for run ID: {run_id} successfully written')