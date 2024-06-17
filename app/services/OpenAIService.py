import json
import time

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
                # hier noch mit dem prompt engineering rumprobieren -> vielleicht mit Hinweis auf code generierung
                "description": "Löse das problem, das aus dem user request hervorgeht, dass sich auf ein politisches Problem bezieht.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Die query, welche die benötigten Daten aus der chromadb sammelt um das problem zu lösen"
                        },
                        "user_prompt": {
                            "type": "string",
                            "description": "Der user prompt, der das problem beinhaltet, das gelöst werden soll"
                        }
                    },
                    "required": ["query", "user_prompt"]
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
    def solve_problem_with_parallelization(query: str, user_prompt: str):

        mediaservice = MediaService()
        openai_service = OpenAIService()
        thread_id = openai_service.create_thread()

        #laden wir hier wirklich schon alle Artikel auf einmal rein?
        articles = mediaservice.get_articles(10, query=query)
        articles_divided = OpenAIService.__divide_lists(articles.get("documents")[0], 5)

        results = []

        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(openai_service.__process_article_list, article_list, user_prompt) for
                       article_list in
                       articles_divided]
            concurrent.futures.wait(futures)
            for future in concurrent.futures.as_completed(futures):
                try:
                    result = future.result()
                    print(result)
                    results.append(result.data[0].content[0].text.value)
                except Exception as exc:
                    print(f"list of articles generated an exception: {exc}")

        #combines the results for one final result
        request = user_prompt + "\n" + "\n\n".join(results)
        openai_service.send_message_to_thread(thread_id.id, request)
        time.sleep(2)
        openai_service.execute_thread(thread_id.id)
        return openai_service.retrieve_messages_from_thread(thread_id.id)

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
        request = user_prompt + "\n" + ("mit den folgenden Materialien (ohne Veränderung des Wortlauts in den "
                                        "Artikeln), sodass es als Zwischenergebnis für folgende Analysen verwendet "
                                        "werden kann") + "\n\n".join(results)

        openai_service.send_message_to_thread(thread_id.id, request)
        time.sleep(2)
        openai_service.execute_thread_without_function_calling(thread_id.id)
        messages = openai_service.retrieve_messages_from_thread(thread_id.id)
        return messages.data[0].content[0].text.value

    function_lookup = {
        "solve_problem": solve_problem
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

    #even necessary anymore?
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
            instructions="you are an analyst that does sentiment-analysis of media-articles, talk in a professional and reasoning way"
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
        text = "kannst du mir lediglich 5 keywords zu folgendem Artikel nennen ohne Nummerierung oder Vergleichbares" + text

        request = {
            "custom_id": document_id,
            "method": "POST",
            "url": "/v1/chat/completions",
            "body": {
                "model": "gpt-3.5-turbo-0125",
                "messages": [
                    {
                        "role": "system",
                        "content": "Du bist ein hilfreicher Assistent, der anhand eines Artikels 5 repräsentative Keywords ableitet,"
                                   "die er nacheinander, nur durch ein Komma getrennt, nennt."
                    },
                    {
                        "role": "user",
                        "content": text
                    }
                ],
                "max_tokens": 1000
            }
        }
        return self.__add_to_batch(request, "test_batch.jsonl")

    #das hier muss an die Batch-API gesendet werden -> eigener Batch
    def create_summary(self, document_id: str, text: str, length):
        text = "kannst du mir Zusammenfassung des folgenden Artikels in " + length + " Wörtern geben" + text

        request = {
            "custom_id": document_id,
            "method": "POST",
            "url": "/v1/chat/completions",
            "body": {
                "model": "gpt-3.5-turbo-0125",
                "messages": [
                    {
                        "role": "system",
                        "content": "Du bist ein hilfreicher Assistent, der eine prägnante aber detaillierte Zusammenfassung"
                                   "aus einem Artikel schreibst"
                    },
                    {
                        "role": "user",
                        "content": text
                    }
                ],
                "max_tokens": 1000
            }
        }
        return self.__add_to_batch(request, "test_batch.jsonl")

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
            file.write(batch.id)

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

    def __process_article_list(self, article_list, user_prompt):
        thread_id = self.create_thread()
        request = "\n\n".join(article_list)
        request = user_prompt + "\n" + request

        self.send_message_to_thread(thread_id.id, request)
        time.sleep(1)
        run = self.execute_thread_without_function_calling(thread_id.id)

        while run.status not in ['completed', 'failed']:
            run = self.retrieve_execution(thread_id.id, run.id)
            print(run.status)
            time.sleep(1)

        print("----------------------------------------------------------------------------")
        print("JETZT IST FERTIG")
        return self.retrieve_messages_from_thread(thread_id.id)

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
