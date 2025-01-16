from flask import Flask, request, jsonify
from flask_cors import CORS  # Import CORS
from pymongo import MongoClient
import hashlib
import hmac
import datetime
import os

app = Flask(__name__)

# Enable CORS for all routes
CORS(app)

# MongoDB connection
client = MongoClient("mongodb+srv://your-connection-string")
db = client['github_webhooks']
collection = db['actions']

# Secret for webhook validation
WEBHOOK_SECRET = "your-webhook-secret"

# Webhook receiver endpoint
@app.route('/webhook', methods=['POST'])
def webhook():
    # Log the incoming request for debugging
    app.logger.info(f"Received a POST request to /webhook with data: {request.data}")
    
    # Validate the GitHub webhook
    signature = request.headers.get('X-Hub-Signature-256')
    if not validate_signature(request.data, signature):
        app.logger.warning(f"Invalid signature received: {signature}")
        return "Invalid signature", 401

    # Parse the webhook payload
    payload = request.json
    app.logger.info(f"Parsed payload: {payload}")

    action_type = payload.get('action')
    author = payload.get('sender', {}).get('login')
    repo = payload.get('repository', {}).get('name')
    timestamp = datetime.datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')

    # Handle different actions
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
        return "No action handled", 200

    # Store the entry in MongoDB
    collection.insert_one(entry)
    return "Event processed", 200

def validate_signature(payload, signature):
    if not signature:
        return False
    computed_hash = hmac.new(WEBHOOK_SECRET.encode(), payload, hashlib.sha256).hexdigest()
    return hmac.compare_digest(f"sha256={computed_hash}", signature)

@app.route('/actions', methods=['GET'])
def get_actions():
    # Log the incoming GET request
    app.logger.info("Received a GET request to /actions")

    # Fetch latest actions from MongoDB
    actions = list(collection.find().sort("timestamp", -1))
    for action in actions:
        action["_id"] = str(action["_id"])  # Convert ObjectId to string
    
    # Log actions fetched from DB
    app.logger.info(f"Fetched actions: {actions}")
    
    return jsonify(actions)

if __name__ == "__main__":
    # Fetch the PORT from environment variables, default to 5000 for local development
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
