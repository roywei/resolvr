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

def insert_incident(file):
    es_client = get_es_client()
    with open(file, 'r') as f:
        data = json.load(f)
        es_insert_report(es_client,"incidents-index", data, update=False)

def insert_folder(path, delete=False, update=False):
    es_client = get_es_client()
    query = {"query" : { 
        "match_all" : {}
    }
    }
    if delete:
        es_client.delete_by_query(index='incidents-index', body=query)
    for filename in os.listdir(path):
        if filename.endswith('.json'):
            file_path = os.path.join(path, filename)
            with open(file_path, 'r') as file:
                data = json.load(file)
                es_insert_report(es_client,"incidents-index", data, update=update)


def convert_spark_to_iso8601(timestamp_str):
    # Assuming your timestamp is in the format 'yy/MM/dd HH:mm:ss'
    dt = datetime.strptime(timestamp_str, '%y/%m/%d %H:%M:%S')
    return dt.isoformat()

def convert_linux_to_iso8601(timestamp_str):
    # Assuming your timestamp is in the format 'yy/MM/dd HH:mm:ss'
    try:
        dt = datetime.strptime(timestamp_str, "%b %d %H:%M:%S")
        return dt.isoformat()
    except Exception as e:
        print("Error converting datetime ", e)
        return timestamp_str


def parse_logline(line, log_type):
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
        
        #Prepare the document to be inserted
        if log_type =='linux':
            timestamp = convert_linux_to_iso8601(timestamp),
        elif log_type == 'spark':
            timestamp = convert_spark_to_iso8601(timestamp),
        
        document = {
             'timestamp': timestamp,
             'message': message,
             'message-vector': []
        }
        
        return document
    except Exception as e:
        print(f"Error inserting log entry: {e}")

def gen_data(es_index, documents):
    for doc in documents:
        yield {
            "_index": es_index,
            "_source": doc
        }


def insert_logs(log_file_path, log_type):
    output_file = log_file_path+".json"
    if not os.path.exists(output_file):
        documents = []
        lines = []
        with open(log_file_path, 'r') as file:
            for line in file:
                line = line.strip()
                if line:  # Skip empty lines
                    document = parse_logline(line, log_type)
                    if document:
                        lines.append(line)
                        documents.append(document)
        embeddings = generate_embedding(lines, 128)  # Get the embedding for the message
        print(embeddings)
        assert len(embeddings) == len(documents), f"embeddings len is {len(embeddings), {len(documents)}}"
        for i, embedding in enumerate(embeddings):
            documents[i]["message-vector"] = embedding

        # Store documents as a local file

        with open(output_file, 'w') as f:
            json.dump(documents, f)
    else:
        with open(output_file, "r") as f:
            documents = json.loads(f.read())
        print("reading from file")
        print(documents)
    
    es_client = get_es_client()
    body = []
    for item in documents:
        body.append({ "index": { "_index": f"{log_type}-index"}})
        body.append(item)
    es_client.bulk(body=body)


insert_incident('sample_data/incidents/IR-20240208-001.json')
#insert_folder('sample_data/incidents/', delete=False)
#insert_logs('sample_data/logs/Linux_2k.log', 'linux')
#insert_logs('sample_data/logs/Spark_2k.log', 'spark')