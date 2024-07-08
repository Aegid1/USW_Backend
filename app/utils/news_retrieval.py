import requests
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta

url = "http://localhost:4000/api/v1/articles/news/all"

# Pfad zur Textdatei, die die Themen enthält
file_path = "topics"

def generate_monthly_dates(start_date, end_date):
    """
    Generate a list of start and end dates for each month between start_date and end_date.

    Parameters:
        start_date (datetime): The start date.
        end_date (datetime): The end date.

    Returns:
        list: A list of tuples containing start and end dates for each month.
    """
    current_date = start_date
    monthly_dates = []

    while current_date < end_date:
        month_start = current_date
        month_end = (month_start + relativedelta(months=1)) - timedelta(days=1)
        if month_end > end_date:
            month_end = end_date
        monthly_dates.append((month_start, month_end))
        current_date = month_end + timedelta(days=1)

    return monthly_dates


def call_news_api_for_month(topic, start_date, end_date):
    """
    Call the news API for a specific topic and date range.

    Parameters:
        topic (str): The topic for the news articles.
        start_date (datetime): The start date of the range.
        end_date (datetime): The end date of the range.

    Returns:
        None
    """
    url = "http://localhost:4000/api/v1/articles/news/all"

    request_data = {
        "start_date": start_date.strftime("%d/%m/%Y"),
        "end_date": end_date.strftime("%d/%m/%Y"),
        "page_number": 1,
        "topic": topic
    }

    response = requests.post(url, json=request_data)

    if response.status_code == 200:
        print(f"Successfully called API for {start_date.strftime('%B %Y')}")
    else:
        print(f"Failed to call API for {start_date.strftime('%B %Y')}. Status code: {response.status_code}")


with open(file_path, 'r') as file:
    start_date = datetime.strptime("01/05/2023", "%d/%m/%Y")
    end_date = datetime.strptime("01/06/2024", "%d/%m/%Y")
    for line in file:
        topic = line.strip()
        print(topic)
        if topic:  # Nur nicht-leere Zeilen verarbeiten
            monthly_dates = generate_monthly_dates(start_date, end_date)
            for start, end in monthly_dates:
                call_news_api_for_month(topic, start, end)

print("Fertig!")
