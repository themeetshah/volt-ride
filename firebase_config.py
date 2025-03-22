import firebase_admin
from firebase_admin import credentials, db

# Load Firebase credentials
cred = credentials.Certificate("firebase_config.json")
firebase_admin.initialize_app(cred, {
    'databaseURL': 'https://console.firebase.google.com/project/volt-ride-1/database/volt-ride-1-default-rtdb/data/~2F'
})

# Get database reference
database = db.reference()
