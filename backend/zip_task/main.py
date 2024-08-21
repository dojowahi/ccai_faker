import base64
import json
import datetime
from google.cloud import firestore
from google.cloud import storage
from google.api_core import retry
from google.api_core.exceptions import ServiceUnavailable
import os 
import logging
import json
from google.api_core.exceptions import TooManyRequests
import zipfile
from google.oauth2 import service_account
import io


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger()


bucket_name = os.getenv('BUCKET_NAME')
project_id = os.getenv('PROJECT_ID')
db_firestore = os.getenv('FIRESTORE_DB') #ccai_faker
key_blob_name = os.getenv('KEY_BLOB_NAME')
expiration_minutes = int(os.getenv('EXPIRATION_MIN'))
current_timestamp = datetime.datetime.now().strftime("%Y%m%d%H%M%S")

db = firestore.Client(database=db_firestore)

def zip_task(event, context):

    pubsub_message = base64.b64decode(event['data']).decode('utf-8')
    print(f"PubSub type {type(pubsub_message)} and Message - {pubsub_message}")
    event_id = context.event_id
    event_type = context.event_type

    # print(f"A new event is received: id={event_id}, type={event_type}")
    # Extract data
    try:
        # Parse the JSON message
        message = json.loads(pubsub_message)
        zip_id = message['zip_id']
        group_id = message['group_id']
        zip_name = message['zip_name']
        folder = message['folder']
        current_timestamp = message['current_timestamp']

        print(f"Processing zip_name {zip_name} for groupid {group_id}")
    except Exception as e:
        print(f"Unable to parse message {e}")

    
    try:
        signed_url = zip_files_and_create_signed_url(folder,zip_name,expiration_minutes)
        if signed_url.startswith("Error"):
            db.collection('zip_repo').document(zip_id).set({
            'group_id': group_id,
            'status': 'failed',
            'reason': signed_url,
            'timestamp': current_timestamp
        })
            return None
        else:
            print(f"Creation of {zip_name} success. Inserting status into firestore..")
            db.collection('zip_repo').document(zip_id).set({
                'group_id': group_id,
                'status': 'completed',
                'zip_filename': zip_name,
                'signed_url':signed_url,
                'expiration_minutes': expiration_minutes,
                'timestamp': current_timestamp
            })
            return signed_url
    except Exception as e:
        print(f"Upload failed after retries: {e}")
        

def zip_files_and_create_signed_url(folder_name, zip_file_name, expiration_minutes=60):
    # Initialize the GCS client
    try:
        print(f"Build zip file {zip_file_name}")
        # Initialize the GCS client to download the service account key
        storage_client = storage.Client()
        bucket = storage_client.bucket(bucket_name)
        key_blob = bucket.blob(key_blob_name)
        
        # Download the service account key JSON content
        key_json_content = key_blob.download_as_bytes()
        credentials = service_account.Credentials.from_service_account_info(
            json.loads(key_json_content)
        )
        
        # Initialize a new GCS client with the service account credentials
        client = storage.Client(credentials=credentials)
        bucket = client.bucket(bucket_name)

        # List all files in the folder
        blobs = storage_client.list_blobs(bucket_name, prefix=folder_name)
        
        # Create an in-memory zip file
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w') as zip_file:
            for blob in blobs:
                # Download the file
                file_content = blob.download_as_bytes()
                
                # Write the file to the zip file
                zip_file.writestr(blob.name[len(folder_name):], file_content)
        
        # Upload the zip file to GCS
        zip_buffer.seek(0)
        zip_blob = bucket.blob(zip_file_name)
        zip_blob.upload_from_file(zip_buffer, content_type='application/zip')
        
        # Generate a signed URL for the zip file
        expiration = datetime.datetime.utcnow() + datetime.timedelta(minutes=expiration_minutes)
        try:
            url = zip_blob.generate_signed_url(
                expiration=expiration,
                method='GET',
                version='v4'
            )
        except Exception as e:
            return f"Error unable to generate signed url:{str(e)}"
        return url
    except Exception as e:
        return f"Error:{str(e)}"