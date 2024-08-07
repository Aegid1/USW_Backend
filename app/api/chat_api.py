from fastapi import APIRouter, Depends
from app.services.OpenAIService import OpenAIService
import time

router = APIRouter()

def get_open_ai_service():
    """
    Get an instance of OpenAIService.

    Returns:
        OpenAIService: An instance of OpenAIService.
    """

    return OpenAIService


@router.post("/chat", status_code=201)
async def create_thread_id(open_ai_service: OpenAIService = Depends()):
    """
    Create a new chat thread using OpenAIService.

    Parameters:
        open_ai_service (OpenAIService): The OpenAI service instance.

    Returns:
        str: The created thread ID.
    """

    thread_id = open_ai_service.create_thread()
    return thread_id


@router.post("/chat/{thread_id}", status_code=200)
async def chat(thread_id, message: dict, open_ai_service: OpenAIService = Depends()):
    """
    Send a message to an existing chat thread and process the response.

    Parameters:
        thread_id (str): The ID of the chat thread.
        message (dict): The message to be sent, containing text.
        open_ai_service (OpenAIService): The OpenAI service instance.

    Returns:
        dict: A dictionary containing the response text and whether a visualization is given.
    """

    start_time = time.time()
    analysis_performed = False
    message_text = message.get("text", "")

    message = open_ai_service.send_message_to_thread(thread_id, message_text)

    run = open_ai_service.execute_thread(thread_id)

    while run.status not in ['completed', 'failed']:
        print(run.status)
        time.sleep(1)
        run = open_ai_service.retrieve_execution(thread_id, run.id)
        if run.status == 'requires_action':
            run = open_ai_service.submit_tool_outputs(thread_id, run.id, run.required_action.submit_tool_outputs.tool_calls)
            analysis_performed = True

    time.sleep(1)
    messages = open_ai_service.retrieve_messages_from_thread(thread_id)

    #is needed for checking, whether a visualization is given or needed
    if analysis_performed:
        print("Code execution time: ")
        print(time.time() - start_time)

        return {
            #TODO when no success of visualizaton than it needs to be set to False even if an analysis is performed
            "text": messages.data[0].content[0].text.value,
            "visualization_given": True
        }

    return {
        "text": messages.data[0].content[0].text.value,
        "visualization_given": False
    }

