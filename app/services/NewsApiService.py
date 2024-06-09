from datetime import datetime

import requests
import yaml
from app.services.OpenAIService import OpenAIService
from app.services.MediaService import MediaService

class NewsApiService:
    url = "https://newsnow.p.rapidapi.com/newsv2"
    config = yaml.safe_load(open("./app/services/openai_config.yaml"))

    def get_articles(self, amount: int, start_date: str, end_date: str):
        # date format is DD/MM/YYYY
        headers = {
            "x-rapidapi-key": self.config["KEYS"]["rapid-api"],
            "x-rapidapi-host": "newsnow.p.rapidapi.com",
            "Content-Type": "application/json"
        }

        #maybe test with variable amount of pages
        payload = {
            "query": "AI",
            "time_bounded": True,
            "from_date": start_date,
            "to_date": end_date,
            "location": "de",
            "language": "de",
            "page": 1
        }
        response = requests.post(self.url, json=payload, headers=headers)
        return response

    def transform_article(self, article, text, keywords):
        transformed_article = {
            "content": text,
            "metadata": {
                "keywords": keywords,
                "title": article.get("title"),
                "author": "placeholder",
                "published": self.__transform_date(article.get("date")),
                "publisher": article.get("publisher").get("title"),
                "url": article.get("url"),
            }
        }
        return transformed_article

    #transforms a date to the format YYYY-MM-DD
    def __transform_date(self, date: str):
        parsed_date = datetime.strptime(date, "%a, %d %b %Y %H:%M:%S %Z")
        formatted_date_str = parsed_date.strftime("%Y-%m-%d")
        return formatted_date_str


news_api = NewsApiService()
response = news_api.get_articles(1, "13/02/2023", "15/02/2023")
print(response.json())
