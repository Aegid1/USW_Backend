import os
import chromadb
import uuid
import tiktoken
from datetime import datetime, timedelta

from enum import Enum

class DocumentType(Enum):
    KEYWORDS = "KEYWORDS"
    SUMMARY = "SUMMARY"

class MediaService:
    if os.getenv('IS_DOCKER') == "true":
        client = chromadb.HttpClient(host="chromadb", port=8000)
    else:
        client = chromadb.HttpClient(host="localhost", port=8000)

    def store_article(self, collection_name, article: dict):
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

    def store_multiple_articles(self, collection_name, articles):
        contents = [article["content"] for article in articles]
        metadata = [article["metadata"] for article in articles]
        collection = self.get_collection(collection_name)
        ids = []

        #creates for every document a id and checks if available or not
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

    def get_articles(self, number_of_articles, query, collection_name="articles"):
        collection = self.get_collection(collection_name)

        return collection.query(
            query_texts=[query],
            n_results=number_of_articles,
        )

    def get_articles_by_date(self, number_of_articles, query, start_date, end_date, collection_name="articles"):
        collection = self.get_collection(collection_name)

        return collection.query(
            query_texts=[query],
            n_results=number_of_articles,
            where={"$and":[{"date_count": {"$gte": start_date}}, {"date_count": {"$lt": end_date}}]}
        )

    def get_collection(self, collection_name):
        return self.client.get_collection(name=collection_name)

    def update_collection(self, collection_name, document_id: str, type: DocumentType, content: str):
        collection = self.get_collection(collection_name)
        print(collection.id)
        if type == DocumentType.SUMMARY:
            collection.update(ids=document_id, documents=content)
        else:
            metadata = self.get_article_by_id(collection, document_id).get("metadatas")[0]
            metadata["keywords"] = content
            collection.update(ids=document_id, metadatas=metadata)

    def create_collection(self, collection_name, embedding_function):
        return self.client.create_collection(name=collection_name, embedding_function=embedding_function)

    def get_article_by_id(self, collection, id):
        return collection.get(id)

    def count_token(self, article: str):
        encoding = tiktoken.encoding_for_model("gpt-3.5-turbo-0125")
        tokens = encoding.encode(article)
        return len(tokens)

    def update_date_counts_all_articles(self, collection):
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
        print("Alle Artikel wurden erfolgreich aktualisiert.")

    #TODO extract this method into a AnalysisService.py
    def filter_documents_by_time_interval(self, articles, lower_boundary, upper_boundary):

        article_per_intervall = {}

        # unter 1 Jahr: 1 Tage Abstand -> end_date - start_date < 365
        # ab 1 Jahr: 2 Tage Abstand ->  364 < end_date - start_date < 730
        # ab 2 Jahr: 4 Tage Abstand ->  729 < end_date - start_date < 1065
        # ab 3 Jahr: 8 Tage Abstand -> 1065 < end_date - start_date < 1430

        def calculate_time_step(days):
            if days < 365:
                return 1
            elif days < 730:
                return 2
            elif days < 1065:
                return 4
            else:
                return 8

        for article, metadata in zip(articles.get("documents")[0], articles.get("metadatas")[0]):

            published_date = metadata['date_count']
            days_difference = upper_boundary - lower_boundary
            time_step = calculate_time_step(days_difference)

            if (published_date - lower_boundary) % time_step == 0:
                day = metadata["published"]
                if day not in article_per_intervall:
                    article_per_intervall[day] = (article, metadata)

        chosen_articles = [(day, article, metadata) for day, (article, metadata) in
                                sorted(article_per_intervall.items())]
        return chosen_articles

    def __is_id_available(self, article_id, collection):
        if collection.get(article_id).get("data") is None:
            return True
        return False
