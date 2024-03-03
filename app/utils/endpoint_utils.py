import requests
import json

from elasticsearch import Elasticsearch
from pinecone import Pinecone
from dotenv import find_dotenv, dotenv_values

config = dotenv_values(find_dotenv())


def get_es_client():
    es_client = Elasticsearch(
        config["ES_ENDPOINT"],  # Elasticsearch endpoint
        api_key=config["ES_API_KEY"],  # API key ID and secret
    )
    print(es_client.info())
    return es_client


def es_search(index, query):
    url = f"{config['ES_ENDPOINT']}/{index}/_search"
    headers = {
        "Authorization": f"ApiKey {config['ES_API_KEY']}",
        "Content-Type": "application/json",
    }
    print("url is", url)
    print("headre is ", headers)
    if isinstance(query, dict):
        query = json.dumps(query)
    response = requests.post(url, headers=headers, data=query)
    return response.json()


def get_pc_client():
    pc_client = Pinecone(api_key=config["PC_API_KEY"])
    return pc_client
