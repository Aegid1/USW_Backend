from fastapi import APIRouter, Depends
from chromadb.utils import embedding_functions
from app.services.MediaService import MediaService
from app.services.NewsApiService import NewsApiService
from app.services.OpenAIService import OpenAIService
from app.services.BatchApiService import BatchApiService
from app.basemodel import Article, Query, NewsApiRequest

router = APIRouter()


def get_media_service():
    """
    Get an instance of MediaService.

    Returns:
        MediaService: An instance of MediaService.
    """
    return MediaService


def get_newsapi_service():
    """
    Get an instance of NewsApiService.

    Returns:
        NewsApiService: An instance of NewsApiService.
    """
    return NewsApiService


def get_openai_service():
    """
    Get an instance of OpenAIService.

    Returns:
        OpenAIService: An instance of OpenAIService.
    """
    return OpenAIService


# only useful for development purposes, will be deleted in the end
@router.post("/createExampleData", status_code=201)
def create_data(media_service: MediaService = Depends()):
    """
    Create example data for development purposes.

    Parameters:
        media_service (MediaService): The Media service instance.

    Returns:
        None
    """
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


@router.post("/articles/news/check")
def get_articles_from_news_api(request: NewsApiRequest,
                               news_api_service: NewsApiService = Depends()):
    """
        Get articles from the News API.

        Parameters:
            request (NewsApiRequest): The request containing start_date, end_date, topic, and page_number.
            news_api_service (NewsApiService): The News API service instance.

        Returns:
            list: A list of articles from the News API.
        """
    articles = news_api_service.get_articles(request.topic, request.page_number, request.start_date,
                                             request.end_date).get("news")
    return articles


@router.post("/articles/news")
def store_articles_from_news_api(request: NewsApiRequest,
                                 media_service: MediaService = Depends(),
                                 news_api_service: NewsApiService = Depends(),
                                 batch_api_service: BatchApiService = Depends()):
    """
        Store articles from the News API and process them using OpenAIService.

        Parameters:
            request (NewsApiRequest): The request containing start_date, end_date, topic, and page_number.
            media_service (MediaService): The Media service instance.
            news_api_service (NewsApiService): The News API service instance.
            open_ai_service (OpenAIService): The OpenAI service instance.
            batch_api_service (BatchApiService): The BatchAPI of OpenAI service instance

        Returns:
            None
        """
    articles = news_api_service.get_articles(request.topic, request.page_number, request.start_date,
                                             request.end_date).get("news")
    for article in articles:
        structured_article = news_api_service.transform_article(article)
        document_id = media_service.store_article("articles", structured_article)
        batch_api_service.create_keywords(document_id, article.get("text"))
        batch_api_service.create_summary(document_id, article.get("text"), 100)


#this is currently only useful for changing the structure of the documents -> later purpose unknown
@router.post("/articles/update")
def update_date_count_of_all_articles(media_service: MediaService = Depends()):
    """
       Update the date count of all articles in the collection.

       Parameters:
           media_service (MediaService): The Media service instance.

       Returns:
           None
       """
    collection = media_service.get_collection("articles")

    media_service.update_date_counts_all_articles(collection)


@router.post("/articles/news/all")
def store_all_articles_from_news_api(request: NewsApiRequest,
                                     media_service: MediaService = Depends(),
                                     news_api_service: NewsApiService = Depends(),
                                     batch_api_service: BatchApiService = Depends()):
    """
        Store all articles from the News API, handling pagination.

        Parameters:
            request (NewsApiRequest): The request containing start_date, end_date, topic, and page_number.
            media_service (MediaService): The Media service instance.
            news_api_service (NewsApiService): The News API service instance.
            open_ai_service (OpenAIService): The OpenAI service instance.
            batch_api_service (BatchApiService): The BatchAPI of OpenAI

        Returns:
            None
        """
    page_number = request.page_number
    response = news_api_service.get_articles(request.topic, page_number, request.start_date, request.end_date)
    articles = response.get("news")
    #this makes sure all articles are retrievedsend_request
    while response.get("count") != 0:
        print("PAGE: " + str(page_number))
        for article in articles:
            structured_article = news_api_service.transform_article(article)
            document_id = media_service.store_article("articles", structured_article)
            batch_api_service.create_keywords(document_id, article.get("text"))
            batch_api_service.create_summary(document_id, article.get("text"), 100)

        page_number += 1
        if (page_number == 10): break
        response = news_api_service.get_articles(request.topic, page_number, request.start_date, request.end_date)
        print(response.get("count"))
        articles = response.get("news")


@router.post("/articles/{collection_name}", status_code=201)
def add_article_to_collection(article: Article, collection_name: str, media_service: MediaService = Depends()):
    """
    Add an article to a specific collection.

    Parameters:
        article (Article): The article to be added.
        collection_name (str): The name of the collection.
        media_service (MediaService): The Media service instance.

    Returns:
        None
    """
    collection = media_service.get_collection(collection_name)
    media_service.store_article(collection, article.dict())


@router.post("/articles/many/{collection_name}", status_code=201)
def add_multiple_articles_to_collection(articles, collection_name, media_service: MediaService = Depends()):
    """
    Add multiple articles to a specific collection.

    Parameters:
        articles (list[Article]): The list of articles to be added.
        collection_name (str): The name of the collection.
        media_service (MediaService): The Media service instance.

    Returns:
        None
    """
    collection = media_service.get_collection(collection_name)
    media_service.store_multiple_articles(collection, articles)


# only useful for development purposes, will be deleted in the end
@router.post("/articles/{collection_name}/{number_of_articles}", status_code=200)
def get_articles_from_collection(collection_name, number_of_articles: int, query: Query,
                                 media_service: MediaService = Depends()):
    """
      Get a specified number of articles from a collection based on a query.

      Parameters:
          collection_name (str): The name of the collection.
          number_of_articles (int): The number of articles to retrieve.
          query (Query): The query to filter articles.
          media_service (MediaService): The Media service instance.

      Returns:
          list: A list of articles matching the query.
      """
    return media_service.get_articles(number_of_articles, query.query, collection_name)


#will be changed later on, to get the average amount of tokens of x articles for further improving
@router.get("/articles/{article_id}")
def get_amount_of_tokens_of_article(article_id: str, media_service: MediaService = Depends()):
    """
    Get the number of tokens in a specific article.

    Parameters:
        article_id (str): The ID of the article.
        media_service (MediaService): The Media service instance.

    Returns:
        int: The number of tokens in the article.
    """
    collection = media_service.get_collection("articles")
    article = media_service.get_article_by_id(collection, article_id)

    return media_service.count_token(article.get("documents")[0])


@router.get("/articles/{collection_name}/{document_id}")
def get_specific_article_by_id(collection_name: str, document_id: str, media_service: MediaService = Depends()):
    """
        Get a specific article by its ID from a specified collection.

        Parameters:
            collection_name (str): The name of the collection containing the article.
            document_id (str): The ID of the document (article) to retrieve.
            media_service (MediaService): The Media service instance.

        Returns:
            dict: The article data retrieved from the specified collection.
        """
    collection = media_service.get_collection(collection_name)
    return media_service.get_article_by_id(collection, document_id)
