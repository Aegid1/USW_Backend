from fastapi import APIRouter, Depends
from chromadb.utils import embedding_functions
from app.services.MediaService import MediaService
from app.services.NewsApiService import NewsApiService
from app.services.OpenAIService import OpenAIService
from pydantic import BaseModel

router = APIRouter()


class Query(BaseModel):
    query: str


class ArticleMetadata(BaseModel):
    keywords: str
    title: str
    author: str
    published: str
    url: str


class Article(BaseModel):
    content: str
    metadata: ArticleMetadata


def get_media_service():
    return MediaService


@router.post("/createExampleData", status_code=201)
def create_data(media_service: MediaService = Depends()):
    default_ef = embedding_functions.DefaultEmbeddingFunction()

    collection = media_service.get_collection("articles")

    if collection is None:
        collection = media_service.create_collection("articles", default_ef)

    articles = [
        {"id": "1", "title": "Article 1", "content": "Content of article 1",
         "metadata": {
             "keywords": "keyword1_keyword2",
             "title": "testtitle",
             "author": "test2",
             "published": "2024-06-04",
             "url": "https://example.com/article1"
         }},
        {"id": "2", "title": "Article 2", "content": "Content of article 2",
         "metadata": {
             "keywords": "keyword1_keyword2",
             "title": "testtitle",
             "author": "test",
             "published": "2024-06-04",
             "url": "https://example.com/article1"
         }},
    ]
    ids = [article["id"] for article in articles]
    titles = [article["title"] for article in articles]
    contents = [article["content"] for article in articles]
    metadata = [article["metadata"] for article in articles]

    collection.add(
        documents=contents,
        metadatas=metadata,
        ids=ids
    )

    print("Initial state has been created and stored.")


@router.post("/articles/{collection_name}", status_code=201)
def add_article_to_collection(article: Article, collection_name: str, media_service: MediaService = Depends()):
    collection = media_service.get_collection(collection_name)
    media_service.store_article(collection, article.dict())


@router.post("/articles/many/{collection_name}", status_code=201)
def add_multiple_articles_to_collection(articles, collection_name, media_service: MediaService = Depends()):
    collection = media_service.get_collection(collection_name)
    media_service.store_multiple_articles(collection, articles)


# only useful for development purposes, will be deleted in the end
@router.post("/articles/{collection_name}/{number_of_articles}", status_code=200)
def get_articles_from_collection(collection_name, number_of_articles: int, query: Query,
                                 media_service: MediaService = Depends()):
    return media_service.get_articles(number_of_articles, query.query, collection_name)


#will be changed later on, to get the average amount of tokens of x articles
@router.get("/articles/{article_id}")
def get_amount_of_tokens_of_article(article_id: str, media_service: MediaService = Depends()):
    collection = media_service.get_collection("articles")
    article = media_service.get_article_by_id(collection, article_id)

    return media_service.count_token(article.get("documents")[0])

@router.post("/articles/news/{start_date}/{end_date}")
def store_articles_from_news_api(start_date: str,
                                 end_date: str,
                                 media_service: MediaService = Depends(),
                                 news_api_service: NewsApiService = Depends(),
                                 open_ai_service: OpenAIService = Depends()):

    articles = news_api_service.get_articles(1, start_date, end_date).get("news")
    for article in articles:
        structured_article = news_api_service.transform_article(article)
        document_id = media_service.store_article("articles", structured_article)

        # keywords = open_ai_service.create_keywords(document_id, article.get("text"))
        # summary = open_ai_service.create_summary(document_id, article.get("text"), 100)
        #media_service.store_article("articles", structured_article)
