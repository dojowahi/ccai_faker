import base64
import json
import datetime
from google.cloud import firestore
from google.cloud import storage
from google.api_core import retry
from google.api_core.exceptions import ServiceUnavailable
import random
import vertexai
import ast
import os 
import time
from vertexai.generative_models import GenerativeModel, GenerationConfig, HarmCategory, HarmBlockThreshold
import logging
import ast
import re
import json
import concurrent.futures
from google.api_core.exceptions import TooManyRequests


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger()


bucket_name = os.getenv('BUCKET_NAME')
project_id = os.getenv('PROJECT_ID')
model_name = os.getenv('GEMINI_MODEL')
db_firestore = os.getenv('FIRESTORE_DB') #ccai_faker
current_timestamp = datetime.datetime.now().strftime("%Y%m%d%H%M%S")

model = GenerativeModel(model_name=model_name)
db = firestore.Client(database=db_firestore)

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
    

def get_lists(group_id):
    doc_ref = db.collection('gemini_lists').document(group_id)
    doc = doc_ref.get()
    if doc.exists:
    # Retrieve the data as a dictionary
        data = doc.to_dict()
        services = data['services_text']
        problems = data['problems_text']
        greetings = data['greetings_text']
        agent_names = data['agent_names_text']
        closing_remarks = data['closing_remarks_text']
        closing = data['closing_responses_text']
        start_date = data['start_date']
        end_date = data['end_date']
        return services, problems, greetings, closing_remarks, closing, agent_names,start_date, end_date
    else:
        print(f"Error:Document does not exist")

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

def process_task(event, context):
    start_time = time.time()
    pubsub_message = base64.b64decode(event['data']).decode('utf-8')
    # print(f"PubSub type {type(pubsub_message)} and Message - {pubsub_message}")
    event_id = context.event_id
    event_type = context.event_type

    # print(f"A new event is received: id={event_id}, type={event_type}")
    # Extract data
    try:
        # Parse the JSON message
        message = json.loads(pubsub_message)
        task_id = message['task_id']
        group_id = message['group_id']
        index = message['index']
        company_name = message['company_name']
        company_website = message['company_website']
        company_reviews = message['company_reviews']
        temperature = message['temperature']
        num_log_files = message['num_log_files']

        print(f"Processing log {index} out of {num_log_files} for groupid {group_id}")
    except Exception as e:
        print(f"Unable to parse message {e}")
    
    try:
        # services, problems, greetings, closing_remarks, closing, agent_names = generate_lists(company_name,company_website,company_reviews,temperature)
        services, problems, greetings, closing_remarks, closing, agent_names,start_date,end_date = get_lists(group_id)
        log_date = random_date_between(start_date,end_date)
        print(f"Generate log for date {log_date}")
        json_object = generate_log(company_name,services, problems, greetings, closing_remarks, closing, agent_names,temperature,log_date)

        if json_object is not None:
            storage_client = storage.Client()
            bucket = storage_client.bucket(bucket_name)
            filename = f"ccai/{company_name}/{group_id}/{task_id}_{index}_{current_timestamp}.json"
            blob = bucket.blob(filename)

            @retry.Retry(predicate=retry.if_exception_type(ServiceUnavailable), deadline=60)
            def upload_blob():
                blob.upload_from_string(json_object)

            try:
                upload_blob()
                print(f"Uploaded {filename} to GCS bucket")
                db.collection('tasks').document(task_id).set({
                    'group_id': group_id,
                    'status': 'completed',
                    'filename': filename,
                    'index':index,
                    'num_log_files':num_log_files,
                    'timestamp': current_timestamp
                })
            except Exception as e:
                print(f"Upload failed after retries: {e}")
                db.collection('tasks').document(task_id).set({
                    'group_id': group_id,
                    'status': 'failed',
                    'reason': str(e),
                    'index':index,
                    'company_name':company_name,
                    'num_log_files':num_log_files,
                    'timestamp': current_timestamp
                })
        else:
            print(f"Skipping call log {index} due to an error.")
            db.collection('tasks').document(task_id).set({
                'group_id': group_id,
                'status': 'skipped',
                'index':index,
                'company_name':company_name,
                'num_log_files':num_log_files,
                'timestamp': current_timestamp
            })
    except Exception as e:
        print(f"Error processing log {index}: {e}")
        db.collection('tasks').document(task_id).set({
            'group_id': group_id,
            'status': 'error',
            'reason': str(e),
            'index':index,
            'company_name':company_name,
            'num_log_files':num_log_files,
            'timestamp': current_timestamp
        })
    end_time = time.time()
    duration = end_time - start_time
    print(f"For {index} of {group_id} -Execution time: {duration:.2f} seconds")

safety_settings = {
    HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
    HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
    HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
    HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
}

def random_date_between(start_date_str, end_date_str, format="%Y-%m-%d"):
  """Generates a random date between two given date strings (inclusive).

  Args:
      start_date_str: The start date string.
      end_date_str: The end date string.
      format: The format of the date strings (default is YYYY-MM-DD).

  Returns:
      A random date string between the start and end dates (inclusive).
  """

  start_date = datetime.datetime.strptime(start_date_str, format).date()
  end_date = datetime.datetime.strptime(end_date_str, format).date()

  delta = end_date - start_date
  random_days = random.randrange(delta.days + 1)

  random_date = start_date + datetime.timedelta(days=random_days)
  return random_date.strftime(format)

def generate_log(company_name,services, problems, greetings, closing_remarks, closing_responses, agent_names, temperature,log_date,max_retries=3):
    generation_config = GenerationConfig(
    temperature=temperature,
    top_p=1.0,
    top_k=32,
    candidate_count=1,
    max_output_tokens=8192,
)
    service = random.choice(services)
    problem_description = random.choice(problems)

    # Generate timestamps
    start_timestamp = int(datetime.datetime.now().timestamp() * 1000000)
      # 1 to 20 seconds in microseconds
    format = "%Y-%m-%d"  # Format for YYYY-MM-DD

    date_obj = datetime.datetime.strptime(log_date, format)
    start_timestamp = int(date_obj.timestamp() * 1000000)
    response_delay = random.randint(1000000, 10000000)

    # Pick a random agent name
    agent_name = random.choice(agent_names)
    customer_behavior = random.choice(["polite and patient", "frustrated and impatient", "angry and demanding", "confused and unsure"])
    # Generate a natural problem statement
    problem_statement_prompt = f"""
    Rewrite this issue into a natural statement a customer would say to describe their problem with their {service}: "{problem_description}" 
    """
    # logger.info(f"Problem Statement:{problem_statement_prompt}")
    for retry_count in range(max_retries):  # Retry mechanism for both problem statement and transcript
        try:
            # Generate a natural problem statement with safety check
            while True:
                problem_statement_response = model.generate_content(problem_statement_prompt,safety_settings=safety_settings)
                
                if not problem_statement_response.candidates[0].finish_reason == "STOP_REASON_SAFETY":  # Check for safety filter triggers
                    customer_statement = problem_statement_response.text.strip()
                    break  # Break out of the loop if the problem statement is safe
                else:
                    logger.info("Problem statement triggered safety filter. Retrying...")
            # logger.info(f"Model response:{customer_statement}")
            # logger.info(f"randomness:{random.choice(greetings)},{random.choice(closing_remarks)}")
            # Enhanced Prompt Template (with customer_statement variable):
            prompt_template = f"""
            Create a customer support transcript where {company_name} agent helps a customer with their {service}. 
            Adhere strictly to this format:
            Agent: [Agent's greeting]
            Customer: {customer_statement}
            Agent: [Agent's response acknowledging the problem and starting troubleshooting]
            Customer: [Customer's response to the troubleshooting steps]
            Agent: [Further troubleshooting or resolution steps]
            ... (continue the back-and-forth as needed)
            Agent: [Resolution of the issue or escalation]
            Agent: [Agent's closing remark]
            Customer: [Customer's natural response acknowledging resolution and ending the call]

            Additional instructions:

            *   Use "{random.choice(greetings)}" for the agent's greeting.
            *   Use "{random.choice(closing_remarks)}" for the agent's closing remark.
            *   The conversation MUST include troubleshooting steps and a resolution.
            *   Focus on a single core issue the customer is experiencing
            *   The customer is "{customer_behavior}"
           """

            # logger.info(f"Prompt template:{prompt_template}")

            response = model.generate_content(prompt_template, generation_config=generation_config,safety_settings=safety_settings)
            if not response.candidates: 
                raise Exception("Model returned no candidates. Retrying...")
            
            for candidate in response.candidates:
                if candidate.finish_reason == "STOP_REASON_SAFETY":
                    raise Exception("Safety filter triggered. Retrying...")
                elif not hasattr(candidate, 'text'):  # Check if 'text' attribute exists
                    raise Exception("Unexpected response format. Retrying...")

            transcript = response.text
            # logger.info(f"Transcript:{transcript}")
            # Check for safety filter blocks in any candidate (not just the first one)
            for candidate in response.candidates:
                if candidate.finish_reason == "STOP_REASON_SAFETY":
                    raise Exception("Safety filter triggered. Retrying...")

            # Enhanced Transcript Parsing with Logic to Prevent Unnatural Endings
            entries = []
            current_speaker = None
            customer_said_no = False 
            short_customer_response = False
            agent_asked_anything_else = False
            last_agent_line = ""  

            for line in transcript.splitlines():
                line = line.strip()
                if line.lower().startswith("customer") or line.lower().startswith("agent"):
                    if line.lower().startswith("customer"):
                        entries.append({"role": "CUSTOMER", "text": line[8:].strip(), "user_id": 1})
                        if line.lower().strip() in ["no", "no thanks", "that's all", "that's it", "i'm good", "nothing else","okay"]:
                            customer_said_no = True
                        if len(line.lower().strip()) <= 3:
                            short_customer_response = True
                    elif line.lower().startswith("agent"):
                        last_agent_line = line[5:].strip()
                        if "anything else" in last_agent_line.lower():
                            agent_asked_anything_else = True
                        
                        # Condition to skip the "anything else" response after customer says no
                        if not (customer_said_no and "anything else" in last_agent_line.lower()):
                            entries.append({"role": "AGENT", "text": line[5:].strip(), "user_id": 2})  

            # Retry Conditions (consolidated for readability)
            if any((
                agent_asked_anything_else and last_agent_line == entries[-1]['text'],
                customer_said_no and "anything else" in last_agent_line.lower(),
                short_customer_response,
                not entries  # Check for blank output
            )):
                retry_reason = (
                    "Customer didn't answer 'anything else?'" if agent_asked_anything_else and last_agent_line == entries[-1]['text'] else
                    "Agent asked again after customer said no" if customer_said_no and "anything else" in last_agent_line.lower() else
                    "Customer response too short" if short_customer_response else
                    "Blank output"
                )
                logger.info(f"{retry_reason}. Retrying...")
                return generate_log(services, problems, greetings, closing_remarks, closing_responses, agent_names)

            # Add timestamps
            for i, entry in enumerate(entries):
                entry["start_timestamp_usec"] = start_timestamp + response_delay * i

            # Replace any remaining placeholders
            for entry in entries:
                if "[agent name]" in entry["text"].lower():
                    entry["text"] = entry["text"].replace("[agent name]", random.choice(agent_names))

            call_log = {"entries": entries}
            json_object = json.dumps(call_log, indent=4)
            return json_object  # Return the generated JSON if successful

        except Exception as e:
            logger.error(f"Error generating log (attempt {retry_count + 1}/{max_retries}): {e}")
            if retry_count < max_retries - 1:  
                time.sleep(2 ** retry_count)  
            else:
                logger.error("Max retries reached. Skipping this call log.")
                return None

