import os
from openai import OpenAI
from dotenv import find_dotenv, dotenv_values


config = dotenv_values(find_dotenv())
os.environ["OPENAI_API_KEY"] = config["OPENAI_API_KEY"]


# Assuming an embedding function that returns a list of floats representing the embedding
def generate_embedding(text, dimensions):
    oai_client = get_oai_client()
    response = oai_client.embeddings.create(
        model="text-embedding-3-small", input=text, dimensions=dimensions
    )
    if type(text) == str:
        return response.data[0].embedding
    else:
        return [item.embedding for item in response.data]


def chat_completion(instruction, prompt, json_mode=False):
    try:
        if json_mode:
            response = get_oai_client().chat.completions.create(
                model="gpt-4-turbo-preview",
                messages=[
                    {"role": "system", "content": instruction},
                    {"role": "user", "content": prompt},
                ],
                response_format={"type": "json_object"},
            )
        else:
            response = get_oai_client().chat.completions.create(
                model="gpt-4-turbo-preview",
                messages=[
                    {"role": "system", "content": instruction},
                    {"role": "user", "content": prompt},
                ],
            )
        return response.choices[0].message.content

    except Exception as e:
        print("Error calling Openai: ", e)


def get_oai_client():
    oai_client = OpenAI()
    return oai_client
