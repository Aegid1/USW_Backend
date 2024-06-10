from fastapi import APIRouter, Depends, HTTPException
from app.services.OpenAIService import OpenAIService
from app.services.MediaService import DocumentType
from app.utils.batch_utils import get_document_type

router = APIRouter()


@router.post("/batch/{batch_name}")
def send_batch(batch_name: str,
               open_ai_service: OpenAIService = Depends()):
    open_ai_service.send_batch(batch_name)


@router.get("/batch/{batch_id}/{batch_type}")
def retrieve_batch(batch_id, batch_type: DocumentType = Depends(get_document_type),
                   open_ai_service: OpenAIService = Depends()):
    open_ai_service.retrieve_batch_content(batch_id, batch_type)
