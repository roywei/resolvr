#!/usr/bin/env python3

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

import logging
import asyncio
from datetime import datetime
from oncall_agent import OnCallAgent
from fastapi.encoders import jsonable_encoder
import json
from aider_helper import run_aider
from utils.endpoint_utils import es_search
from utils.oai_utils import generate_embedding, chat_completion
import json

app = FastAPI()

#Set up CORS middleware options
allowed_origins = [
    "http://localhost:3001",  # Local development
    "http://localhost:3000",  # Local development
    "https://resolvr-ai.vercel.app",  # Production frontend URL
    # Add other domains as needed
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,  # Use the list of allowed origins
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)

oncall_gent = OnCallAgent()
handled_incidents = []


# root
@app.get("/")
async def root():
    return "Samaritan is running"


@app.get("/log_query")
async def log_query(log_group: str, query: str, query_type: str):
    if query_type == "semantic":
        # Perform semantic search based on the query
        # Implement your logic here
        results = await perform_semantic_search(log_group, query)
    elif query_type == "text":
        # Perform text search based on the query
        # Implement your logic here
        results = await perform_text_search(log_group, query)
    else:
        return {"message": "Invalid query type"}

    return results


async def perform_semantic_search(log_group, query):
    # query rewrite
    instruction = """You are a helpful assistant that generate fake log lines to improve verctor search hit rate. \
            Based on user question and the system (linux serve, spark, zookeeper, etc), generate logs lines that could match what user is looking for directly."""
    user_input = f"""The original query is asking about {log_group} log streams. \
            Generate 3 variations of log lines that could be potential user interest. Do NOT re-write the questions. Output fake log messages directly: """
    new_query = chat_completion(
        instruction=instruction, prompt=user_input + query)
    print("new query is ", new_query)
    query_embedding = generate_embedding(new_query, 128)
    data = {
        "knn": {
            "field": "message-vector",
            "query_vector": query_embedding,
            "k": 10,
            "num_candidates": 10
        },
        "fields": ["message"]
    }
    response = es_search(index=f"{log_group}-index", query=data)
    all_results = response["hits"]["hits"]
    source_array = [result["_source"] for result in all_results]
    score_array = [result["_score"] for result in all_results]
    source_array = [{k: v for k, v in source.items() if not k.endswith("-vector")}
                    for source in source_array]
    source_array = [
        f"{k}: {v}" for source in source_array for k, v in source.items()]
    combined = [source_array[i] + ' ' + source_array[i+1] for i in range(0, len(source_array), 2)]

    source_string = "\n".join(
        [f"Score: {score} {message}, " for score, message in zip(score_array, combined)])
    print("processed ES returned wiht score ", source_string)
    instruction = """You are a helpful assistant that help user come up with answer based on search results. Use stricly information provded in context, do NOT make things up, do NOT use results with low score."""
    user_input = f"""Given the following search results from relevant log liens:
            {source_string}
            Based on the above information, answer the user's question:
            {query}"""
    answer = chat_completion(instruction=instruction, prompt=user_input)
    return {"results": f"{answer}", "evidence": combined}


async def perform_text_search(log_group, query):
    # Implement your text search logic here
    # Example: return results based on text search
    query = {
        "query": {
            "query_string": {
                "query": query
            }
        }
    }
    response = es_search(index=f"{log_group}-index", query=query)
    print(response)
    all_results = response["hits"]["hits"]
    source_array = [result["_source"] for result in all_results]
    source_array = [{k: v for k, v in source.items() if not k.endswith("-vector")}
                    for source in source_array]
    source_array = [
        f"{k}: {v}" for source in source_array for k, v in source.items()]
    combined = [source_array[i] + ' ' + source_array[i+1] for i in range(0, len(source_array), 2)]
    return {"results": "Key word search result", "evidence": combined}



@app.get("/incident_report_all")
async def incident_report_all():
    query = {
        "query": {
            "match_all": {}
        }
    }
    response = es_search("incidents-index", query=query)
    all_results = response["hits"]["hits"]

    # Extract _source field as an array
    source_array = [result["_source"] for result in all_results]

    # Remove fields ending with "-vector"
    source_array = [{k: v for k, v in source.items() if not k.endswith("-vector")}
                    for source in source_array]

    return source_array


@app.get("/rca")
async def rca(request: Request, report_id:str, stack_trace: str):
    # report_id = incident_data.get("report_id")
    # stack_trace = incident_data.get("stack_trace")
    print("starting RCA on ", report_id)
    stack_trace_embedding = generate_embedding(stack_trace, 512)
    data = {
        "knn": {
            "field": "stacktrace-vector",
            "query_vector": stack_trace_embedding,
            "k": 1,
            "num_candidates": 1
        },
        "fields": ["message"]
    }
    response = es_search(index="incidents-index", query=data)
    all_results = response["hits"]["hits"]
    source_array = [result["_source"] for result in all_results]
    #score_array = [result["_score"] for result in all_results]
    source_array = [{k: v for k, v in source.items() if not k.endswith("-vector")}
                    for source in source_array]
    past_report_string = str(source_array[0])
    json_schema = {
        "root_cause": "example root cause",
        "solution": "example solution",
        "relevant_report_id": "example report id"
    }

    json_schema_string = json.dumps(json_schema)

    instruction = f"""You are a helpful assistant that helo with oncall root cause analysis, you will be given a stack trace and an error, followed by \
        relevant past incident report and solutions. Your goal is to ouput possible root cause and possible solution. Return only Json data with schema: {json_schema_string}"""
    user_input = f"""The stack trace is {stack_trace} \
            and the relevant incident reports is as following: {past_report_string} \
            return only json with schema {json_schema_string} """
    solution = chat_completion(
        instruction=instruction, prompt=user_input, json_mode=True)
    return json.loads(solution)


# incident endpoint
@app.post("/incident")
async def process_incident(request: Request, incident_data: dict):
    # Process the incident data here
    # You can perform any necessary operations with the provided data

    # Get request information
    ip_address = request.client.host
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Extract incident data
    error_message = incident_data.get("error_message")
    stack_trace = incident_data.get("stack_trace")
    additional_info = incident_data.get("additional_info")

    # Check if incident has already been handled
    if (error_message, stack_trace) in handled_incidents:
        return {"message": "Incident already handled"}

    # Print request information
    logging.error(f"Received incident from:")
    logging.error(f"IP Address: {ip_address}")
    logging.error(f"Time: {current_time}")

    logging.error(f"Error Message: {error_message}")
    logging.error(f"Stack Trace: {stack_trace}")
    logging.error(f"Additional Info: {additional_info}")

    # Mark incident as handled
    handled_incidents.append((error_message, stack_trace))

    asyncio.create_task(handle_incident(
        error_message, stack_trace, additional_info))
    # Return a response if needed
    return {"message": "Incident handled successfully"}


async def handle_incident(error_message, stack_trace, additional_info):
    logging.warn(f"Oncall agent is invoked!")
    response = oncall_gent.research_incident(
        error_message, stack_trace, additional_info)
    root_cause = response.content[0].text.value
    root_cause = root_cause.strip('`').strip('json').strip()
    # Assuming `root_cause` is a JSON string
    try:
        root_cause_json = json.loads(root_cause)
        # Do something with root_cause_json
    except json.JSONDecodeError as e:
        print("Failed to parse JSON. Error:", e)
        print("Raw string:", root_cause)
        return
    except Exception as e:
        print("An unexpected error occurred:", e)
        return
    # Access the values of the fields
    file = root_cause_json['file']
    area = root_cause_json['area']
    instruction = root_cause_json['instruction']
    report = root_cause_json['report_name']

    # Do something with the values
    print("Found solution based on this incident report:")
    print(report)

    # Read the report content and print it out
    with open('../incident_reports/' + report, 'r') as f:
        report_content = f.read()
        print("Report Content:")
        print(report_content)

    print("Now trying to fix the problem!")
    file_path = '/home/roywei/workspace/next13-ecommerce-store/'+file
    print("file path: ", file_path)
    print("instruction: ", instruction)
    print("area in file: ", area)
    run_aider(file_path, instruction, area_to_focus=area)
