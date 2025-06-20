import os
import time
import json
import threading
import requests
from flask import Flask
from dotenv import load_dotenv

load_dotenv()

NOTION_TOKEN = os.getenv("NOTION_TOKEN")
DATABASE_ID = os.getenv("NOTION_DATABASE_ID")
SLACK_BOT_TOKEN = os.getenv("SLACK_BOT_TOKEN")
SLACK_CHANNEL_ID = os.getenv("SLACK_CHANNEL_ID")

NOTION_HEADERS = {
    "Authorization": f"Bearer {NOTION_TOKEN}",
    "Notion-Version": "2022-06-28",
    "Content-Type": "application/json"
}

LAST_SEEN_FILE = "last_seen.txt"

def load_last_seen():
    if os.path.exists(LAST_SEEN_FILE):
        with open(LAST_SEEN_FILE, "r") as f:
            return f.read().strip()
    return ""

def save_last_seen(last):
    with open(LAST_SEEN_FILE, "w") as f:
        f.write(last)

def query_notion():
    url = f"https://api.notion.com/v1/databases/{DATABASE_ID}/query"
    response = requests.post(url, headers=NOTION_HEADERS)
    return response.json().get("results", [])

def extract_fields(page):
    props = page.get("properties", {})

    def find_key_like(target):
        return next((k for k in props if target.lower() in k.lower()), None)

    title_key = find_key_like("PTO Request Title")
    type_key = find_key_like("PTO Type")
    date_key = find_key_like("PTO Date")
    notes_key = find_key_like("Additional Notes")
    creator = props.get(respondent_key, {}).get("created_by", {})
    name = creator.get("name")
    email = creator.get("person", {}).get("email")
    
    if name and email:
        respondent = f"{name} ({email})"
    elif email:
        respondent = email
    else:
        respondent = "Anonymous"


    # Title
    title = (
        props.get(title_key, {}).get("title", [{}])[0]
        .get("text", {}).get("content", "Untitled")
    ) if title_key else "Untitled"

    # PTO Type (multi_select or select)
    type_prop = props.get(type_key, {}) if type_key else {}
    multi_select = type_prop.get("multi_select", [])
    if multi_select:
        pto_type = ", ".join([opt.get("name", "N/A") for opt in multi_select])
    else:
        pto_type = type_prop.get("select", {}).get("name", "N/A")

    # PTO Dates
    date_range = props.get(date_key, {}).get("date", {}) if date_key else {}
    start_date = date_range.get("start", "N/A")
    end_date = date_range.get("end", start_date)

    # Notes
    notes = (
        props.get(notes_key, {}).get("rich_text", [{}])[0]
        .get("text", {}).get("content", "None")
    ) if notes_key else "None"

    # ✅ Correct Respondent extraction
    respondent = (
        props.get(respondent_key, {})
             .get("created_by", {})
             .get("name", "Anonymous")
    ) if respondent_key else "Anonymous"

    return title, pto_type, start_date, end_date, notes, respondent


def send_to_slack(title, pto_type, start_date, end_date, notes, respondent):
    msg = (
        f"*New PTO Request!*\n"
        f"*Respondent:* {respondent}\n"
        f"*Title:* {title}\n"
        f"*Type:* {pto_type}\n"
        f"*Dates:* {start_date} → {end_date}\n"
        f"*Notes:* {notes}"
    )
    requests.post(
        "https://slack.com/api/chat.postMessage",
        headers={
            "Authorization": f"Bearer {SLACK_BOT_TOKEN}",
            "Content-Type": "application/json"
        },
        json={"channel": SLACK_CHANNEL_ID, "text": msg}
    )

from datetime import datetime, timedelta

def poll_notion():
    print("✅ Notion poller running (time-filtered).")
    while True:
        try:
            pages = query_notion()
            now = datetime.utcnow()
            for page in pages:
                created = page.get("created_time", "")
                created_dt = datetime.fromisoformat(created.replace("Z", "+00:00"))
                # only post pages created in the last 3 minutes
                if (now - created_dt) < timedelta(minutes=3):
                    fields = extract_fields(page)
                    send_to_slack(*fields)
        except Exception as e:
            print("⚠️ Error during polling:", e)
        time.sleep(30)

# -- dummy Flask app for Render --
app = Flask(__name__)

@app.route("/")
def index():
    return "👋 Polling server active", 200

threading.Thread(target=poll_notion, daemon=True).start()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
