import os
import chromadb
import uuid
import tiktoken


class MediaService:
    if os.getenv('IS_DOCKER') == "true":
        client = chromadb.HttpClient(host="chromadb", port=8000)
    else:
        client = chromadb.HttpClient(host="localhost", port=8000)

    def store_article(self, collection, article: dict):
        content = article.get("content")
        metadata = article.get("metadata")
        ids = []
        availability = False

        while availability == False:
            generated_id = str(uuid.uuid4())
            availability = self.__is_id_available(generated_id, collection)

        collection.add(
            documents=content,
            metadatas=metadata,
            ids=generated_id
        )

    def store_multiple_articles(self, collection, articles):
        contents = [article["content"] for article in articles]
        metadata = [article["metadata"] for article in articles]
        ids = []

        #creates for every document a id and checks if available or not
        for article in articles:
            availability = False
            while availability == False:
                generated_id = str(uuid.uuid4())
                availability = self.__is_id_available(generated_id, collection)
                if availability:
                    ids.append(generated_id)

        collection.add(
            documents=contents,
            metadatas=metadata,
            ids=ids
        )

    def get_articles(self, number_of_articles, query, collection_name="articles"):
        collection = self.get_collection(collection_name)

        return collection.query(
            query_texts=[query],
            n_results=number_of_articles
        )

    def get_collection(self, collection_name):
        return self.client.get_collection(name=collection_name)

    def create_collection(self, collection_name, embedding_function):
        return self.client.create_collection(name=collection_name, embedding_function=embedding_function)

    def __is_id_available(self, article_id, collection):
        if collection.get(article_id).get("data") is None:
            return True

        return False

    def get_article_by_id(self, collection, id):
        return collection.get(id)

    def count_token(self, article: str):
        encoding = tiktoken.encoding_for_model("gpt-3.5-turbo-0125")
        tokens = encoding.encode(article)
        return len(tokens)
