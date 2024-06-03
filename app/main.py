import chromadb
from chromadb.utils import embedding_functions
import uvicorn
from fastapi import FastAPI

# Configure Chroma to save and load from your local machine. Data will be persisted automatically
# and loaded on start (if it exists).
# the given path is inside the container

app = FastAPI()

@app.post("/createData")
def createData():
    default_ef = embedding_functions.DefaultEmbeddingFunction()

    client = chromadb.HttpClient(host="0.0.0.0", port=8000)

    collection = client.create_collection(name="articles", embedding_function=default_ef)

    articles = [
        {"id": "1", "title": "Article 1", "content": "Content of article 1",
         "metadata": {"keywords": ["keyword1", "keyword2"], "title": "testtitle", "author": "test2"}},
        {"id": "2", "title": "Article 2", "content": "Content of article 2",
         "metadata": {"keywords": ["keyword1", "keyword2"], "title": "testtitle", "author": "test"}},
    ]

    # Prepare lists of attributes
    ids = [article["id"] for article in articles]
    titles = [article["title"] for article in articles]
    contents = [article["content"] for article in articles]
    metadata = [article["metadata"] for article in articles]

    # Add articles to the collection
    collection.add(
        documents=contents,
        metadatas=metadata,
        ids=ids
    )

    print("Initial state has been created and stored.")


if __name__ == "__main__":
    uvicorn.run("main:app", host="localhost", port=4000)
