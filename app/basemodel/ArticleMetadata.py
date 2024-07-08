from pydantic import BaseModel

class ArticleMetadata(BaseModel):
    keywords: str
    title: str
    author: str
    published: str
    url: str