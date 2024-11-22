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
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger()

# Retrieve environment variables for configuration
bucket_name = os.getenv('BUCKET_NAME')
project_id = os.getenv('PROJECT_ID')
db_firestore = os.getenv('FIRESTORE_DB') 
# Sample key_blob_name : sa_key/gen-ai-4all-8cf2714638bc.json stored in Github secrets. The JSON file is uploaded to the bucket ccai_gemini_datagen/sa_key
key_blob_name = os.getenv('KEY_BLOB_NAME')
expiration_minutes = int(os.getenv('EXPIRATION_MIN'))
current_timestamp = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
sender_email = os.environ.get('SENDER_EMAIL')
# The password was setup for a Google Account(wahi80) via App Password: https://support.google.com/mail/answer/185833?hl=en
sender_pwd = os.environ.get('SENDER_PWD')

# Initialize Firestore client
db = firestore.Client(database=db_firestore)

def send_email(sender_email, sender_password, receiver_email, subject,body):
  """
  Sends an email with the given parameters.

  Args:
    sender_email: The sender's email address.
    sender_password: The sender's email password.
    receiver_email: The recipient's email address.
    subject: The subject of the email.
    body: The body of the email.
  """

  message = MIMEMultipart()
  message['From'] = sender_email
  message['To'] = receiver_email
  message['Subject'] = subject
  message.attach(MIMEText(body, 'plain'))
  try:
    server = smtplib.SMTP('smtp.gmail.com', 587)
    server.starttls()
    server.login(sender_email, sender_password)
    server.sendmail(sender_email, receiver_email,message.as_string())
    server.quit()
    print("Email sent successfully!")
  except Exception as e:
    print(f"Error sending email: {e}")

def get_notification_email(group_id):
    doc_ref = db.collection('gemini_lists').document(group_id)
    doc = doc_ref.get()
    if doc.exists:
    # Retrieve the data as a dictionary
        data = doc.to_dict()
        notification_email = data['notification_email']
        return notification_email
    else:
        return "ankurwahi@google.com"


def zip_task(event, context):
    # Decode and parse the Pub/Sub message
    pubsub_message = base64.b64decode(event['data']).decode('utf-8')
    event_id = context.event_id
    event_type = context.event_type

    try:
        message = json.loads(pubsub_message)
        # Extract relevant data from the message
        zip_id = message['zip_id']
        group_id = message['group_id']
        zip_name = message['zip_name']
        folder = message['folder']
        current_timestamp = message['current_timestamp']
        print(f"Start zipping for group {group_id}")
    except Exception as e:
        print(f"Unable to parse message {e}")

    try:
        # Zip files and generate a signed URL
        signed_url = zip_files_and_create_signed_url(folder,zip_name,expiration_minutes)
        if signed_url.startswith("Error"):
            # Handle errors during zip creation or URL generation
            db.collection('zip_repo').document(zip_id).set({
            'group_id': group_id,
            'status': 'failed',
            'reason': signed_url,
            'timestamp': current_timestamp
        })
            return None
        else:
            # Store success status and signed URL in Firestore
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
        # Handle any other unexpected errors
        print(f"Upload failed after retries: {e}")
        
# Create zip file and signed_url for download
def zip_files_and_create_signed_url(folder_name, zip_file_name,group_id, expiration_minutes=360):
    try:
        # Initialize GCS clients and download service account key
        notification_email = get_notification_email(group_id)
        storage_client = storage.Client()
        bucket = storage_client.bucket(bucket_name)
        key_blob = bucket.blob(key_blob_name) 
        key_json_content = key_blob.download_as_bytes()
        credentials = service_account.Credentials.from_service_account_info(
            json.loads(key_json_content)
        )
        client = storage.Client(credentials=credentials)
        bucket = client.bucket(bucket_name)

        # List files in the specified folder
        blobs = storage_client.list_blobs(bucket_name, prefix=folder_name)
        
        # Create an in-memory zip file
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w') as zip_file:
            for blob in blobs:
                # Download each file and add it to the zip
                file_content = blob.download_as_bytes()
                zip_file.writestr(blob.name[len(folder_name):], file_content)
        
        # Upload the zip file to GCS
        zip_buffer.seek(0)
        zip_blob = bucket.blob(zip_file_name)
        zip_blob.upload_from_file(zip_buffer, content_type='application/zip')
        
        # Generate a signed URL for the zip file with expiration
        expiration = datetime.datetime.utcnow() + datetime.timedelta(minutes=expiration_minutes)
        try:
            url = zip_blob.generate_signed_url(
                expiration=expiration,
                method='GET',
                version='v4'
            )
            send_email(sender_email, 
                sender_pwd, 
                notification_email, 
                f'Download files for Group Id {group_id}', 
                f'This UR: {url} is valid for next hour')
        except Exception as e:
            return f"Error unable to generate signed url:{str(e)}"
        return url
    except Exception as e:
        return f"Error:{str(e)}"