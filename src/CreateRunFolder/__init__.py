import logging
import os
import json
import datetime
import uuid
import azure.functions as func
from azure.storage.blob import BlobServiceClient, BlobClient, ContainerClient

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
    
    if mytimer.past_due:
        logger.info('The timer is past due!')
    
    logger.info('CreateRunFolder function triggered at: %s', datetime.datetime.utcnow())
    
    # Check if ready.json exists (gate file)
    try:
        storage_connection_string = os.environ.get("AzureWebJobsStorage")
        if not storage_connection_string:
            logger.error("No storage connection string available")
            return
        
        blob_service_client = BlobServiceClient.from_connection_string(storage_connection_string)
        
        # Check for ready.json
        ready_blob_client = blob_service_client.get_blob_client(
            container="",
            blob="ready.json"
        )
        
        if not ready_blob_client.exists():
            logger.info("ready.json not found, skipping run creation")
            return
        
        # Check frequency settings
        frequency_blob_client = blob_service_client.get_blob_client(
            container="",
            blob="frequency.json"
        )
        
        daily_frequency = 1  # Default to 1 run per day
        
        if frequency_blob_client.exists():
            frequency_data = frequency_blob_client.download_blob().readall().decode('utf-8')
            frequency = json.loads(frequency_data)
            daily_frequency = frequency.get('daily', 1)
        
        # Check if we've already created enough runs for today
        container_client = blob_service_client.get_container_client("generated")
        
        today = datetime.datetime.utcnow().strftime('%Y%m%d')
        blobs = container_client.list_blobs(name_starts_with=f"{today}")
        
        # Count unique run folders for today
        today_runs = set()
        for blob in blobs:
            # Extract run ID from path
            parts = blob.name.split('/')
            if len(parts) >= 2 and parts[0].startswith(today):
                today_runs.add(parts[0])
        
        if len(today_runs) >= daily_frequency:
            logger.info(f"Already created {len(today_runs)} runs today, which meets or exceeds the daily frequency of {daily_frequency}")
            return
        
        # Create a new run ID
        timestamp = datetime.datetime.utcnow().strftime('%Y%m%d_%H%M%S')
        run_guid = str(uuid.uuid4())[:8]  # Short GUID
        run_id = f"{timestamp}_{run_guid}"
        
        # Create the .run blob in the new folder
        run_blob_path = f"generated/{run_id}/.run"
        
        # Check if the .run blob already exists (idempotency)
        run_blob_client = blob_service_client.get_blob_client(
            container="",
            blob=run_blob_path
        )
        
        if run_blob_client.exists():
            logger.info(f"Run folder {run_id} already exists, skipping")
            return
        
        # Create the .run blob
        outputBlob.set("")
        logger.info(f"Created new run folder: {run_id}")
        
    except Exception as e:
        logger.error(f"Error creating run folder: {str(e)}")
        raise