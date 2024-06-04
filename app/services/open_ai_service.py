import yaml
from openai import OpenAI


class OpenAIService:
    config = yaml.safe_load(open("../config_empty.yaml"))
    client = OpenAI(api_key=config['KEYS']['openai'])

    assistant = client.beta.assistants.create(
        name="Email Assistant",
        instructions="You are an assistant who has access to Emails and the web.",
        tools=[],
        model="gpt-3.5-turbo-0125"
    )

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

    def execute_thread(self, thread_id):
        return self.client.beta.threads.runs.create(
            thread_id=thread_id,
            assistant_id=self.assistant.id,
            instructions="Please address the user as my Lord. The user has a premium account."
        )

    def retrieve_execution(self, thread_id, run_id):
        return self.client.beta.threads.runs.retrieve(thread_id=thread_id, run_id=run_id)

    def retrieve_messages_from_thread(self, thread_id):
        return self.client.beta.threads.messages.list(thread_id=thread_id)