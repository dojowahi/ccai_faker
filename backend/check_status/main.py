import functions_framework
from google.cloud import firestore
import logging
import os
import io
import datetime
from google.cloud import storage
from google.auth import default
import zipfile
import json
import re
import json
from google.cloud import pubsub_v1
from google.cloud import firestore
import os
import datetime
import base64
import uuid
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

current_timestamp = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger()

bucket_name = os.getenv('BUCKET_NAME')
project_id = os.getenv('PROJECT_ID')
db_firestore = os.getenv('FIRESTORE_DB') #ccai-faker
topic_id = os.getenv("ZIP_TOPIC_ID") #Topic where zipping details will be inserted
sender_email = os.environ.get('SENDER_EMAIL')
# The password was setup for a Google Account(wahi80) via App Password: https://support.google.com/mail/answer/185833?hl=en
sender_pwd = os.environ.get('SENDER_PWD')


db = firestore.Client(database=db_firestore)

def publish_to_pubsub(message):
    publisher = pubsub_v1.PublisherClient()
    topic_path = publisher.topic_path(project_id, topic_id)
    message_data = json.dumps(message).encode("utf-8")
    future = publisher.publish(topic_path, message_data)
    future.result()

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


@functions_framework.http
def check_status(request):
    """
    HTTP Cloud Function that counts task statuses for a given group ID.

    Args:
        request: The HTTP request object containing the group_id parameter.

    Returns:
        A dictionary containing the count of each task status for the given group ID.
    """

    # Extract group_id from the request
    request_json = request.get_json(silent=True)
    request_args = request.args

    if request_json and 'group_id' in request_json:
        group_id = request_json['group_id']
    elif request_args and 'group_id' in request_args:
        group_id = request_args['group_id']
    else:
        return 'group_id not provided', 400

    status_counts = {"failed": 0, "completed": 0, "error": 0, "skipped": 0, "pending": 0}
    num_log_files = None
    total_documents = 0
    pending_docs = 0
    filename = ""

    # Initialize Firestore client
    tasks_ref = db.collection('tasks').where('group_id', '==', group_id)

    # Perform group by on status and count documents
    query = tasks_ref.where('group_id', '==', group_id)
    docs = query.stream()

    # Count statuses and get num_log_files
    for doc in docs:
        status = doc.get('status')
        if status == 'pending':
            pending_docs +=1
        else:
            total_documents += 1
        
        if status in status_counts:
            status_counts[status] += 1
        else:
            status_counts[status] = 1

    # Get num_log_files from any document matching the group_id
    doc_snapshot = tasks_ref.limit(1).get()
    if doc_snapshot:
        num_log_files = doc_snapshot[0].to_dict().get('num_log_files', 0)  # Handle case where field might be missing
    else:
        num_log_files = 0  # Or handle the case where no documents match

    # Compare counts and return message
    if num_log_files is not None and num_log_files <= total_documents:
        # Scrape a filename of any completed record
        query = tasks_ref.where('group_id', '==', group_id).where('status', '==', 'completed').limit(1)
        docs = query.stream()
            # Retrieve and return the first document found
        completed_document_found = False
        for doc in docs:
            completed_document_found = True
            signed_url = check_zip_file_exist(group_id)
            print(f"Signed URL from {signed_url}")
            if signed_url:
                send_email(sender_email, 
                sender_pwd, 
                "ankurwahi@google.com", 
                'Group Id', 
                f'Use this {group_id} to check status')

                return {
                "message": "Job completed. ",
                "status_counts": status_counts,
                "signed_url": signed_url
            }
            
            else:
                filename = doc.get('filename')
                zip_name,folder = build_zip_name_folder(filename)
                zip_id = str(uuid.uuid4())
                zip_message = {
                    "zip_id": zip_id,
                    "group_id": group_id,
                    "zip_name":zip_name,
                    "folder":folder,
                    "current_timestamp": current_timestamp
                }
                publish_to_pubsub(zip_message)
                # url = zip_files_and_create_signed_url(folder,zip_name)
                return {
                    "message": "Job completed, zipping process started. Check back in 10 min. ",
                    "status_counts": status_counts,
                    "data_path": folder
                }

        if not completed_document_found:
            if total_documents == 0:
                return {
                    "message": "Your group_id is yet to be processed.Check after 15 min. ",
                    "status_counts": status_counts,"num_log_files": num_log_files, "total_documents": total_documents
                }
            else:
                return{
                    "message": "Contact Ankur Wahi, with your group_id",
                    "status_counts": status_counts,"num_log_files": num_log_files, "total_documents": total_documents
                }
    
    else:
        return {"message": "Job NOT completed.", "status_counts": status_counts, "num_log_files": num_log_files, "total_documents": total_documents}

# Check existence of zip file by querying firestore
def check_zip_file_exist(group_id):
    from datetime import datetime, timedelta
    cutoff_time = datetime.utcnow() - timedelta(minutes=60)
    print(f"Querying zip firestore db with {group_id} to see if valid signed_url exists")
    # Query the Firestore collection
    query = db.collection('zip_repo')\
              .where('group_id', '==', group_id)\
              .where('status', '==', 'completed')\
              .limit(1)

    results = query.stream()

    # Extract the signed URL from the query results
    for doc in results:
        url = doc.to_dict().get('signed_url')
        print(f"Return from Firestore zip_repo:{url}")
        return url
    
    return None


def build_zip_name_folder(filename):
    print(f"Extract zip_name from {filename}")
    match = re.match(r"ccai/([^/]+)/([^/]+)/", filename)
    if match:
        category = match.group(1).replace(' ', '_')
        uuid = match.group(2)
        zip_prefix = f"{category}_{uuid}"
        zip_name = f"{zip_prefix}.zip"
        parts = filename.split("/")
        folder = "/".join(parts[:3])
        print(f"Zip filename:{zip_name}, Folder: {folder}")
        return zip_name, folder

