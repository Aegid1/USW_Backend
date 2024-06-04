from fastapi import APIRouter, Depends
from ..services.chat_service import chat_service
from ..services.open_ai_service import open_ai_service

router = APIRouter()

def get_chat_service():
    return chat_service()

def get_open_ai_service():
    return open_ai_service

@router.post("/chat")
async def create_thread_id(open_ai_service: open_ai_service =Depends()):
    thread_id = open_ai_service.create_thread_id()
    return thread_id

@router.post("/chat/{thread_id}")
async def chat(thread_id, message: dict):
