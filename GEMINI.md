# Gemini Code Understanding

## Project Overview

This project, "CCAI Faker," is a web application designed to generate synthetic customer service call conversations using Google's Gemini large language model. These generated conversations can then be used with Google Cloud's Contact Center AI (CCAI) product.

The application is built with Python and has a microservices architecture. The frontend is a [NiceGUI](https://nicegui.io/) web application that runs on Google Cloud Run. The backend is composed of four serverless Google Cloud Functions that communicate with each other using Pub/Sub messages. The application uses Firestore as its database and Google Cloud Storage for file storage.

The core of the application lies in the `process_task` Cloud Function, which uses the Vertex AI SDK to interact with the Gemini model. It generates conversations based on a set of prompts stored in the `prompts/` directory.

## Architecture

The project follows a decoupled, event-driven architecture.

*   **Frontend:** A NiceGUI web application running on Cloud Run provides the user interface for initiating the data generation process.
*   **Backend:**
    *   **`start_task` (Cloud Function):** Triggered by a Pub/Sub message from the frontend, this function starts the conversation generation process.
    *   **`process_task` (Cloud Function):** This is the core function that generates the synthetic conversations using the Gemini model. It is triggered by the `start_task` function via a Pub/Sub message for each conversation to be generated.
    *   **`zip_task` (Cloud Function):** Once all conversations are generated, this function is triggered by a Pub/Sub message to zip the generated conversation files and store them in Google Cloud Storage.
    *   **`check_status` (Cloud Function):** A an HTTP-triggered function that allows the frontend to check the status of a generation task.
*   **Google Cloud Services:**
    *   **Cloud Run:** Hosts the frontend application.
    *   **Cloud Functions:** Hosts the backend microservices.
    *   **Pub/Sub:** Used for asynchronous communication between the backend services.
    *   **Firestore:** Used as the database to store task information and other metadata.
    *   **Google Cloud Storage:** Used to store the generated conversation files and prompts.
    *   **Vertex AI:** Provides access to the Gemini large language model.

An architecture diagram is available at `static/ccai_faker_architeture.png`.

## Building and Running

The application is designed to be deployed on the Google Cloud Platform. The `scripts/setup_cloud.sh` script automates the deployment process.

### Prerequisites

*   A Google Cloud Platform (GCP) project with billing enabled.
*   A service account with the following roles:
    *   Vertex AI Admin
    *   Cloud Run Admin
    *   Artifact Registry Administrator
    *   Cloud Datastore User
    *   Pub/Sub Admin
    *   Storage Admin
*   A Firestore database with the collections: `tasks`, `gemini_lists`, and `zip_repo`.
*   An Artifact Registry repository named `genai`.

### Deployment Steps

1.  **Configure the Deployment Script:**
    *   Open `scripts/setup_cloud.sh` and update the following variables with your GCP project details:
        *   `PROJECT_ID`
        *   `BUCKET_NAME`
        *   `FIRESTORE_DB`
        *   `GEMINI_MODEL`
    *   You may also need to update the `--service-account` flag in the `gcloud` commands to point to your service account.

2.  **Run the Deployment Script:**
    *   Execute the script from your terminal:
        ```bash
        sh scripts/setup_cloud.sh
        ```

The script will perform the following actions:

*   Create three Pub/Sub topics: `start_ccai`, `task_ccai`, and `zip_ccai`.
*   Deploy the four backend Cloud Functions (`start_task`, `process_task`, `zip_task`, and `check_status`).
*   Build the frontend Docker image and deploy it to Cloud Run.

### Environment Variables

The application is configured using environment variables, which are set in the `scripts/setup_cloud.sh` script.

*   **`BUCKET_NAME`**: The name of the GCS bucket for storing data.
*   **`PROJECT_ID`**: Your GCP project ID.
*   **`GEMINI_MODEL`**: The name of the Gemini model to use (e.g., `gemini-1.5-flash-001`).
*   **`FIRESTORE_DB`**: The name of the Firestore database.
*   **`TASK_TOPIC_ID`**: The ID of the Pub/Sub topic for processing tasks.
*   **`ZIP_TOPIC_ID`**: The ID of the Pub/Sub topic for zipping files.
*   **`EXPIRATION_MIN`**: The expiration time in minutes for signed URLs.

## Development Conventions

*   The project is organized into `frontend` and `backend` directories.
*   Each backend Cloud Function has its own directory containing its source code and `requirements.txt` file.
*   The frontend is a NiceGUI application with its own `requirements.txt` file.
*   Prompts for the Gemini model are stored in the `prompts/` directory as `.txt` files.
