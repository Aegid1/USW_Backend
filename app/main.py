import uvicorn
from fastapi import FastAPI
from app.api.chat_api import router as chat_router
from app.api.media_api import router as media_router

app = FastAPI()

app.include_router(chat_router, prefix="/api/v1")
app.include_router(media_router, prefix="/api/v1")

if __name__ == "__main__":
    uvicorn.run("app.main:app", host="localhost", port=4000)
