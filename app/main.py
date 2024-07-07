import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.chat_api import router as chat_router
from app.api.media_api import router as media_router
from app.api.openai_api import router as openai_router

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["*"],
)

app.include_router(chat_router, prefix="/api/v1")
app.include_router(media_router, prefix="/api/v1")
app.include_router(openai_router, prefix="/api/v1")


if __name__ == "__main__":
    uvicorn.run("app.main:app", host="localhost", port=4000)
