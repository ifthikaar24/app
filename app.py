from flask import Flask, request, jsonify
from flask_cors import CORS
from pymongo import MongoClient
import hashlib
import hmac
import datetime
import os

app = Flask(__name__)
CORS(app)  # Enable CORS for all origins

# MongoDB connection
client = MongoClient("mongodb+srv://ifthikaar:<taaeif10>@github-webhooks.lugoq.mongodb.net/?retryWrites=true&w=majority&appName=github-webhooks")
db = client['github_webhooks']
collection = db['actions']

# Secret for webhook validation
WEBHOOK_SECRET = "taaeif10"

# Webhook receiver endpoint
@app.route('/webhook', methods=['POST'])
def webhook():
    app.logger.info(f"Received a POST request to /webhook with data: {request.data}")
    
    # Validate the GitHub webhook
    signature = request.headers.get('X-Hub-Signature-256')
    if not validate_signature(request.data, signature):
        app.logger.warning(f"Invalid signature received: {signature}")
        return jsonify({"error": "Invalid signature"}), 401

    payload = request.json
    app.logger.info(f"Parsed payload: {payload}")

    action_type = payload.get('action')
    author = payload.get('sender', {}).get('login')
    repo = payload.get('repository', {}).get('name')
    timestamp = datetime.datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')

    # Handle GitHub actions
    entry = None
    if action_type == "push":
        to_branch = payload.get('ref', '').replace('refs/heads/', '')
        entry = {
            "request_id": payload.get('after'),
            "author": author,
            "action": "PUSH",
            "from_branch": None,
            "to_branch": to_branch,
            "timestamp": timestamp
        }
    elif action_type == "pull_request":
        from_branch = payload.get('pull_request', {}).get('head', {}).get('ref')
        to_branch = payload.get('pull_request', {}).get('base', {}).get('ref')
        entry = {
            "request_id": str(payload.get('pull_request', {}).get('id')),
            "author": author,
            "action": "PULL_REQUEST",
            "from_branch": from_branch,
            "to_branch": to_branch,
            "timestamp": timestamp
        }
    elif action_type == "closed" and payload.get('pull_request', {}).get('merged', False):
        from_branch = payload.get('pull_request', {}).get('head', {}).get('ref')
        to_branch = payload.get('pull_request', {}).get('base', {}).get('ref')
        entry = {
            "request_id": str(payload.get('pull_request', {}).get('id')),
            "author": author,
            "action": "MERGE",
            "from_branch": from_branch,
            "to_branch": to_branch,
            "timestamp": timestamp
        }
    else:
        app.logger.info("No actionable event type received.")
        return jsonify({"message": "No action handled"}), 200

    # Store entry in MongoDB
    if entry:
        collection.insert_one(entry)
        app.logger.info(f"Stored entry: {entry}")

    return jsonify({"message": "Event processed"}), 200

def validate_signature(payload, signature):
    """Validate the HMAC signature."""
    if not signature:
        return False
    computed_hash = hmac.new(WEBHOOK_SECRET.encode(), payload, hashlib.sha256).hexdigest()
    return hmac.compare_digest(f"sha256={computed_hash}", signature)

@app.route('/actions', methods=['GET'])
def get_actions():
    app.logger.info("Received a GET request to /actions")
    actions = list(collection.find().sort("timestamp", -1))
    for action in actions:
        action["_id"] = str(action["_id"])  # Convert ObjectId to string
    app.logger.info(f"Fetched actions: {actions}")
    return jsonify(actions)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
