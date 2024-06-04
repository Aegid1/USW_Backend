from fastapi import APIRouter
import chromadb
from chromadb.utils import embedding_functions

router = APIRouter()


@router.post("/createData")
def create_data():
    default_ef = embedding_functions.DefaultEmbeddingFunction()

    client = chromadb.HttpClient(host="0.0.0.0", port=8000)

    collection = client.get_collection(name="articles")

    if collection is None:
        collection = client.create_collection(name="articles", embedding_function=default_ef)

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
