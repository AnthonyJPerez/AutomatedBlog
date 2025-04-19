import logging
import json
import azure.functions as func
from azure.storage.blob import BlobServiceClient, BlobClient, ContainerClient
from azure.identity import DefaultAzureCredential

def main(req: func.HttpRequest, outputBlob: func.Out[str]) -> func.HttpResponse:
    """
    HTTP trigger for logging results of the content generation pipeline.
    This function accepts JSON results and writes them to blob storage.
    
    Parameters:
        req: The HTTP request
        outputBlob: Output binding for the results.json file
    """
    # Set up logging
    logger = logging.getLogger('ResultsLogger')
    logger.info('ResultsLogger function triggered')
    
    # Get runId from route parameter
    run_id = req.route_params.get('runId')
    if not run_id:
        return func.HttpResponse(
            "Please provide a runId in the route parameter.",
            status_code=400
        )
    
    logger.info(f'Processing run ID: {run_id}')
    
    # Get request body
    try:
        req_body = req.get_json()
    except ValueError:
        return func.HttpResponse(
            "Please pass a valid JSON in the request body.",
            status_code=400
        )
    
    # Add runId to results if not present
    if 'runId' not in req_body:
        req_body['runId'] = run_id
    
    # Check if results already exist (idempotency)
    try:
        connection_string = get_storage_connection_string()
        if connection_string:
            blob_service_client = BlobServiceClient.from_connection_string(connection_string)
            blob_client = blob_service_client.get_blob_client(
                container="generated",
                blob=f"{run_id}/results.json"
            )
            
            if blob_client.exists():
                logger.info(f'Results already exist for run ID: {run_id}, updating')
    except Exception as e:
        logger.warning(f'Error checking if results exist: {str(e)}')
    
    # Add metrics to results
    req_body.setdefault('metrics', {})
    if 'content' in req_body:
        word_count = len(req_body['content'].split())
        req_body['metrics']['contentWordCount'] = word_count
    
    # If latencyMs not provided, use 0
    req_body['metrics'].setdefault('apiLatencyMs', 0)
    
    # Write results to blob
    try:
        outputBlob.set(json.dumps(req_body, indent=2))
        logger.info(f'Results for run ID: {run_id} written')
        
        return func.HttpResponse(
            json.dumps({"status": "success", "message": f"Results for run ID: {run_id} logged"}),
            mimetype="application/json",
            status_code=200
        )
    except Exception as e:
        logger.error(f'Error writing results: {str(e)}')
        return func.HttpResponse(
            json.dumps({"status": "error", "message": f"Error writing results: {str(e)}"}),
            mimetype="application/json",
            status_code=500
        )

def get_storage_connection_string():
    """Get Azure Storage connection string"""
    # First try to get from environment variable
    import os
    connection_string = os.environ.get("AzureWebJobsStorage")
    
    if connection_string:
        return connection_string
    
    # If not in environment, try to construct from account name and key
    account_name = os.environ.get("STORAGE_ACCOUNT_NAME")
    account_key = os.environ.get("STORAGE_ACCOUNT_KEY")
    
    if account_name and account_key:
        return f"DefaultEndpointsProtocol=https;AccountName={account_name};AccountKey={account_key};EndpointSuffix=core.windows.net"
    
    return None