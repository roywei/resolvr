import os
from openai import OpenAI
from dotenv import find_dotenv, dotenv_values


config = dotenv_values(find_dotenv())
os.environ['OPENAI_API_KEY'] = config['OPENAI_API_KEY']

# Assuming an embedding function that returns a list of floats representing the embedding
def generate_embedding(text, dimensions):
    oai_client = get_oai_client()
    response = oai_client.embeddings.create(model="text-embedding-3-small",
                                            input=text, 
                                            dimensions=dimensions)
    embedding = response.data[0].embedding
    return embedding


def get_oai_client():
    oai_client = OpenAI()
    return oai_client




