# Import necessary modules and classes
import os
import chromadb
import uuid
import tiktoken
from datetime import datetime, timedelta
from enum import Enum

# Enum for Document Types
class DocumentType(Enum):
    KEYWORDS = "KEYWORDS"
    SUMMARY = "SUMMARY"

# MediaService class for managing articles and collections
class MediaService:
    # Initialize the ChromaDB client depending on whether the application is running in Docker or not
    if os.getenv('IS_DOCKER') == "true":
        client = chromadb.HttpClient(host="chromadb", port=8000)
    else:
        client = chromadb.HttpClient(host="localhost", port=8000)

    # Store a single article in the specified collection
    def store_article(self, collection_name: str, article: dict):
        """
        Store a single article in the specified collection.

        Parameters:
            collection_name (str): The name of the collection.
            article (dict): The article to store, including content and metadata.

        Returns:
            str: The generated ID of the stored article.
        """
        content = article.get("content")
        metadata = article.get("metadata")
        collection = self.get_collection(collection_name)
        ids = []
        availability = False

        while not availability:
            generated_id = str(uuid.uuid4())
            availability = self.__is_id_available(generated_id, collection)

        collection.add(
            documents=content,
            metadatas=metadata,
            ids=generated_id
        )
        return generated_id

    # Store multiple articles in the specified collection
    def store_multiple_articles(self, collection_name: str, articles: list[dict]):
        """
        Store multiple articles in the specified collection.

        Parameters:
            collection_name (str): The name of the collection.
            articles (list[dict]): The list of articles to store, each including content and metadata.

        Returns:
            None
        """
        contents = [article["content"] for article in articles]
        metadata = [article["metadata"] for article in articles]
        collection = self.get_collection(collection_name)
        ids = []

        # Create a unique ID for each document and check its availability
        for article in articles:
            availability = False
            generated_id = ""
            while not availability:
                generated_id = str(uuid.uuid4())
                availability = self.__is_id_available(generated_id, collection)
                print(availability)

            ids.append(generated_id)

        collection.add(
            documents=contents,
            metadatas=metadata,
            ids=ids
        )

    # Retrieve articles from the specified collection based on a query
    def get_articles(self, number_of_articles: int, query: str, collection_name: str = "articles"):
        """
        Retrieve articles from the specified collection based on a query.

        Parameters:
            number_of_articles (int): The number of articles to retrieve.
            query (str): The query to filter articles.
            collection_name (str): The name of the collection.

        Returns:
            list: A list of articles matching the query.
        """
        collection = self.get_collection(collection_name)

        return collection.query(
            query_texts=[query],
            n_results=number_of_articles,
        )

    # Retrieve articles from the specified collection based on a date range
    def get_articles_by_date(self, number_of_articles: int, query: str, start_date: str, end_date: str, collection_name: str = "articles"):
        """
        Retrieve articles from the specified collection based on a date range.

        Parameters:
            number_of_articles (int): The number of articles to retrieve.
            query (str): The query to filter articles.
            start_date (str): The start date of the range.
            end_date (str): The end date of the range.
            collection_name (str): The name of the collection.

        Returns:
            list: A list of articles matching the query and date range.
        """
        collection = self.get_collection(collection_name)

        return collection.query(
            query_texts=[query],
            n_results=number_of_articles,
            where={"$and":[{"date_count": {"$gte": start_date}}, {"date_count": {"$lt": end_date}}]}
        )

    # Get the specified collection
    def get_collection(self, collection_name: str):
        """
        Get the specified collection.

        Parameters:
            collection_name (str): The name of the collection.

        Returns:
            Collection: The specified collection.
        """
        return self.client.get_collection(name=collection_name)

    # Update a document in the specified collection
    def update_collection(self, collection_name: str, document_id: str, type: DocumentType, content: str):
        """
        Update a document in the specified collection.

        Parameters:
            collection_name (str): The name of the collection.
            document_id (str): The ID of the document to update.
            type (DocumentType): The type of document (KEYWORDS or SUMMARY).
            content (str): The new content to update.

        Returns:
            None
        """
        collection = self.get_collection(collection_name)
        print(collection.id)
        if type == DocumentType.SUMMARY:
            collection.update(ids=document_id, documents=content)
        else:
            metadata = self.get_article_by_id(collection, document_id).get("metadatas")[0]
            metadata["keywords"] = content
            collection.update(ids=document_id, metadatas=metadata)

    # Create a new collection
    def create_collection(self, collection_name: str, embedding_function):
        """
        Create a new collection.

        Parameters:
            collection_name (str): The name of the collection.
            embedding_function: The embedding function to use.

        Returns:
            Collection: The created collection.
        """
        return self.client.create_collection(name=collection_name, embedding_function=embedding_function)

    # Get an article by its ID
    def get_article_by_id(self, collection, id: str):
        """
        Get an article by its ID.

        Parameters:
            collection (Collection): The collection containing the article.
            id (str): The ID of the article.

        Returns:
            dict: The retrieved article.
        """
        return collection.get(id)

    # Count the number of tokens in an article
    def count_token(self, article: str):
        """
        Count the number of tokens in an article.

        Parameters:
            article (str): The article to count tokens in.

        Returns:
            int: The number of tokens in the article.
        """
        encoding = tiktoken.encoding_for_model("gpt-3.5-turbo-0125")
        tokens = encoding.encode(article)
        return len(tokens)

    # Update the date counts for all articles in the collection
    def update_date_counts_all_articles(self, collection):
        """
        Update the date counts for all articles in the collection.

        Parameters:
            collection (Collection): The collection to update.

        Returns:
            None
        """
        start_date_str = "2010-01-01"
        start_date = datetime.strptime(start_date_str, "%Y-%m-%d").date()

        for i in range(0, 1000, 1):
            try:
                batch = collection.get(
                    include=["metadatas", "documents"],
                    limit=1,
                    offset=i)

                batch = dict(batch)

                article_date_str = batch["metadatas"][0]["published"]
                article_date = datetime.strptime(article_date_str, "%Y-%m-%d").date()

                date_count = article_date - start_date
                batch["metadatas"][0]["date_count"] = date_count.days

                collection.update(
                    ids=batch["ids"],
                    metadatas=batch["metadatas"]
                )

            except KeyError:
                continue
        print("All texts were successfully updated.")

    # Filter documents by a specified time interval
    def filter_documents_by_time_interval(self, articles: dict, lower_boundary: int, upper_boundary: int):
        """
        Filter documents by a specified time interval.

        Parameters:
            articles (dict): The articles to filter.
            lower_boundary (int): The lower boundary of the time interval.
            upper_boundary (int): The upper boundary of the time interval.

        Returns:
            dict: The filtered articles.
        """
        def calculate_time_step(days):
            if days < 365:
                return 1
            elif days < 730:
                return 2
            elif days < 1065:
                return 4
            else:
                return 8

        metadatas = articles.get("metadatas")[0]
        texts = articles.get("documents")[0]

        days_difference = upper_boundary - lower_boundary
        time_step = calculate_time_step(days_difference)

        existing_dates = []
        indices_to_remove = []

        for index, (text, metadata) in enumerate(zip(texts, metadatas)):
            published_date = metadata['date_count']

            if (published_date - lower_boundary) % time_step == 0:
                if published_date not in existing_dates:
                    existing_dates.append(published_date)
                else:
                    indices_to_remove.append(index)
            else:
                indices_to_remove.append(index)

        for index in sorted(indices_to_remove, reverse=True):
            del metadatas[index]
            del texts[index]

        articles["documents"][0] = texts
        articles["metadatas"][0] = metadatas

        return articles

    # Check if a generated ID is available in the collection
    def __is_id_available(self, article_id: str, collection):
        """
        Check if a generated ID is available in the collection.

        Parameters:
            article_id (str): The generated ID to check.
            collection (Collection): The collection to check against.

        Returns:
            bool: True if the ID is available, False otherwise.
        """
        if collection.get(article_id).get("data") is None:
            return True
        return False
