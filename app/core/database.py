import os
from google.cloud import firestore
from dotenv import load_dotenv

load_dotenv()

# Initialize Firestore client
# Credentials are loaded from GOOGLE_APPLICATION_CREDENTIALS environment variable
db = firestore.Client()
