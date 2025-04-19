import logging
import os
import json
import datetime
import azure.functions as func
from ..shared.storage_service import StorageService

def main(mytimer: func.TimerRequest, outputBlob: func.Out[str]) -> None:
    """
    Timer trigger that creates a new run folder.
    This function runs on a schedule defined by frequency.json and creates an empty blob to trigger the pipeline.
    
    Parameters:
        mytimer: The timer trigger that invoked this function
        outputBlob: Output binding to the .run blob that will trigger the next function
    """
    # Set up logging
    logger = logging.getLogger('CreateRunFolder')
    logger.info('CreateRunFolder function triggered')
    
    # Initialize storage service for reading configuration
    storage_service = StorageService()
    
    # Read frequency.json to determine if we should run
    try:
        frequency_data = storage_service.get_blob('', 'frequency.json')
        if not frequency_data:
            logger.warning('frequency.json not found, using default frequency (daily)')
            frequency = {'daily': 1}
        else:
            frequency = json.loads(frequency_data)
    except Exception as e:
        logger.error(f'Error reading frequency.json: {str(e)}')
        frequency = {'daily': 1}
    
    # Check if ready.json exists to gate pipeline execution
    try:
        ready_data = storage_service.get_blob('', 'ready.json')
        if not ready_data:
            logger.warning('ready.json not found, pipeline is not ready to run')
            return
    except Exception as e:
        logger.error(f'Error checking ready.json: {str(e)}')
        return
    
    # Determine run frequency
    daily_runs = frequency.get('daily', 1)
    
    # Check if it's time to run based on frequency
    # For testing, we're always running, but in production this would be controlled by the timer schedule
    if daily_runs > 0:
        # Create a new run folder by writing to the output binding
        # The binding will automatically set the path with the current date/time and a random GUID
        outputBlob.set(json.dumps({"timestamp": datetime.datetime.utcnow().isoformat()}))
        logger.info('Created new run folder')
    else:
        logger.info('No runs scheduled for today based on frequency configuration')