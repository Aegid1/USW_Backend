import requests
import yaml


class NewsApiService:
    url = "https://newsnow.p.rapidapi.com/newsv2"
    config = yaml.safe_load(open("openai_config.yaml"))

    payload = {
        "query": "AI",
        "time_bounded": True,
        "from_date": "06/06/2023",
        "to_date": "07/06/2023",
        "location": "us",
        "language": "en",
        "page": 1
    }
    headers = {
        "x-rapidapi-key": config['KEYS']['rapid-api'],
        "x-rapidapi-host": "newsnow.p.rapidapi.com",
        "Content-Type": "application/json"
    }

    response = requests.post(url, json=payload, headers=headers)
    print(len(response.json()))
    print(response.json().get("news")[1].get("text"))
    # print(response.json())
