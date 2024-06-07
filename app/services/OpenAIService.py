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
            futures = [executor.submit(self.__process_batch, batch, user_prompt) for batch in articles_divided]
            concurrent.futures.wait(futures)
            for future in concurrent.futures.as_completed(futures):
                try:
                    result = future.result()
                    results.append(result.data[0].content[0].text.value)
                except Exception as exc:
                    print(f"Batch generated an exception: {exc}")

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

    def __divide_lists(self, data: list, n: int) -> list[list]:
        """Teilt eine Liste in n gleichgroße Unterlisten auf"""
        k, m = divmod(len(data), n)
        return [data[i * k + min(i, m):(i + 1) * k + min(i + 1, m)] for i in range(n)]

    def __process_batch(self, batch, user_prompt):
        thread_id = self.create_thread_id()
        request = "\n\n".join(batch)
        request = user_prompt + "\n" + request

        result = self.send_message_to_thread(thread_id, request)
        #maybe kill the thread afterwards?

        return result
