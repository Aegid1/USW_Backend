import json
import os
from app.services.MediaService import MediaService, DocumentType
from app.services.OpenAIService import OpenAIService
class BatchApiService:

    openaiservice = OpenAIService()
    mediaservice = MediaService()

    # TODO keywords of an article is not used anywhere, maybe delete afterwards
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

    # das hier muss an die Batch-API gesendet werden -> eigener Batch
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
        """
                Send a batch of requests.

                Parameters:
                    batch_name (str): The name of the batch file.

                Returns:
                    None
        """
        batch_input_file = self.openaiservice.client.files.create(
            file=open(batch_name, "rb"),
            purpose="batch"
        )
        batch = self.openaiservice.client.batches.create(
            input_file_id=batch_input_file.id,
            endpoint="/v1/chat/completions",
            completion_window="24h",
            metadata={
                "description": "nightly eval job"
            }
        )

        if (batch_name == "batch_summary.jsonl"):
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
        batch = self.openaiservice.client.batches.retrieve(batch_id)
        if batch.status != "completed":
            return "Your batch is currently not ready and in the state: " + batch.status

        output_file = self.openaiservice.client.files.content(batch.output_file_id)

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
        batch = self.openaiservice.client.batches.retrieve(batch_id)
        return batch.status

    def delete_batch_file(self, batch_type):
        """
                Delete a batch file which contains the ids of the batches.

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

    def get_batch_ids(self, batch_type):
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

    def __add_to_batch(self, request: dict, file_name: str):
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

