# CCAI Faker

![Architecture Diagram](/static/ccai_faker_architeture.png)

Generates synthetic conversation of customer service calls using Gemini, which can be fed into Google Cloud's CCAI product.

## Features

* List the key features or functionalities of your project

## Getting Started

### Prerequisites

* GCP account, with billing enabled and a Service Account with Vertex AI Admin,Cloud Run Admin. Artifact Registry Administrator, Cloud Datastore User, Pub/Sub Admin and Storage Admin permissions

* A firestore database with three collections: tasks, gemini_lists, zip_repo

* An artifact repository called genai

### Installation

1. Change variables in /scripts/setup_cloud.sh and execute it
2. Once script is executed you should have 3 PubSub topics created along 4 cloud functions deployed for the backend and one cloud run deployed for the frontend


## Architecture

* The frontend uses NiceGUI and runs on Cloud Run
* The backend uses GCS, PubSub,Firestore, and runs on Cloud Functions Gen2
