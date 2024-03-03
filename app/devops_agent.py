"""
DevOpsAgent class is responsible for communicating with user and the OpenAI API.
"""

import time

from openai import OpenAI
from dotenv import find_dotenv, dotenv_values

config = dotenv_values(find_dotenv())


class DevOpsAgent:
    def __init__(self):
        self.client = OpenAI(api_key=config["OPENAI_API_KEY"])
        if not config["RESOLVR_ID"]:
            raise RuntimeError("RESOLVR_ID not found in .env file")
        else:
            self.assistant_id = config["RESOLVR_ID"]
            print("using existing id: ", self.assistant_id)

    def chat(self, user_message):
        print(f"Resolver is thinking")
        thread = self.client.beta.threads.create()
        message = self.client.beta.threads.messages.create(
            thread_id=thread.id,
            role="user",
            content=user_message,
        )
        run = self.client.beta.threads.runs.create(
            thread_id=thread.id,
            assistant_id=self.assistant_id,
            # tools=[{"type": "retrieval"}],
        )
        while run.status != "completed":
            run = self.client.beta.threads.runs.retrieve(
                thread_id=thread.id, run_id=run.id
            )
            print(run.status)
            if run.status == "failed":
                print("run failed!")
                break
            time.sleep(1)
        messages = self.client.beta.threads.messages.list(thread_id=thread.id)
        return messages.data[0].content
