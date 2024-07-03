import json
import os
import subprocess
import time
import re
from datetime import datetime, timedelta

import yaml
from openai import OpenAI
import concurrent.futures
from app.services.MediaService import MediaService


class OpenAIService:
    config = yaml.safe_load(open("openai_config.yaml"))
    client = OpenAI(api_key=config['KEYS']['openai'])

    def __init__(self):
        tools = [{
            "type": "function",
            "function": {
                "name": "solve_problem",
                "description": "Solve the problem resulting from the user request that relates to a problem.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "topic": {
                            "type": "string",
                            "description": "The general topic of the user-request"
                        },
                        "user_prompt": {
                            "type": "string",
                            "description": "The user prompt containing the problem to be solved without the information of the visualization information"
                        },
                        "chart_type": {
                            "type": "string",
                            "description": "the type of visualization requested by the user"
                        },
                        "time_period": {
                            "type": "string",
                            "description": "the time period to be taken into account when the current date is " + time.strftime(
                                "%Y-%m-%d") + ", in the format YYYY-MM-DD:YYYY-MM-DD"
                        },
                        "sentiment_categories": {
                            "type": "array",
                            "items": {
                                "type": "string"
                            },
                            "description": "the sentiment categories mentioned in the analysis"
                        }

                    },
                    "required": ["topic", "user_prompt", "chart_type", "time_period"]
                }
            }
        }]

        self.assistant = self.client.beta.assistants.create(
            name="Email Assistant",
            instructions="You are an assistant who has access to media articles that are about political topics.",
            tools=tools,
            model="gpt-3.5-turbo-0125"
        )

    mediaservice = MediaService()

    @staticmethod
    def solve_problem_parallelization(topic: str, user_prompt: str, chart_type: str, time_period: str, sentiment_categories: list):

        print(chart_type)
        print(sentiment_categories)
        lower_boundary, upper_boundary = OpenAIService.__create_date_boundaries(time_period)

        mediaservice = MediaService()
        openai_service = OpenAIService()

        thread_id = openai_service.create_thread()

        articles = mediaservice.get_articles_by_date(50, topic, lower_boundary, upper_boundary)
        articles_without_date = articles.get("documents")[0]
        print(len(articles_without_date))

        for i in range(len(articles.get("metadatas")[0])):
            articles_without_date[i] += " " + articles.get("metadatas")[0][i].get("published")

        articles_divided = OpenAIService.__divide_lists(articles.get("documents")[0], 10)

        results = []

        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = [
                executor.submit(openai_service.__process_article_list, article_list, user_prompt, sentiment_categories)
                for
                article_list in
                articles_divided]
            concurrent.futures.wait(futures)
            for future in concurrent.futures.as_completed(futures):
                try:
                    result = future.result()
                    results.append(result)
                except Exception as exc:
                    print(f"list of articles generated an exception: {exc}")

        #combines the results for one final result
        request = "Can you generate the python code for me to create a " + chart_type + " with streamlit (make sure to flatten the lists) with the following data: " + "\n" + "\n".join(
            results)

        openai_service.send_message_to_thread(thread_id.id, request)
        time.sleep(1)

        run = openai_service.execute_thread_without_function_calling(thread_id.id)

        while run.status not in ['completed', 'failed']:
            run = openai_service.retrieve_execution(thread_id.id, run.id)
            print(run.status)
            time.sleep(1)

        final_result = openai_service.retrieve_messages_from_thread(thread_id.id).data[0].content[0].text.value
        extracted_code = OpenAIService.__extract_generated_code(final_result)

        OpenAIService.__execute_generated_code(extracted_code)

        return "Here is the desired " + chart_type

    @staticmethod
    def solve_problem(query: str, user_prompt: str):

        mediaservice = MediaService()
        openai_service = OpenAIService()

        # laden wir hier wirklich schon alle Artikel auf einmal rein?
        articles = mediaservice.get_articles(10, query=query)

        #TODO() number of articles per thread needs to be adjusted
        articles_divided = OpenAIService.__divide_lists(articles.get("documents")[0], 5)
        results = []

        for article_list in articles_divided:
            result = openai_service.__process_article_list(article_list, user_prompt)
            results.append(result.data[0].content[0].text.value)

        thread_id = openai_service.create_thread()
        # combines the results for one final result
        request = user_prompt + "\n" + ("with the following materials (without changing the wording in the "
                                        " articles) so that it can be used as an interim result for the following analyses "
                                        " can be used") + "\n\n".join(results)

        openai_service.send_message_to_thread(thread_id.id, request)
        time.sleep(2)
        openai_service.execute_thread_without_function_calling(thread_id.id)
        final_result = openai_service.retrieve_messages_from_thread(thread_id.id)
        return final_result.data[0].content[0].text.value

    function_lookup = {
        "solve_problem": solve_problem_parallelization
    }

    def create_thread(self):
        return self.client.beta.threads.create()

    def get_thread_id(self):
        #TODO
        pass

    def send_message_to_thread(self, thread_id, message_text):
        return self.client.beta.threads.messages.create(
            thread_id=thread_id,
            role="user",
            content=message_text
        )

    #TODO not necessary anymore
    def derive_query_from_request(self, thread_id):
        return self.client.beta.threads.messages.create(
            thread_id=thread_id,
            role="user",
            content="Please derive a search query based on my previous message" +
                    " so that all relevant articles on this topic can be collected from ChromaDB."
        )

    def execute_thread(self, thread_id):
        return self.client.beta.threads.runs.create(
            thread_id=thread_id,
            assistant_id=self.assistant.id,
            instructions="you are a sentiment-analyst, I give you text wrapped in quotes on a topic and you analyze it"
        )

    def execute_thread_without_function_calling(self, thread_id):
        return self.client.beta.threads.runs.create(
            thread_id=thread_id,
            assistant_id=self.assistant.id,
            instructions="you are an analyst that does sentiment-analysis of media-articles, talk in a professional and reasoning way",
            tool_choice="none"
        )

    def retrieve_execution(self, thread_id, run_id):
        return self.client.beta.threads.runs.retrieve(thread_id=thread_id, run_id=run_id)

    def retrieve_messages_from_thread(self, thread_id):
        return self.client.beta.threads.messages.list(thread_id=thread_id)

    #executes the chosen function
    def submit_tool_outputs(self, thread_id, run_id, tools_to_call):
        tool_output_array = []
        for tool in tools_to_call:
            output = None
            tool_call_id = tool.id
            function_name = tool.function.name
            function_args = json.loads(tool.function.arguments)
            function_to_call = self.function_lookup[function_name]

            #the chosen function is executed here
            output = function_to_call(**function_args)
            if output:
                tool_output_array.append({"tool_call_id": tool_call_id, "output": output})

            # if function_name == "solve_problem":
            #     #closes the thread
            #     # cancelled_run = self.client.beta.threads.runs.cancel(run_id=run_id, thread_id=thread_id)
            #     # print(cancelled_run)
            #     #vielleicht hier noch ein kurzer timeout
            #     return output

        return self.client.beta.threads.runs.submit_tool_outputs(
            thread_id=thread_id,
            run_id=run_id,
            tool_outputs=tool_output_array
        )

    #das hier muss an die Batch-API gesendet werden -> eigener Batch
    def create_keywords(self, document_id, text):
        text = "can you just give me 5 keywords for the following text without numbering or similar" + text

        request = {
            "custom_id": document_id,
            "method": "POST",
            "url": "/v1/chat/completions",
            "body": {
                "model": "gpt-3.5-turbo-0125",
                "messages": [
                    {
                        "role": "system",
                        "content": "You are a helpful assistant who derives 5 representative keywords from a text,"
                                   "which he names one after the other, separated only by a comma."
                    },
                    {
                        "role": "user",
                        "content": text
                    }
                ],
                "max_tokens": 1000
            }
        }
        return self.__add_to_batch(request, "batch_keywords.jsonl")

    #das hier muss an die Batch-API gesendet werden -> eigener Batch
    def create_summary(self, document_id: str, text: str, length):
        text = "can you send me a summary of the following text in max. " + str(
            length) + " words without changing the wording of the text: " + text

        request = {
            "custom_id": document_id,
            "method": "POST",
            "url": "/v1/chat/completions",
            "body": {
                "model": "gpt-3.5-turbo-0125",
                "messages": [
                    {
                        "role": "system",
                        "content": "You are a helpful assistant who writes a concise but detailed summary"
                                   "from a text"
                    },
                    {
                        "role": "user",
                        "content": text
                    }
                ],
                "max_tokens": 1000
            }
        }
        return self.__add_to_batch(request, "batch_summary.jsonl")

    def send_batch(self, batch_name: str):
        batch_input_file = self.client.files.create(
            file=open(batch_name, "rb"),
            purpose="batch"
        )
        batch = self.client.batches.create(
            input_file_id=batch_input_file.id,
            endpoint="/v1/chat/completions",
            completion_window="24h",
            metadata={
                "description": "nightly eval job"
            }
        )
        with open("batch_ids", 'a') as file:
            file.write('\n' + batch.id)

    def retrieve_batch_content(self, batch_id: str, content_type):
        batch = self.client.batches.retrieve(batch_id)
        if batch.status != "completed":
            return "Your batch is currently not ready and in the state: " + batch.status

        output_file = self.client.files.content(batch.output_file_id)

        content = output_file.content
        content_str = content.decode('utf-8')
        lines = content_str.splitlines()
        request_list = [json.loads(line) for line in lines]

        for request in request_list:
            document_id = request.get("custom_id")
            response = request.get("response").get("body").get("choices")[0].get("message").get("content")
            self.mediaservice.update_collection("articles", document_id, content_type, response)

    def check_batch_status(self, batch_id: str):
        batch = self.client.batches.retrieve(batch_id)
        return batch.status

    def __process_article_list(self, article_list, user_prompt, expected_categories):
        thread_id = self.create_thread()
        request = "\n\n".join(article_list)
        request = ("You are a sentiment analysis assistant" + "with these categories " + str(expected_categories) + ", I give you texts and you give me the results on "
                   " this topic with these categories") + user_prompt + "\n" + request + "\n" + (
                      "Please enter results in this format without "
                      " text: Date, result")

        self.send_message_to_thread(thread_id.id, request)
        time.sleep(1)
        run = self.execute_thread_without_function_calling(thread_id.id)

        while run.status not in ['completed', 'failed']:
            run = self.retrieve_execution(thread_id.id, run.id)
            print(run.status)
            time.sleep(1)

        result = self.retrieve_messages_from_thread(thread_id.id).data[0].content[0].text.value
        extracted_result = OpenAIService.__extract_analysis_results(result)

        if (len(extracted_result) == 0):
            #this prompt mostly solves the problem, the model seems sometimes a little confused with these types of tasks
            self.send_message_to_thread(thread_id, "why not? Just use the provided texts by me")
            time.sleep(1)
            run = self.execute_thread_without_function_calling(thread_id.id)

            while run.status not in ['completed', 'failed']:
                run = self.retrieve_execution(thread_id.id, run.id)
                print(run.status)
                time.sleep(1)

            result = self.retrieve_messages_from_thread(thread_id.id).data[0].content[0].text.value

        result = OpenAIService.__extract_analysis_results(result)
        filtered_result = [item for item in result if item[1].lower() in expected_categories]

        #print("RESULT: " + str(filtered_result).lower())
        return str(filtered_result).lower()

    @staticmethod
    def __divide_lists(data: list, n: int) -> list[list]:
        """Teilt eine Liste in n gleichgroße Unterlisten auf"""
        k, m = divmod(len(data), n)
        return [data[i * k + min(i, m):(i + 1) * k + min(i + 1, m)] for i in range(n)]

    @staticmethod
    def __add_to_batch(request: dict, file_name: str):
        with open(file_name, 'a') as file:
            json_str = json.dumps(request)
            file.write(json_str + '\n')

    @staticmethod
    def __extract_analysis_results(analysis: str):
        pattern = r'(\d{1,4}[-/]\d{1,2}[-/]\d{2}),\s*(\w+)'
        matches = re.findall(pattern, analysis)

        if len(matches) == 0:
            pattern = r'(\d{1,4}[-/]\d{1,2}[-/]\d{2}):\s*(\w+)'
            matches = re.findall(pattern, analysis)

        return matches

    @staticmethod
    def __extract_generated_code(request: str):

        code_match = re.search(r'```python\n(.*?)\n```', request, re.DOTALL)
        if code_match:
            extracted_code = code_match.group(1)

            return extracted_code

    @staticmethod
    def __execute_generated_code(extracted_code: str):
        #TODO add ExceptionHandling
        with open("extracted_streamlit_app.py", "w") as code_file:
            code_file.write(extracted_code)

        process = subprocess.Popen(["streamlit", "run", "extracted_streamlit_app.py"])

        time.sleep(10)
        process.terminate()

        if os.path.exists("extracted_streamlit_app.py"):
            os.remove("extracted_streamlit_app.py")
            print(f"The file was deleted.")
        else:
            print(f"The file was not found.")

    @staticmethod
    def __create_date_boundaries(time_period: str):
        initial_date_str = "2010-01-01"
        initial_date = datetime.strptime(initial_date_str, "%Y-%m-%d").date()

        start_date_str, end_date_str = time_period.split(":")

        start_date = datetime.strptime(start_date_str, "%Y-%m-%d").date()
        end_date = datetime.strptime(end_date_str, "%Y-%m-%d").date()

        upper_boundary = end_date - initial_date
        lower_boundary = start_date - initial_date

        return lower_boundary.days, upper_boundary.days
