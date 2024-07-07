# Import necessary modules and classes from FastAPI and custom services
from fastapi import APIRouter, Depends
from app.services.ChatService import ChatService
from app.services.OpenAIService import OpenAIService
import time

# Create a router for the API endpoints
router = APIRouter()

# Dependency function to get an instance of ChatService
def get_chat_service():
    """
    Get an instance of ChatService.

    Returns:
        ChatService: An instance of ChatService.
    """
    return ChatService()

# Dependency function to get an instance of OpenAIService
def get_open_ai_service():
    """
    Get an instance of OpenAIService.

    Returns:
        OpenAIService: An instance of OpenAIService.
    """
    return OpenAIService()

# Endpoint to create a new chat thread
@router.post("/chat", status_code=201)
async def create_thread_id(open_ai_service: OpenAIService = Depends()):
    """
    Create a new chat thread using OpenAIService.

    Parameters:
        open_ai_service (OpenAIService): The OpenAI service instance.

    Returns:
        str: The created thread ID.
    """
    # Create a new thread using OpenAI service
    thread_id = open_ai_service.create_thread()
    # Return the created thread ID
    return thread_id

# Endpoint to send a message to an existing chat thread
@router.post("/chat/{thread_id}", status_code=200)
async def chat(thread_id: str, message: dict, open_ai_service: OpenAIService = Depends()):
    """
    Send a message to an existing chat thread and process the response.

    Parameters:
        thread_id (str): The ID of the chat thread.
        message (dict): The message to be sent, containing text.
        open_ai_service (OpenAIService): The OpenAI service instance.

    Returns:
        dict: A dictionary containing the response text and whether a visualization is given.
    """
    # Record the start time for code execution
    start_time = time.time()
    # Variable to track if analysis was performed
    analysis_performed = False
    # Extract text from the received message
    message_text = message.get("text", "")

    # Send the message to the thread using OpenAI service
    message = open_ai_service.send_message_to_thread(thread_id, message_text)

    # Execute the thread using OpenAI service
    run = open_ai_service.execute_thread(thread_id)

    # Wait for the execution to complete or fail
    while run.status not in ['completed', 'failed']:
        print(run.status)
        # Wait for one second
        time.sleep(1)
        # Retrieve the current status of the execution
        run = open_ai_service.retrieve_execution(thread_id, run.id)
        if run.status == 'requires_action':
            # If an action is required, perform it
            run = open_ai_service.submit_tool_outputs(thread_id, run.id, run.required_action.submit_tool_outputs.tool_calls)
            analysis_performed = True

    # If analysis was performed, print the execution time
    if analysis_performed:
        print("Code execution time: ")
        print(time.time() - start_time)

        # Return the result indicating that a visualization was given
        return {
            "text": "Here is the result ",
            "visualization_given": True
        }

    # Wait for one second (potentially unnecessary)
    time.sleep(1)

    # Retrieve messages from the thread
    messages = open_ai_service.retrieve_messages_from_thread(thread_id)

    # Return the first message from the retrieved messages
    return {
        "text": messages.data[0].content[0].text.value,
        "visualization_given": False
    }
