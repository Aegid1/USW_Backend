# Import necessary modules and classes
from datetime import datetime
import requests
import yaml
from app.services.OpenAIService import OpenAIService
from app.services.MediaService import MediaService

# NewsApiService class for interacting with the News API
class NewsApiService:
    # Base URL for the News API
    url = "https://newsnow.p.rapidapi.com/newsv2"
    # Load configuration from the YAML file
    config = yaml.safe_load(open("openai_config.yaml"))

    # Method to get articles from the News API
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
        # Set up the headers for the request
        headers = {
            "x-rapidapi-key": self.config["KEYS"]["rapid-api"],
            "x-rapidapi-host": "newsnow.p.rapidapi.com",
            "Content-Type": "application/json"
        }

        # Set up the payload for the request
        payload = {
            "query": topic,
            "time_bounded": True,
            "from_date": start_date,
            "to_date": end_date,
            "location": "de",
            "language": "de",
            "page": page_number
        }

        # Send the POST request to the News API
        response = requests.post(self.url, json=payload, headers=headers)
        # Return the response as a JSON object
        return response.json()

    # Method to transform an article to a specific format
    def transform_article(self, article: dict, text: str = "", keywords: str = ""):
        """
        Transform an article to a specific format for storage.

        Parameters:
            article (dict): The article to transform.
            text (str): The content of the article (default: empty string).
            keywords (str): The keywords associated with the article (default: empty string).

        Returns:
            dict: The transformed article.
        """
        # Define the start date for calculating date counts
        start_date_str = "2010-01-01"
        start_date = datetime.strptime(start_date_str, "%Y-%m-%d").date()

        # Transform the article date to the format YYYY-MM-DD
        article_date_str = self.__transform_date(article.get("date"))
        article_date = datetime.strptime(article_date_str, "%Y-%m-%d").date()

        # Calculate the date count as the difference between the article date and the start date
        date_count = article_date - start_date

        # Create the transformed article
        transformed_article = {
            "content": text,
            "metadata": {
                "keywords": keywords,
                "title": article.get("title"),
                "author": "placeholder",  # Placeholder for the author field
                "published": article_date_str,
                "publisher": article.get("publisher").get("title"),
                "url": article.get("url"),
                "date_count": date_count.days
            }
        }
        return transformed_article

    # Private method to transform a date to the format YYYY-MM-DD
    def __transform_date(self, date: str):
        """
        Transform a date to the format YYYY-MM-DD.

        Parameters:
            date (str): The date to transform.

        Returns:
            str: The transformed date in the format YYYY-MM-DD.
        """
        # Parse the date using the provided format
        parsed_date = datetime.strptime(date, "%a, %d %b %Y %H:%M:%S %Z")
        # Format the parsed date as YYYY-MM-DD
        formatted_date_str = parsed_date.strftime("%Y-%m-%d")
        return formatted_date_str
