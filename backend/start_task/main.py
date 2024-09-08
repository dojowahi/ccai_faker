import json
from google.cloud import pubsub_v1
from google.cloud import firestore
import os
import datetime
import base64
import uuid
import time
from vertexai.generative_models import GenerativeModel, GenerationConfig, HarmCategory, HarmBlockThreshold
from google.cloud import storage
from google.api_core.exceptions import TooManyRequests

bucket_name = os.getenv('BUCKET_NAME')
project_id = os.getenv("PROJECT_ID")
topic_id = os.getenv("TASK_TOPIC_ID") #Topic where tasks will be inserted
db_firestore = os.getenv('FIRESTORE_DB') #ccai_faker
model_name = os.getenv('GEMINI_MODEL')
current_timestamp = datetime.datetime.now().strftime("%Y%m%d%H%M%S")



publisher = pubsub_v1.PublisherClient()
topic_path = publisher.topic_path(project_id, topic_id)
model = GenerativeModel(model_name=model_name)
db = firestore.Client(database=db_firestore)

def publish_to_pubsub(message):
    message_data = json.dumps(message).encode("utf-8")
    future = publisher.publish(topic_path, message_data)
    future.result()

def get_gemini_response(model,prompt,generation_config,max_retries=3):
    for retry_count in range(max_retries):
        try:
            response = model.generate_content(prompt, generation_config=generation_config)
            return response.text  # Assuming you only need the text
        except TooManyRequests as e:
            if retry_count < max_retries - 1:  # Don't sleep on the last attempt
                sleep_duration = 2 ** retry_count  # Exponential backoff
                print(f"Rate limit exceeded. Retrying in {sleep_duration} seconds...")
                time.sleep(sleep_duration)
            else:
                print(f"Max retries reached. Giving up on this request: {e}")
                raise 

safety_settings = {
    HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
    HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
    HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
    HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
}

def load_prompt(object_name):
    """Function to load a prompt from a file"""
    try:
        storage_client = storage.Client()

        # Get the bucket
        bucket = storage_client.bucket(bucket_name)

        # Get the blob (file)
        blob = bucket.blob(object_name)

        # Download the file content
        file_content = blob.download_as_string().decode('utf-8')
        # print(f"Prompt Content:{file_content}")

        return file_content
    except Exception as e:
        return f"Error loading prompt: {e}"

#Generate sample data which will be inserted into Firestore DB    
def generate_lists(group_id,company_name,company_website,company_reviews,temperature,start_date,end_date):
    generation_config = GenerationConfig(
    temperature=temperature,
    top_p=1.0,
    top_k=32,
    candidate_count=1,
    max_output_tokens=2048,
)
    service_prompt_file_path = "prompts/ccai_service_prompt.txt"
    service_prompt = load_prompt(service_prompt_file_path).replace("company_name",company_name).replace("url",company_website)
    problem_prompt_file_path = "prompts/ccai_problem_prompt.txt"
    problem_prompt = load_prompt(problem_prompt_file_path).replace("company_name",company_name).replace("review_website",company_reviews)
    greeting_prompt_file_path = "prompts/ccai_greeting_prompt.txt"
    greeting_prompt = load_prompt(greeting_prompt_file_path).replace("company_name",company_name)

    
    agent_prompt_file_path = "prompts/ccai_agent_prompt.txt"
    agent_name_prompt = load_prompt(agent_prompt_file_path).replace("company_name",company_name)
    closing_prompt_file_path = "prompts/ccai_closing_prompt.txt"
    closing_prompt = load_prompt(closing_prompt_file_path).replace("company_name",company_name)
  
    closing_response_prompt_file_path = "prompts/ccai_closing_response_prompt.txt"
    closing_response_prompt = load_prompt(closing_response_prompt_file_path).replace("company_name",company_name)
    service = get_gemini_response(model,service_prompt, generation_config=generation_config)
    problem = get_gemini_response(model,problem_prompt, generation_config=generation_config)
    greeting = get_gemini_response(model,greeting_prompt, generation_config=generation_config)
    agent = get_gemini_response(model,agent_name_prompt, generation_config=generation_config)
    closing_remarks = get_gemini_response(model,closing_prompt, generation_config=generation_config)
    closing_response = get_gemini_response(model,closing_response_prompt, generation_config=generation_config)

    services_text = service.strip()[1:-1].replace('"', '').split(",")

    problems_text = problem.strip()[1:-1].replace('"', '').replace("\n", "").split(",")

    greetings_text = greeting.strip()[1:-1].replace('"', '').replace("\n", "").split(",")

    # agent_names_text = agent.strip()[1:-1].replace('"', '').split(",")

    closing_remarks_text = closing_remarks.strip()[1:-1].replace('"', '').split(",")
    
    closing_responses_text = closing_response.strip()[1:-1].replace('"', '').replace('-', '').split(",")
    # print(f"Agent Names:{agent_names_text}")
    db.collection('gemini_lists').document(group_id).set({
                    'group_id': group_id,
                    'services_text': services_text,
                    'problems_text': problems_text,
                    'greetings_text':greetings_text,
                    # 'agent_names_text':agent_names_text,
                    'closing_remarks_text':closing_remarks_text,
                    'closing_responses_text':closing_responses_text,
                    'start_date': start_date,
                    'end_date': end_date,
                    'timestamp': current_timestamp
                })
    # logger.info(f"Responses:{services_text}->{problems_text}->{greetings_text}->{closing_responses_text}")
    # return services_text, problems_text, greetings_text, closing_remarks_text, closing_responses_text, agent_names_text

    
def start_task(event, context):
    # Extract msg from start topic id. The msg was insterd by the UI
    pubsub_message = base64.b64decode(event['data']).decode('utf-8')
    event_id = context.event_id
    event_type = context.event_type

    try:
        # Parse the JSON message
        message = json.loads(pubsub_message)
        group_id = message['group_id']
        company_name = message['company_name']
        company_website = message['company_website']
        company_reviews = message['company_reviews']
        temperature = message['temperature']
        num_log_files = message['num_log_files']
        start_date = message['start_date']
        end_date = message['end_date']
        print(f"Log files:{num_log_files}, Company_Name:{company_name}, Temperature:{temperature}")
    except Exception as e:
        print(f"Unable to parse message {e}")

    generate_lists(group_id,company_name,company_website,company_reviews,temperature,start_date,end_date)

    try:
        for i in range(int(num_log_files)):
            task_id = str(uuid.uuid4())
            message = {
                "task_id": task_id,
                "group_id": group_id,
                "index": i,
                "company_name": company_name,
                "company_website": company_website,
                "company_reviews": company_reviews,
                "temperature": temperature,
                "num_log_files": num_log_files
            }
            print(f"Message to be published {message}")

            # Insert n tasks into task topic id
            publish_to_pubsub(message)
            print(f"Insert {i} to Firestore")
            db.collection('tasks').document(task_id).set({
                'group_id': group_id,
                'status': 'pending',
                'index':i,
                'num_log_files':num_log_files,
                'timestamp': current_timestamp
            })
    except Exception as e:
        print(f"Unable to publish message to {topic_id} - {e}")

    
    # task_ref = db.collection('tasks').document()
    # task_id = task_ref.id
    # task_ref.set({'status': 'queued', 'num_log_files': num_log_files, 'company_name': company_name, 'temperature': temperature, 'company_reviews':company_reviews})
    
    # topic_path = publisher.topic_path(project_id, topic_id)
    # for i in range(num_log_files):
    #     future = publisher.publish(topic_path, json.dumps({'task_id': task_id, 'index': i, 'company_name': company_name, 'temperature': temperature}).encode("utf-8"))
    #     future.result()
    
    # return json.dumps({"task_id": task_id})
