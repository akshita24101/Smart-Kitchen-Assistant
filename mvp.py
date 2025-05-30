from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, login_user, logout_user, login_required, UserMixin
import requests
import json
import os
from datetime import datetime
from flask_login import current_user, login_required



# ------------------ CONFIG ------------------
app = Flask(__name__)
app.secret_key = 'your_secret_key'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///users.db'
db = SQLAlchemy(app)
login_manager = LoginManager(app)

YOUTUBE_API_KEY = "YOUR_YOUTUBE_API_KEY"
HF_TOKEN = "YOUR_HUGGING_FACE_API_TOKEN"

# ------------------ MODELS ------------------
class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(100), nullable=False)
    profile = db.Column(db.Text)  # Store questionnaire data as JSON string

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

#------------------STORE HISTORY------------------
def log_search_history(username, query, results):
    history_file = "search_history.json"

    # Create if doesn't exist
    if not os.path.exists(history_file):
        with open(history_file, "w") as f:
            json.dump({}, f)

    # Load existing history
    with open(history_file, "r") as f:
        history_data = json.load(f)

    # Add new entry for user
    if username not in history_data:
        history_data[username] = []

    history_data[username].append({
        "query": query,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "results": results  # List of top video titles or URLs
    })

    # Save updated history
    with open(history_file, "w") as f:
        json.dump(history_data, f, indent=4)


# ------------------ ROUTES ------------------
@app.route('/register', methods=['POST'])
def register():
    data = request.json
    new_user = User(username=data['username'], password=data['password'])
    db.session.add(new_user)
    db.session.commit()
    return jsonify({"message": "User registered successfully"})

@app.route('/login', methods=['POST'])
def login():
    data = request.json
    user = User.query.filter_by(username=data['username'], password=data['password']).first()
    if user:
        login_user(user)
        return jsonify({"message": "Login successful"})
    else:
        return jsonify({"message": "Invalid credentials"}), 401

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return jsonify({"message": "Logged out"})

# ------------------ QUESTIONNAIRE ------------------
@app.route('/questionnaire', methods=['POST'])
@login_required
def questionnaire():
    user = User.query.get(session['_user_id'])
    profile_data = request.json
    user.profile = json.dumps(profile_data)
    db.session.commit()
    return jsonify({"message": "Profile updated"})

# ------------------ YOUTUBE SEARCH API ------------------
@app.route('/youtube', methods=['POST'])
@login_required
def youtube_search():
    data = request.get_json()
    query = data.get('query')

    url = f"https://www.googleapis.com/youtube/v3/search?part=snippet&type=video&maxResults=5&q={query}&key={YOUTUBE_API_KEY}"
    response = requests.get(url)

    if response.status_code == 200:
        videos = response.json().get('items', [])
        results = [
            {
                "title": vid["snippet"]["title"],
                "channel": vid["snippet"]["channelTitle"],
                "video_url": f"https://www.youtube.com/watch?v={vid['id']['videoId']}"
            }
            for vid in videos
        ]

        # ✅ Save history
        log_search_history(current_user.username, query, [r["title"] for r in results])

        return jsonify(results)
    else:
        return jsonify({"error": "YouTube API failed"}), 500


# ------------------ HUGGING FACE SUMMARIZATION ------------------
@app.route('/summarize', methods=['POST'])
@login_required
def summarize_text():
    input_text = request.json.get("text")
    headers = {
        "Authorization": f"Bearer {HF_TOKEN}"
    }
    data = {
        "inputs": input_text,
        "parameters": {"max_length": 100, "min_length": 30}
    }

    response = requests.post(
        "https://api-inference.huggingface.co/models/facebook/bart-large-cnn",
        headers=headers,
        json=data
    )

    result = response.json()
    if isinstance(result, list):
        return jsonify({"summary": result[0]["summary_text"]})
    else:
        return jsonify({"error": result.get("error", "Unknown error")})

# ------------------ MAIN ------------------
if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)
# login, fill questionnaire, give inputs, get video links with summary options.
# stores search history