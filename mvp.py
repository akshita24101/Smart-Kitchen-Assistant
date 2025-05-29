from flask import Flask, request, jsonify
from youtubesearchpython import YoutubeSearch
from youtube_transcript_api import YouTubeTranscriptApi
import requests
import re
from googleapiclient.discovery import build
from textblob import TextBlob

app = Flask(__name__)

# 🔑 Replace with your actual YouTube Data API Key and Hugging Face Token
YOUTUBE_API_KEY = "YOUR_YOUTUBE_API_KEY"
HUGGINGFACE_TOKEN = "YOUR_HUGGINGFACE_TOKEN"

# ---------- Utility Functions ----------

def search_youtube_videos(query, max_results=5):
    search = YoutubeSearch(query, max_results=max_results)
    results = search.to_dict()
    return results

def get_video_comments(video_id):
    youtube = build("youtube", "v3", developerKey=YOUTUBE_API_KEY)
    request = youtube.commentThreads().list(
        part="snippet",
        videoId=video_id,
        maxResults=100,
        textFormat="plainText"
    )
    response = request.execute()

    comments = []
    for item in response.get("items", []):
        text = item["snippet"]["topLevelComment"]["snippet"]["textDisplay"]
        comments.append(text)

    return comments

def analyze_sentiment(comments):
    pos_count = 0
    for comment in comments:
        blob = TextBlob(comment)
        if blob.sentiment.polarity > 0.2:
            pos_count += 1
    return pos_count / len(comments) if comments else 0

def get_transcript(video_id):
    try:
        transcript = YouTubeTranscriptApi.get_transcript(video_id)
        full_text = " ".join([segment['text'] for segment in transcript])
        return full_text
    except:
        return None

def summarize_text(text):
    headers = {
        "Authorization": f"Bearer {HUGGINGFACE_TOKEN}"
    }
    payload = {
        "inputs": text[:1000]  # Shorten if needed for demo
    }

    response = requests.post(
        "https://api-inference.huggingface.co/models/facebook/bart-large-cnn",
        headers=headers,
        json=payload
    )

    if response.status_code == 200:
        return response.json()[0]['summary_text']
    else:
        return "Summary not available."

# ---------- Flask Routes ----------

@app.route('/get_recipe_suggestions', methods=['POST'])
def get_recipe_suggestions():
    data = request.json
    ingredients = ", ".join(data.get("ingredients", []))
    meal_type = data.get("meal_type", "")
    prep_time = data.get("prep_time", "")
    query = f"{meal_type} recipe with {ingredients} in {prep_time} minutes"

    search_results = search_youtube_videos(query)
    response_data = []

    for result in search_results:
        video_id = result['id']
        title = result['title']
        link = "https://www.youtube.com" + result['url_suffix']

        comments = get_video_comments(video_id)
        sentiment_score = analyze_sentiment(comments)

        if sentiment_score >= 0.6:  # Filter on positive comments
            transcript = get_transcript(video_id)
            if transcript:
                summary = summarize_text(transcript)
            else:
                summary = "Transcript not available"

            response_data.append({
                "title": title,
                "video_id": video_id,
                "link": link,
                "positivity_score": sentiment_score,
                "summary": summary
            })

    return jsonify(response_data)


@app.route('/summarize_video/<video_id>', methods=['GET'])
def summarize_video(video_id):
    transcript = get_transcript(video_id)
    if not transcript:
        return jsonify({"summary": "Transcript not available"})
    summary = summarize_text(transcript)
    return jsonify({"summary": summary})


if __name__ == '__main__':
    app.run(debug=True)
