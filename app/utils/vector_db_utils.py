import os
import json
import re
from datetime import datetime

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


def convert_to_iso8601(timestamp_str):
    # Assuming your timestamp is in the format 'yy/MM/dd HH:mm:ss'
    dt = datetime.strptime(timestamp_str, '%y/%m/%d %H:%M:%S')
    return dt.isoformat()


def insert_log_entry(es_client, line, log_type):
    try:
        if log_type == "linux":
            regex = r"(\b[A-Za-z]{3} +\d{1,2} \d{2}:\d{2}:\d{2}\b)"
        elif log_type == 'spark':
            regex = r"(\d{2}:\d{2}:\d{2})"
        # Split line by timestamp and message
        matches = re.finditer(regex, line)
        end_index = next(matches).end() if matches else None
        if end_index is not None:
            # Everything after the timestamp is considered the message
            message = line[end_index:].strip()  # Strip leading/trailing whitespaces
            timestamp = line[:end_index].strip()
            print(f"Timestamp: '{timestamp}', Message: '{message}'")
        else:
            print("Timestamp not found.")
        
        # Generate embedding
        embedding = generate_embedding(message, 128)  # Get the embedding for the message
        
        #Prepare the document to be inserted
        document = {
             'timestamp': convert_to_iso8601(timestamp),
             'message': message,
             'message-vector': embedding
        }
        
        # Insert the document into Elasticsearch
        es_client.index(index=f"{log_type}-index", document=document)
    except Exception as e:
        print(f"Error inserting log entry: {e}")


def insert_logs(log_file_path, log_type):
    es_client = get_es_client()
    with open(log_file_path, 'r') as file:
        for line in file:
            line = line.strip()
            if line:  # Skip empty lines
                insert_log_entry(es_client, line, log_type)


#insert_folder('sample_data/incidents/', delete=True)
#insert_logs('sample_data/logs/Linux_2k.log', 'linux')
insert_logs('sample_data/logs/Spark_2k.log', 'spark')