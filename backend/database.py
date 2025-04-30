from pymongo import MongoClient

client = MongoClient("mongodb://localhost:27017")
db = client.nhs_app
users_collection = db.users
feedback_collection = db.feedback
