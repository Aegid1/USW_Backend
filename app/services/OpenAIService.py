import json
import os
import subprocess
import threading
import time
import re
import ast
from datetime import datetime

import yaml
from openai import OpenAI
import concurrent.futures
from app.services.MediaService import MediaService, DocumentType


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
                    "required": ["topic", "user_prompt", "chart_type", "time_period", "sentiment_categories"]
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
    def solve_problem_parallelization(topic: str, user_prompt: str, chart_type: str, time_period: str,
                                      sentiment_categories: list):
        """
                Solve a problem/analysis in parallel using multiple threads.

                Parameters:
                    topic (str): The topic of the user request.
                    user_prompt (str): The user prompt containing the problem to be solved.
                    chart_type (str): The type of visualization requested.
                    time_period (str): The time period to be considered.
                    sentiment_categories (list): The sentiment categories mentioned in the analysis.

                Returns:
                    str: The result of the problem-solving process.
        """

        #check if something is missing and tell the user afterwards
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
            return f"Tell the user that the following parameters are missing or invalid: {', '.join(missing_params)}"

        print(chart_type)
        print(sentiment_categories)
        print(time_period)
        print(topic)

        #check if the provided date is valid or not
        date_is_valid = OpenAIService.__check_date(time_period)
        if not date_is_valid:
            return "Tell the user that the time period is invalid"

        lower_boundary, upper_boundary = OpenAIService.__create_date_boundaries(time_period)

        mediaservice = MediaService()
        openai_service = OpenAIService()

        thread_id = openai_service.create_thread()
        #check if a time series is wanted -> time series visualization is more complex
        time_series_synonyms = ["timeseries", "time series", "linechart", "line chart"]

        if chart_type.lower() in time_series_synonyms:
            #we need more data when having a time series -> sometimes multiple articles on one day
            #we want for every day atleast 2 articles, so it is multiplied by 2
            articles = mediaservice.get_articles_by_date((upper_boundary-lower_boundary) * 2, topic, lower_boundary, upper_boundary)
            articles = mediaservice.filter_documents_by_time_interval(articles, lower_boundary, upper_boundary)

        else:
            #gpt 3.5 can only handle up to 200 - 300 articles with 100 words each article -> otherwise it will throw an error therefore * 0.7
            articles = mediaservice.get_articles_by_date(int((upper_boundary-lower_boundary)*0.7), topic, lower_boundary, upper_boundary)


        articles_without_date = articles.get("documents")[0]
        for i in range(len(articles.get("metadatas")[0])):
            articles_without_date[i] += " " + articles.get("metadatas")[0][i].get("published")

        articles_divided = OpenAIService.__divide_lists(articles_without_date, int(len(articles.get("documents")[0]) / 10))

        results = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=int(len(articles.get("documents")[0]) / 10)) as executor:
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

        flattened_results = []
        #combines the results for one final result
        for sublist_str in results:
            sublist = ast.literal_eval(sublist_str)
            flattened_results.extend(sublist)

        request = ("Can you generate the directly executable python script for me to create a "
                   + chart_type + " with streamlit with a pattern like this, where you have a list of tuples: "
                   + "\n" + "data = [('2024-05-08', '3')]"
                   )

        openai_service.send_message_to_thread(thread_id.id, request)
        time.sleep(1)

        run = openai_service.execute_thread_without_function_calling(thread_id.id)

        #executes the code generation prompt
        while run.status not in ['completed', 'failed']:
            run = openai_service.retrieve_execution(thread_id.id, run.id)
            print(run.status)
            time.sleep(1)

        final_result = openai_service.retrieve_messages_from_thread(thread_id.id).data[0].content[0].text.value
        try:
            extracted_code = OpenAIService.__extract_generated_code(final_result, flattened_results)
            #OpenAIService.__execute_generated_code(extracted_code)
            print(extracted_code)
            thread = threading.Thread(target=OpenAIService.__execute_generated_code)
            thread.start()

        except RuntimeError as e:
            return "Tell the user something went wrong with the execution of the generated code"

        return "Here is the desired " + chart_type

    @staticmethod
    def solve_problem(topic: str, user_prompt: str, chart_type: str, time_period: str, sentiment_categories: list):
        """
                Solve a problem/analysis using a single thread.

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

        request = "Can you generate the python code for me to create a " + chart_type + " with streamlit (make sure to flatten the lists) with the following data: " + "\n" + "\n".join(
            results)

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

    #executes the chosen function
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

            #the chosen function is executed here
            output = function_to_call(**function_args)
            if output:
                tool_output_array.append({"tool_call_id": tool_call_id, "output": output})

        return self.client.beta.threads.runs.submit_tool_outputs(
            thread_id=thread_id,
            run_id=run_id,
            tool_outputs=tool_output_array
        )

    def __process_article_list(self, article_list, user_prompt, expected_categories):
        """
                Process a list of articles and generate the sub-results for the final result.

                Parameters:
                    article_list (list): The list of articles to process.
                    user_prompt (str): The user prompt containing the problem to be solved.
                    expected_categories (list): The expected sentiment categories.

                Returns:
                    str: The results of the sentiment analysis.
        """
        thread = self.create_thread()
        provided_data = "\n\n".join(article_list)

        #prompt for generating the sub-result
        request = ("You are a sentiment analysis assistant" + "with these categories " + str(
            expected_categories) + ", I give you texts and you give me the results on "
                                   " this topic with these categories") + user_prompt + "\n" + provided_data + "\n" + (
                      "Please enter results in this format without text: Date, result"
        )

        self.send_message_to_thread(thread.id, request)
        time.sleep(1)
        run = self.execute_thread_without_function_calling(thread.id)

        while run.status not in ['completed', 'failed']:
            run = self.retrieve_execution(thread.id, run.id)
            print(run.status)
            time.sleep(1)

        result = self.retrieve_messages_from_thread(thread.id).data[0].content[0].text.value
        extracted_result = OpenAIService.__extract_analysis_results(result)

        #if the extracted result is bad and the model doesnt give us the result we ask why
        if (len(extracted_result) == 0):
            #this prompt mostly solves the problem, the gpt-model-3.5 seems sometimes a little confused with these types of tasks
            self.send_message_to_thread(thread, "why not? Just use the provided texts by me")
            time.sleep(1)
            run = self.execute_thread_without_function_calling(thread.id)

            while run.status not in ['completed', 'failed']:
                run = self.retrieve_execution(thread.id, run.id)
                print(run.status)
                time.sleep(1)

            result = self.retrieve_messages_from_thread(thread.id).data[0].content[0].text.value

        result = OpenAIService.__extract_analysis_results(result)
        #filter out the bad results that dont match the expected results
        filtered_result = [item for item in result if item[1].lower() in expected_categories]

        return str(filtered_result).lower()

    def __divide_lists(dself, data: list, n: int) -> list[list]:
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

    def __extract_analysis_results(self, analysis: str):
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

    def __extract_generated_code(self, request: str, data):
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

                with open("extracted_streamlit_app.py", "w") as code_file:
                    code_file.write(extracted_code)

                # TODO this name is currently only hard coded
                return "extracted_streamlit_app.py"
        except Exception as e:
            raise RuntimeError("Error when extracting the generated code") from e

    def __execute_generated_code(self):
        """
                Execute the extracted code.

                Parameters:
                    extracted_code (str): The extracted code to execute.

                Returns:
                    None
        """
        try:
            #TODO this name is currently only hard coded
            process = subprocess.Popen(["streamlit", "run", "extracted_streamlit_app.py"],
                                       stdout=subprocess.PIPE,
                                       stderr=subprocess.PIPE
                                       )
            #time.sleep(30)
            #process.terminate()

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

    def __create_date_boundaries(self, time_period: str):
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

    def __check_date(self, time_period):
        """
            Check if the provided time period is valid.

            Parameters:
                time_period (str): The time period in the format 'YYYY-MM-DD:YYYY-MM-DD'.

            Returns:
                bool: True if the time period is valid, False otherwise.
                str: Error message if the time period is invalid.
        """
        try:
            start_date_str, end_date_str = time_period.split(':')

            start_date_obj = datetime.strptime(start_date_str, '%Y-%m-%d')
            end_date_obj = datetime.strptime(end_date_str, '%Y-%m-%d')

            today = datetime.now().date()

            min_year = 2010

            if start_date_obj.date() > today:
                return False
            elif start_date_obj.date().year < min_year:
                return False

            if end_date_obj.date() > today:
                return False
            elif end_date_obj.date().year < min_year:
                return False

            if end_date_obj < start_date_obj:
                return False

            return True

        except ValueError:
            return False
