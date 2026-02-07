START_TOPIC="start_ccai"
TASK_TOPIC="task_ccai"
ZIP_TOPIC="zip_ccai"
FIRESTORE_DB="ccai-faker"
BUCKET_NAME="ccai_gemini_datagen"
PROJECT_ID="gen-ai-4all"
GEMINI_MODEL="gemini-2.5-flash"
EXPIRATION_MIN=260

echo "#########################Create PubSub topic##########################3"
gcloud pubsub topics create ${START_TOPIC}
gcloud pubsub topics create ${TASK_TOPIC}
gcloud pubsub topics create ${ZIP_TOPIC}

echo "###########################Create Start Task CF#######################"
cd ~/ccaifunc/backend/start_task
gcloud functions deploy start_ccai_task \
    --gen2 \
    --max-instances 1 \
    --region us-central1 \
    --source . \
    --entry-point start_task \
    --runtime python311 \
    --memory 1Gi \
    --trigger-topic ${START_TOPIC} \
    --timeout 540 \
    --set-env-vars BUCKET_NAME=${BUCKET_NAME},TASK_TOPIC_ID=${TASK_TOPIC},PROJECT_ID=${PROJECT_ID},GEMINI_MODEL=${GEMINI_MODEL},FIRESTORE_DB=${FIRESTORE_DB} \
    --service-account=genai-592@gen-ai-4all.iam.gserviceaccount.com 

echo "######################Create Process Task CF######################"

cd ~/ccaifunc/backend/process_task
gcloud functions deploy process_ccai_task\
    --gen2 \
    --max-instances 8 \
    --region us-central1 \
    --source . \
    --entry-point process_task \
    --runtime python311 \
    --memory 1Gi \
    --timeout 540 \
    --trigger-topic ${TASK_TOPIC} \
    --set-env-vars BUCKET_NAME=${BUCKET_NAME},PROJECT_ID=${PROJECT_ID},GEMINI_MODEL=${GEMINI_MODEL},FIRESTORE_DB=${FIRESTORE_DB} \
    --service-account=genai-592@gen-ai-4all.iam.gserviceaccount.com 


echo "#################Create Zip Task CF#####################"

cd ~/ccaifunc/backend/zip_task      
gcloud functions deploy zip_ccai_task\
    --gen2 \
    --max-instances 2 \
    --region us-central1 \
    --source . \
    --entry-point zip_task \
    --runtime python311 \
    --memory 1Gi \
     --timeout 1800 \
    --trigger-topic ${ZIP_TOPIC} \
    --set-env-vars BUCKET_NAME=${BUCKET_NAME},PROJECT_ID=${PROJECT_ID},FIRESTORE_DB=${FIRESTORE_DB},KEY_BLOB_NAME="sa_key/gen-ai-4all-a3547fc1376f.json",EXPIRATION_MIN=${EXPIRATION_MIN}\
    --service-account=genai-592@gen-ai-4all.iam.gserviceaccount.com 
      
echo "#################Create Check Task CF###################"

cd ~/ccaifunc/backend/check_status
gcloud functions deploy check_ccai_status \
    --gen2 \
    --max-instances 2 \
    --region us-central1 \
    --source . \
    --entry-point check_status \
    --runtime python311 \
    --memory 1Gi \
    --timeout 1800 \
    --trigger-http \
    --allow-unauthenticated \
    --set-env-vars ZIP_TOPIC_ID=${ZIP_TOPIC},BUCKET_NAME=${BUCKET_NAME},PROJECT_ID=${PROJECT_ID},FIRESTORE_DB=${FIRESTORE_DB} \
    --service-account=genai-592@gen-ai-4all.iam.gserviceaccount.com 

cd ~/ccaifunc/frontend
gcloud builds submit --tag us-central1-docker.pkg.dev/${PROJECT_ID}/genai/ccai:v1.0.0
gcloud run deploy ccai-generator --image us-central1-docker.pkg.dev/${PROJECT_ID}/genai/ccai:v1.0.0 --port 8080 --service-account genai-592@gen-ai-4all.iam.gserviceaccount.com --region us-central1 --allow-unauthenticated
      


# Test Ids

# {
#   "group_id": "5c69bd9c-c803-44a7-9a35-8b31a7d20ad0"
# }

# {
#   "group_id": "e26ee85d-7edd-4c95-8c85-d43ac3cda73b"
# }