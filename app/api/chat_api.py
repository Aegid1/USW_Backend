import json
import time

from fastapi import APIRouter, Depends
from app.services.ChatService import ChatService
from app.services.OpenAIService import OpenAIService
from app.utils.analysis_utils import is_analysis_pending
import time

router = APIRouter()


def get_chat_service():
    return ChatService()


def get_open_ai_service():
    return OpenAIService


@router.post("/chat", status_code=201)
async def create_thread_id(open_ai_service: OpenAIService = Depends()):
    thread_id = open_ai_service.create_thread()
    return thread_id


@router.post("/chat/{thread_id}", status_code=200)
async def chat(thread_id, message: dict, open_ai_service: OpenAIService = Depends()):

    start_time = time.time()
    analysis_performed = False
    message_text = message.get("text", "")

    #send message to thread
    message = open_ai_service.send_message_to_thread(thread_id, message_text)

    #run thread with the assigned message
    run = open_ai_service.execute_thread(thread_id)

    #check if its a normal request or needs more actions
    while run.status not in ['completed', 'failed']:
        print(run.status)
        time.sleep(1)
        run = open_ai_service.retrieve_execution(thread_id, run.id)
        if run.status == 'requires_action':
            run = open_ai_service.submit_tool_outputs(thread_id, run.id, run.required_action.submit_tool_outputs.tool_calls)
            analysis_performed = True

    #TODO this is currently only hard coded
    if analysis_performed:
        return "This is the result: "

    time.sleep(1)

    messages = open_ai_service.retrieve_messages_from_thread(thread_id)
    print("Code execution time: ")
    print(time.time() - start_time)
    return messages.data[0].content[0].text.value
