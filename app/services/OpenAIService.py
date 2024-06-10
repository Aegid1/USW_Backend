import json
import yaml
from openai import OpenAI
import concurrent.futures
from app.services.MediaService import MediaService


class OpenAIService:
    config = yaml.safe_load(open("openai_config.yaml"))
    client = OpenAI(api_key=config['KEYS']['openai'])

    mediaservice = MediaService()
    #metadata of the given functions
    tools = []

    function_lookup = {}

    assistant = client.beta.assistants.create(
        name="Email Assistant",
        instructions="You are an assistant who has access to media articles that are about political topics.",
        tools=tools,
        model="gpt-3.5-turbo-0125"
    )

    def solveProblem(self, query: str, user_prompt: str):
        #laden wir hier wirklich schon alle Artikel auf einmal rein?
        articles = self.mediaservice.get_articles(10, query=query)
        articles_divided = self.__divide_lists(articles, 5)
        print(len(articles_divided))

        results = []

        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(self.__process_article_list, article_list, user_prompt) for article_list in articles_divided]
            concurrent.futures.wait(futures)
            for future in concurrent.futures.as_completed(futures):
                try:
                    result = future.result()
                    results.append(result.data[0].content[0].text.value)
                except Exception as exc:
                    print(f"list of articles generated an exception: {exc}")

        thread_id = self.create_thread_id()

        #combines the results for one final result
        request = user_prompt + "\n" + "\n\n".join(results)

        return self.send_message_to_thread(thread_id, request)


    def create_thread_id(self):
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
            instructions="we are two good knight buddies, can you please talk like a knight with old-fashioned expressions"
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
        self.__add_to_batch(request, "test_batch.jsonl")

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
        self.__add_to_batch(request, "test_batch.jsonl")


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
        #TODO() check the status of the batch
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
        #TODO()
        pass

    def __add_to_batch(self, request: dict, file_name: str):
        with open(file_name, 'a') as file:
            json_str = json.dumps(request)
            file.write(json_str + '\n')

    def __divide_lists(self, data: list, n: int) -> list[list]:
        """Teilt eine Liste in n gleichgroße Unterlisten auf"""
        k, m = divmod(len(data), n)
        return [data[i * k + min(i, m):(i + 1) * k + min(i + 1, m)] for i in range(n)]

    def __process_article_list(self, article_list, user_prompt):
        thread_id = self.create_thread_id()
        request = "\n\n".join(article_list)
        request = user_prompt + "\n" + request

        result = self.send_message_to_thread(thread_id, request)

        return result