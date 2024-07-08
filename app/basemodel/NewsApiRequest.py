from pydantic import BaseModel

class NewsApiRequest(BaseModel):
    start_date: str
    end_date: str
    topic: str
    page_number: int