import os
from dotenv import load_dotenv
import firebase_admin
from firebase_admin import credentials, firestore

# Load environment variables FIRST
load_dotenv()

# Get the path to service account key
cred_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "serviceAccount.json")

# Initialize Firebase Admin SDK
cred = credentials.Certificate(cred_path)
firebase_admin.initialize_app(cred)

# Initialize Firestore client
db = firestore.client()

print("✅ Firebase Admin SDK initialized successfully")
