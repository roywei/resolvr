import os
import json

from oai_utils import generate_embedding
from endpoint_utils import get_es_client


def es_insert_report(es_client, index, doc, update=False):
    # Concatenate the stack trace for embedding
    stack_trace_text = " ".join(doc["stack_trace"])
    stack_trace_embedding = generate_embedding(stack_trace_text, 512)
    print("len of stack_trace_embedding embedding is", len(stack_trace_embedding))

    # Concatenate all textual information for another embedding
    full_text = f"{doc['title']} {doc['error_name']}  {doc['description']} {doc['solution']} {' '.join(doc['stack_trace'])}"
    full_text_embedding = generate_embedding(full_text, 512)
    print("len of fulltext embedding is", len(full_text_embedding))

    # Adding embeddings to the document
    doc["stacktrace-vector"] = stack_trace_embedding
    doc["fulltext-vector"] = full_text_embedding

    # Index the document (replace 'postmortem_index' with your index name)
    if update:
        es_client.update(index=index, id=doc["report_id"], body=doc)
    else:
        es_client.index(index=index, id=doc["report_id"], body=doc)


def merge_updates(updates):
    return [f"{update['update_time']} - {update['update_description']}" for update in updates]


def pc_insert_report(pc_idnex, doc):
    # Concatenate the stack trace for embedding
    stack_trace_text = " ".join(doc["stack_trace"])
    stack_trace_embedding = generate_embedding(stack_trace_text)

    # Concatenate all textual information for another embedding
    # full_text = f"{doc['title']} {doc['description']} {doc['solution']} {' '.join(doc['stack_trace'])}"
    # full_text_embedding = generate_embedding(full_text)

    doc["updates"] = merge_updates(doc['updates'])

    pc_idnex.upsert(
        vectors=[
            {
                "id": doc["title"],
                "values": stack_trace_embedding,
                "metadata": doc
            }
        ],
        namespace="stack_trace_embedding"
    )


def insert_folder(path, delete=False, update=False):
    es_client = get_es_client()
    query = {"query" : { 
        "match_all" : {}
    }
    }
    es_client.delete_by_query(index='incidents-index', body=query)
    for filename in os.listdir(path):
        if filename.endswith('.json'):
            file_path = os.path.join(path, filename)
            with open(file_path, 'r') as file:
                data = json.load(file)
                es_insert_report(es_client,"incidents-index", data, update=update)

insert_folder('sample_data/incidents/', delete=True)
