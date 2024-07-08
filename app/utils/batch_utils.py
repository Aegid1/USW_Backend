from fastapi import HTTPException

from app.services.MediaService import DocumentType


def __get_document_type(batch_type: str) -> DocumentType:
    try:
        return DocumentType[batch_type]
    except KeyError:
        raise HTTPException(status_code=400, detail=f"Invalid batch_type: {batch_type}")
