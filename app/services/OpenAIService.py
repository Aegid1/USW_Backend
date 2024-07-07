import json
import os
import subprocess
import time
import re
import ast
from datetime import datetime

import yaml
from openai import OpenAI
import concurrent.futures
from app.services.MediaService import MediaService, DocumentType

# OpenAIService class for interacting with the OpenAI API
class OpenAIService:
    # Load configuration from the YAML file
    config = yaml.safe_load(open("openai_config.yaml"))
    # Initialize the OpenAI client with the API key
    client = OpenAI(api_key=config['KEYS']['openai'])

    def __init__(self):
        # Define tools for the assistant
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
                            "description": "the time period to be taken into account when the current date is " + time.strftime("%Y-%m-%d") + ", in the format YYYY-MM-DD:YYYY-MM-DD"
                        },
                        "sentiment_categories": {
                            "type": "array",
                            "items": {
                                "type": "string"
                            },
                            "description": "the sentiment categories mentioned in the analysis"
                        }
                    },
                    "required": ["topic", "user_prompt", "chart_type", "time_period", "sentiment_categories"]
                }
            }
        }]

        # Create an assistant with specific instructions and tools
        self.assistant = self.client.beta.assistants.create(
            name="Email Assistant",
            instructions="You are an assistant who has access to media articles that are about political topics.",
            tools=tools,
            model="gpt-3.5-turbo-0125"
        )

    # Initialize MediaService
    mediaservice = MediaService()

    @staticmethod
    def solve_problem_parallelization(topic: str, user_prompt: str, chart_type: str, time_period: str, sentiment_categories: list):
        """
        Solve a problem in parallel using multiple threads.

        Parameters:
            topic (str): The topic of the user request.
            user_prompt (str): The user prompt containing the problem to be solved.
            chart_type (str): The type of visualization requested.
            time_period (str): The time period to be considered.
            sentiment_categories (list): The sentiment categories mentioned in the analysis.

        Returns:
            str: The result of the problem-solving process.
        """
        missing_params = []
        if not topic:
            missing_params.append('topic')
        if not user_prompt:
            missing_params.append('user_prompt')
        if not chart_type:
            missing_params.append('chart_type')
        if not time_period:
            missing_params.append('time_period')
        if not sentiment_categories:
            missing_params.append('sentiment_categories')

        if missing_params:
            return f"The following parameters are missing or invalid: {', '.join(missing_params)}"

        print(chart_type)
        print(sentiment_categories)
        print(time_period)
        lower_boundary, upper_boundary = OpenAIService.__create_date_boundaries(time_period)

        mediaservice = MediaService()
        openai_service = OpenAIService()

        thread_id = openai_service.create_thread()

        if chart_type.lower() == "timeseries" or chart_type.lower() == "time series":
            # Retrieve more data for time series
            articles = mediaservice.get_articles_by_date(600, topic, lower_boundary, upper_boundary)
            print(len(articles.get("documents")[0]))
            articles = mediaservice.filter_documents_by_time_interval(articles, lower_boundary, upper_boundary)
            print(len(articles.get("documents")[0]))
        else:
            articles = mediaservice.get_articles_by_date(300, topic, lower_boundary, upper_boundary)

        articles_without_date = articles.get("documents")[0]
        for i in range(len(articles.get("metadatas")[0])):
            articles_without_date[i] += " " + articles.get("metadatas")[0][i].get("published")

        articles_divided = OpenAIService.__divide_lists(articles_without_date, int(len(articles.get("documents")[0]) / 10))

        results = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=int(len(articles.get("documents")[0]) / 10)) as executor:
            futures = [
                executor.submit(openai_service.__process_article_list, article_list, user_prompt, sentiment_categories)
                for article_list in articles_divided
            ]
            concurrent.futures.wait(futures)
            for future in concurrent.futures.as_completed(futures):
                try:
                    result = future.result()
                    results.append(result)
                except Exception as exc:
                    print(f"List of articles generated an exception: {exc}")

        flattened_results = []
        for sublist_str in results:
            sublist = ast.literal_eval(sublist_str)
            flattened_results.extend(sublist)

        request = ("Can you generate the directly executable python script for me to create a "
                   + chart_type + " with streamlit with like this: "
                   + "\n" + "data = [('2024-05-08', '3')]"
                   )
        openai_service.send_message_to_thread(thread_id.id, request)
        time.sleep(1)

        run = openai_service.execute_thread_without_function_calling(thread_id.id)

        while run.status not in ['completed', 'failed']:
            run = openai_service.retrieve_execution(thread_id.id, run.id)
            print(run.status)
            time.sleep(1)

        final_result = openai_service.retrieve_messages_from_thread(thread_id.id).data[0].content[0].text.value
        try:
            extracted_code = OpenAIService.__extract_generated_code(final_result, flattened_results)
            OpenAIService.__execute_generated_code(extracted_code)
        except RuntimeError as e:
            return "Something went wrong with the execution of the generated code"

        return "Here is the desired " + chart_type

    @staticmethod
    def solve_problem(topic: str, user_prompt: str, chart_type: str, time_period: str, sentiment_categories: list):
        """
        Solve a problem using a single thread.

        Parameters:
            topic (str): The topic of the user request.
            user_prompt (str): The user prompt containing the problem to be solved.
            chart_type (str): The type of visualization requested.
            time_period (str): The time period to be considered.
            sentiment_categories (list): The sentiment categories mentioned in the analysis.

        Returns:
            str: The result of the problem-solving process.
        """
        print(chart_type)
        print(sentiment_categories)
        print(time_period)
        lower_boundary, upper_boundary = OpenAIService.__create_date_boundaries(time_period)

        mediaservice = MediaService()
        openai_service = OpenAIService()

        thread_id = openai_service.create_thread()

        articles = mediaservice.get_articles_by_date(400, topic, lower_boundary, upper_boundary)

        if chart_type == "timeseries" or chart_type == "time series":
            articles = mediaservice.filter_documents_by_time_interval(articles, lower_boundary, upper_boundary)

        articles_without_date = articles.get("documents")[0]
        for i in range(len(articles.get("metadatas")[0])):
            articles_without_date[i] += " " + articles.get("metadatas")[0][i].get("published")

        articles_divided = OpenAIService.__divide_lists(articles_without_date, 10)

        results = []
        for article_list in articles_divided:
            result = openai_service.__process_article_list(article_list, user_prompt, sentiment_categories)
            results.append(result)

        request = "Can you generate the python code for me to create a " + chart_type + " with streamlit (make sure to flatten the lists) with the following data: " + "\n" + "\n".join(results)

        openai_service.send_message_to_thread(thread_id.id, request)
        time.sleep(1)

        run = openai_service.execute_thread_without_function_calling(thread_id.id)

        execution_counter = 0
        while run.status not in ['completed', 'failed']:
            execution_counter += 1
            if execution_counter > 60:
                return "There was an issue with your request, try again"

            run = openai_service.retrieve_execution(thread_id.id, run.id)
            print(run.status)
            time.sleep(1)

        final_result = openai_service.retrieve_messages_from_thread(thread_id.id).data[0].content[0].text.value

        try:
            extracted_code = OpenAIService.__extract_generated_code(final_result)
            OpenAIService.__execute_generated_code(extracted_code)
        except RuntimeError as e:
            return "Something went wrong with the execution of the generated code"

        return "Here is the desired " + chart_type

    function_lookup = {
        "solve_problem": solve_problem_parallelization
    }

    def create_thread(self):
        """
        Create a new thread.

        Returns:
            Thread: The created thread.
        """
        return self.client.beta.threads.create()

    def send_message_to_thread(self, thread_id, message_text):
        """
        Send a message to a specific thread.

        Parameters:
            thread_id (str): The ID of the thread.
            message_text (str): The text of the message.

        Returns:
            Message: The created message.
        """
        return self.client.beta.threads.messages.create(
            thread_id=thread_id,
            role="user",
            content=message_text
        )

    def execute_thread(self, thread_id):
        """
        Execute a thread with function calling.

        Parameters:
            thread_id (str): The ID of the thread.

        Returns:
            Run: The created run.
        """
        return self.client.beta.threads.runs.create(
            thread_id=thread_id,
            assistant_id=self.assistant.id,
            instructions="you are a sentiment-analyst, I give you text wrapped in quotes on a topic and you analyze it"
        )

    def execute_thread_without_function_calling(self, thread_id):
        """
        Execute a thread without function calling.

        Parameters:
            thread_id (str): The ID of the thread.

        Returns:
            Run: The created run.
        """
        return self.client.beta.threads.runs.create(
            thread_id=thread_id,
            assistant_id=self.assistant.id,
            instructions="you are an analyst that does sentiment-analysis of media-articles, talk in a professional and reasoning way",
            tool_choice="none"
        )

    def retrieve_execution(self, thread_id, run_id):
        """
        Retrieve the execution status of a run.

        Parameters:
            thread_id (str): The ID of the thread.
            run_id (str): The ID of the run.

        Returns:
            Run: The retrieved run.
        """
        return self.client.beta.threads.runs.retrieve(thread_id=thread_id, run_id=run_id)

    def retrieve_messages_from_thread(self, thread_id):
        """
        Retrieve messages from a thread.

        Parameters:
            thread_id (str): The ID of the thread.

        Returns:
            list: A list of messages from the thread.
        """
        return self.client.beta.threads.messages.list(thread_id=thread_id)

    def submit_tool_outputs(self, thread_id, run_id, tools_to_call):
        """
        Submit the tool outputs for a run.

        Parameters:
            thread_id (str): The ID of the thread.
            run_id (str): The ID of the run.
            tools_to_call (list): The list of tools to call.

        Returns:
            Run: The updated run with tool outputs submitted.
        """
        tool_output_array = []
        for tool in tools_to_call:
            output = None
            tool_call_id = tool.id
            function_name = tool.function.name
            function_args = json.loads(tool.function.arguments)
            function_to_call = self.function_lookup[function_name]

            # Execute the chosen function
            output = function_to_call(**function_args)
            if output:
                tool_output_array.append({"tool_call_id": tool_call_id, "output": output})

        return self.client.beta.threads.runs.submit_tool_outputs(
            thread_id=thread_id,
            run_id=run_id,
            tool_outputs=tool_output_array
        )

    def create_keywords(self, document_id, text):
        """
        Create keywords for a document.

        Parameters:
            document_id (str): The ID of the document.
            text (str): The text of the document.

        Returns:
            None
        """
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
                        "content": "You are a helpful assistant who derives 5 representative keywords from a text, which he names one after the other, separated only by a comma."
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

    def create_summary(self, document_id: str, text: str, length):
        """
        Create a summary for a document.

        Parameters:
            document_id (str): The ID of the document.
            text (str): The text of the document.
            length (int): The maximum length of the summary.

        Returns:
            None
        """
        text = "can you send me a summary of the following text in max. " + str(length) + " words without changing the wording of the text: " + text

        request = {
            "custom_id": document_id,
            "method": "POST",
            "url": "/v1/chat/completions",
            "body": {
                "model": "gpt-3.5-turbo-0125",
                "messages": [
                    {
                        "role": "system",
                        "content": "You are a helpful assistant who writes a concise but detailed summary from a text"
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
        """
        Send a batch of requests.

        Parameters:
            batch_name (str): The name of the batch file.

        Returns:
            None
        """
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

        if batch_name == "batch_summary.jsonl":
            with open("batch_ids_summary", 'a') as file:
                file.write('\n' + batch.id)
        else:
            with open("batch_ids_keywords", 'a') as file:
                file.write('\n' + batch.id)

    def retrieve_batch_content(self, batch_id: str, content_type):
        """
        Retrieve the content of a batch.

        Parameters:
            batch_id (str): The ID of the batch.
            content_type (DocumentType): The type of content (SUMMARY or KEYWORDS).

        Returns:
            str: The status of the batch if not completed, otherwise None.
        """
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
        """
        Check the status of a batch.

        Parameters:
            batch_id (str): The ID of the batch.

        Returns:
            str: The status of the batch.
        """
        batch = self.client.batches.retrieve(batch_id)
        return batch.status

    def __process_article_list(self, article_list, user_prompt, expected_categories):
        """
        Process a list of articles.

        Parameters:
            article_list (list): The list of articles to process.
            user_prompt (str): The user prompt containing the problem to be solved.
            expected_categories (list): The expected sentiment categories.

        Returns:
            str: The results of the sentiment analysis.
        """
        thread = self.create_thread()
        provided_data = "\n\n".join(article_list)
        request = ("You are a sentiment analysis assistant with these categories " + str(expected_categories) + ", I give you texts and you give me the results on this topic with these categories") + user_prompt + "\n" + provided_data + "\n" + "Please enter results in this format without text: Date, result"

        self.send_message_to_thread(thread.id, request)
        time.sleep(1)
        run = self.execute_thread_without_function_calling(thread.id)

        while run.status not in ['completed', 'failed']:
            run = self.retrieve_execution(thread.id, run.id)
            print(run.status)
            time.sleep(1)

        time.sleep(0.5)
        result = self.retrieve_messages_from_thread(thread.id).data[0].content[0].text.value
        extracted_result = OpenAIService.__extract_analysis_results(result)

        if len(extracted_result) == 0:
            self.send_message_to_thread(thread, "why not? Just use the provided texts by me")
            time.sleep(1)
            run = self.execute_thread_without_function_calling(thread.id)

            while run.status not in ['completed', 'failed']:
                run = self.retrieve_execution(thread.id, run.id)
                print(run.status)
                time.sleep(1)

            time.sleep(0.5)
            result = self.retrieve_messages_from_thread(thread.id).data[0].content[0].text.value

        result = OpenAIService.__extract_analysis_results(result)
        filtered_result = [item for item in result if item[1].lower() in expected_categories]

        return str(filtered_result).lower()

    @staticmethod
    def __divide_lists(data: list, n: int) -> list[list]:
        """
        Split a list into n sublists of equal size.

        Parameters:
            data (list): The list to split.
            n (int): The number of sublists to create.

        Returns:
            list: A list of sublists.
        """
        k, m = divmod(len(data), n)
        return [data[i * k + min(i, m):(i + 1) * k + min(i + 1, m)] for i in range(n)]

    @staticmethod
    def __add_to_batch(request: dict, file_name: str):
        """
        Add a request to a batch file.

        Parameters:
            request (dict): The request to add.
            file_name (str): The name of the batch file.

        Returns:
            None
        """
        with open(file_name, 'a') as file:
            json_str = json.dumps(request)
            file.write(json_str + '\n')

    @staticmethod
    def __extract_analysis_results(analysis: str):
        """
        Extract analysis results from a string.

        Parameters:
            analysis (str): The analysis string.

        Returns:
            list: A list of extracted results.
        """
        pattern = r'(\d{1,4}[-/]\d{1,2}[-/]\d{2}),\s*(\w+)'
        matches = re.findall(pattern, analysis)

        if len(matches) == 0:
            pattern = r'(\d{1,4}[-/]\d{1,2}[-/]\d{2}):\s*(\w+)'
            matches = re.findall(pattern, analysis)

        return matches

    @staticmethod
    def __extract_generated_code(request: str, data):
        """
        Extract generated code from a request.

        Parameters:
            request (str): The request string.
            data (list): The data to include in the code.

        Returns:
            str: The extracted code.
        """
        try:
            code_match = re.search(r'```python\n(.*?)\n```', request, re.DOTALL)
            if code_match:
                extracted_code = code_match.group(1)
                print(extracted_code)

                data_str = str(data)

                extracted_code = re.sub(r'data\s*=\s*\[\s*\(.*?\)\s*\]', f'data = {data_str}', extracted_code)
                print(extracted_code)

                return extracted_code
        except Exception as e:
            raise RuntimeError("Error when extracting the generated code") from e

    @staticmethod
    def __execute_generated_code(extracted_code: str):
        """
        Execute the extracted code.

        Parameters:
            extracted_code (str): The extracted code to execute.

        Returns:
            None
        """
        try:
            with open("extracted_streamlit_app.py", "w") as code_file:
                code_file.write(extracted_code)

            process = subprocess.Popen(["streamlit", "run", "extracted_streamlit_app.py"],
                                       stdout=subprocess.PIPE,
                                       stderr=subprocess.PIPE
                                       )

            time.sleep(10)
            process.terminate()

            stdout, stderr = process.communicate()

            stdout = stdout.decode('utf-8')
            stderr = stderr.decode('utf-8')
            print(stderr)

            if stderr:
                raise RuntimeError(f"Error during Streamlit execution: {stderr}")

            if os.path.exists("extracted_streamlit_app.py"):
                os.remove("extracted_streamlit_app.py")
                print(f"The file was deleted.")
            else:
                print(f"The file was not found.")
        except Exception as e:
            raise RuntimeError("Error when executing the code") from e

    @staticmethod
    def __create_date_boundaries(time_period: str):
        """
        Create date boundaries from a time period string.

        Parameters:
            time_period (str): The time period in the format YYYY-MM-DD:YYYY-MM-DD.

        Returns:
            tuple: The lower and upper boundaries as days from the initial date.
        """
        initial_date_str = "2010-01-01"
        initial_date = datetime.strptime(initial_date_str, "%Y-%m-%d").date()

        start_date_str, end_date_str = time_period.split(":")

        start_date = datetime.strptime(start_date_str, "%Y-%m-%d").date()
        end_date = datetime.strptime(end_date_str, "%Y-%m-%d").date()

        upper_boundary = end_date - initial_date
        lower_boundary = start_date - initial_date

        return lower_boundary.days, upper_boundary.days

    @staticmethod
    def delete_batch_file(batch_type):
        """
        Delete a batch file.

        Parameters:
            batch_type (DocumentType): The type of document (SUMMARY or KEYWORDS).

        Returns:
            None
        """
        if batch_type == DocumentType.SUMMARY:
            file_name = "batch_ids_summary"
        else:
            file_name = "batch_ids_keywords"

        try:
            os.remove(file_name)
            print(f"File '{file_name}' deleted successfully.")
        except OSError as e:
            print(f"Error deleting file '{file_name}': {e}")

    @staticmethod
    def get_batch_ids(batch_type):
        """
        Get batch IDs from a file.

        Parameters:
            batch_type (DocumentType): The type of document (SUMMARY or KEYWORDS).

        Returns:
            list: A list of batch IDs.
        """
        batch_ids = []
        if batch_type == DocumentType.SUMMARY:
            filename = "batch_ids_summary"
        else:
            filename = "batch_ids_keywords"

        with open(filename, "r") as file:
            for line in file:
                batch_id = line.strip()
                if batch_id:
                    batch_ids.append(batch_id)
        return batch_ids
