from datetime import datetime

import requests
import yaml
from app.services.OpenAIService import OpenAIService
from app.services.MediaService import MediaService

class NewsApiService:
    url = "https://newsnow.p.rapidapi.com/newsv2"
    config = yaml.safe_load(open("openai_config.yaml"))

    def get_articles(self, topic: str, page_number: int, start_date: str, end_date: str):
        """
                Get articles from the News API based on the provided topic and date range.

                Parameters:
                    topic (str): The topic to search for.
                    page_number (int): The page number to retrieve.
                    start_date (str): The start date for the search (DD/MM/YYYY).
                    end_date (str): The end date for the search (DD/MM/YYYY).

                Returns:
                    dict: The response from the News API as a JSON object.
        """
        # date format is DD/MM/YYYY
        headers = {
            "x-rapidapi-key": self.config["KEYS"]["rapid-api"],
            "x-rapidapi-host": "newsnow.p.rapidapi.com",
            "Content-Type": "application/json"
        }

        #maybe test with variable amount of pages
        payload = {
            "query": topic,
            "time_bounded": True,
            "from_date": start_date,
            "to_date": end_date,
            "location": "de",
            "language": "de",
            "page": page_number
        }
        response = requests.post(self.url, json=payload, headers=headers)
        return response.json()

    def transform_article(self, article, text="", keywords=""):
        """
                Transform an article to a specific format for storage.

                Parameters:
                    article (dict): The article to transform.
                    text (str): The content of the article (default: empty string).
                    keywords (str): The keywords associated with the article (default: empty string).

                Returns:
                    dict: The transformed article.
        """
        start_date_str = "2010-01-01"
        start_date = datetime.strptime(start_date_str, "%Y-%m-%d").date()
        article_date_str = self.__transform_date(article.get("date"))
        article_date = datetime.strptime(article_date_str, "%Y-%m-%d").date()
        date_count = article_date - start_date

        transformed_article = {
            "content": text,
            "metadata": {
                "keywords": keywords,
                "title": article.get("title"),
                "author": "placeholder",
                "published": article_date_str,
                "publisher": article.get("publisher").get("title"),
                "url": article.get("url"),
                "date_count": date_count.days
            }
        }
        return transformed_article

    #transforms a date to the format YYYY-MM-DD
    def __transform_date(self, date: str):
        """
                Transform a date to the format YYYY-MM-DD.

                Parameters:
                    date (str): The date to transform.

                Returns:
                    str: The transformed date in the format YYYY-MM-DD.
        """
        parsed_date = datetime.strptime(date, "%a, %d %b %Y %H:%M:%S %Z")
        formatted_date_str = parsed_date.strftime("%Y-%m-%d")
        return formatted_date_str
