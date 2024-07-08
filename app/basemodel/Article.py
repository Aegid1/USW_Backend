from pydantic import BaseModel
from app.basemodel.ArticleMetadata import ArticleMetadata
class Article(BaseModel):
    content: str
    metadata: ArticleMetadata