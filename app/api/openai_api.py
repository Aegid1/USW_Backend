# Import necessary modules and classes from FastAPI and custom services
from fastapi import APIRouter, Depends, HTTPException
from app.services.OpenAIService import OpenAIService
from app.services.MediaService import DocumentType
from app.utils.batch_utils import get_document_type

# Create a router for the API endpoints
router = APIRouter()


# Endpoint to send a batch of documents
@router.post("/batch/{batch_name}")
def send_batch(batch_name: str, open_ai_service: OpenAIService = Depends()):
    """
    Send a batch of documents to the OpenAI service.

    Parameters:
        batch_name (str): The name of the batch to be sent.
        open_ai_service (OpenAIService): The OpenAI service instance.

    Returns:
        None
    """
    open_ai_service.send_batch(batch_name)


# Endpoint to check the status of a batch
@router.get("/batch/status/{batch_id}")
def check_batch_status(batch_id: str, open_ai_service: OpenAIService = Depends()):
    """
    Check the status of a specific batch.

    Parameters:
        batch_id (str): The ID of the batch to check the status of.
        open_ai_service (OpenAIService): The OpenAI service instance.

    Returns:
        dict: The status of the batch.
    """
    return open_ai_service.check_batch_status(batch_id)


# Endpoint to retrieve and delete batch content based on document type
@router.get("/batch/retrieval/{batch_type}")
def retrieve_batch(batch_type: DocumentType = Depends(get_document_type),
                   open_ai_service: OpenAIService = Depends()):
    """
    Retrieve the content of batches and delete batch files based on document type.

    Parameters:
        batch_type (DocumentType): The type of document to retrieve.
        open_ai_service (OpenAIService): The OpenAI service instance.

    Returns:
        None
    """
    # Get batch IDs of the specified type
    batch_ids = open_ai_service.get_batch_ids(batch_type)
    for batch_id in batch_ids:
        # Retrieve the content of each batch
        open_ai_service.retrieve_batch_content(batch_id, batch_type)

    # Delete the batch files of the specified type
    open_ai_service.delete_batch_file(batch_type)
