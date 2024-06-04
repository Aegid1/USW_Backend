import uvicorn
from fastapi import FastAPI
from api.chat_api import router as chat_router
from api.media_api import router as media_router

app = FastAPI()

app.include_router(chat_router, prefix="/api/v1")
app.include_router(media_router, prefix="/api/v1")

app = FastAPI()

if __name__ == "__main__":
    uvicorn.run("main:app", host="localhost", port=4000)
