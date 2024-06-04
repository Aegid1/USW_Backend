from fastapi import APIRouter

router = APIRouter()

@router.post("/chat")
async def create_thread_id():


@router.post("/chat/{thread_id}")
async def chat(thread_id, message: dict):
