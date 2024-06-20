import requests
import json

url = "http://localhost:4000/api/v1/articles/news/all"

# Pfad zur Textdatei, die die Themen enthält
file_path = "topics"

# Definieren Sie das JSON-Template
request_template = {
    "start_date": "17/12/2023",
    "end_date": "18/05/2024",
    "page_number": 1,
    "topic": ""
}

def send_request(topic):
    request_data = request_template.copy()
    request_data["topic"] = topic
    response = requests.post(url, json=request_data)
    return response.status_code, response.json()


with open(file_path, 'r') as file:
    for line in file:
        topic = line.strip()
        print(topic)
        if topic:  # Nur nicht-leere Zeilen verarbeiten
            status_code, response_json = send_request(topic)

print("Fertig!")
