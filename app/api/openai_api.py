from fastapi import APIRouter, Depends, HTTPException
from app.services.OpenAIService import OpenAIService
from app.services.MediaService import DocumentType
from app.utils.batch_utils import get_document_type

router = APIRouter()


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


@router.get("/batch/retrieval/{batch_type}")
def retrieve_batch(batch_type: DocumentType = Depends(get_document_type),
                   open_ai_service: OpenAIService = Depends()):
    """
    Retrieve the content of batches and delete the batch files, where the ids of the batches are stored -> no usage needed anymore

    Parameters:
        batch_type (DocumentType): The type of document to retrieve.
        open_ai_service (OpenAIService): The OpenAI service instance.

    Returns:
        None
    """
    batch_ids = OpenAIService.get_batch_ids(batch_type)
    for batch_id in batch_ids:
        open_ai_service.retrieve_batch_content(batch_id, batch_type)

    OpenAIService.delete_batch_file(batch_type)
