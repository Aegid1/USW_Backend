from fastapi import APIRouter, Depends, HTTPException
from app.services.OpenAIService import OpenAIService
from app.services.BatchApiService import BatchApiService
from app.services.MediaService import DocumentType
from app.utils.batch_utils import get_document_type

router = APIRouter()


@router.post("/batch/{batch_name}")
def send_batch(batch_name: str, batch_api_service: BatchApiService = Depends()):
    """
    Send a batch of documents to the OpenAI service.

    Parameters:
        batch_name (str): The name of the batch to be sent.
        batch_api_service (OpenAIService): The OpenAI service instance.

    Returns:
        None
    """
    batch_api_service.send_batch(batch_name)


@router.get("/batch/status/{batch_id}")
def check_batch_status(batch_id: str, batch_api_service: BatchApiService = Depends()):
    """
    Check the status of a specific batch.

    Parameters:
        batch_id (str): The ID of the batch to check the status of.
        batch_api_service (OpenAIService): The OpenAI service instance.

    Returns:
        dict: The status of the batch.
    """
    return batch_api_service.check_batch_status(batch_id)


@router.get("/batch/retrieval/{batch_type}")
def retrieve_batch(batch_type: DocumentType = Depends(get_document_type),
                   batch_api_service: BatchApiService = Depends()):
    """
    Retrieve the content of batches and delete the batch files, where the ids of the batches are stored -> no usage needed anymore

    Parameters:
        batch_type (DocumentType): The type of document to retrieve.
        batch_api_service (OpenAIService): The OpenAI service instance.

    Returns:
        None
    """
    batch_ids = batch_api_service.get_batch_ids(batch_type)
    for batch_id in batch_ids:
        batch_api_service.retrieve_batch_content(batch_id, batch_type)

    batch_api_service.delete_batch_file(batch_type)
