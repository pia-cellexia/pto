import os
import time
import threading
import requests
from flask import Flask
from dotenv import load_dotenv

load_dotenv()

# ENV vars
NOTION_TOKEN = os.getenv("NOTION_TOKEN")
DATABASE_ID = os.getenv("NOTION_DATABASE_ID")
SLACK_BOT_TOKEN = os.getenv("SLACK_BOT_TOKEN")
SLACK_CHANNEL_ID = os.getenv("SLACK_CHANNEL_ID")

NOTION_HEADERS = {
    "Authorization": f"Bearer {NOTION_TOKEN}",
    "Notion-Version": "2022-06-28",
    "Content-Type": "application/json"
}

seen_pages = set()

def query_notion():
    url = f"https://api.notion.com/v1/databases/{DATABASE_ID}/query"
    response = requests.post(url, headers=NOTION_HEADERS)
    return response.json().get("results", [])

def extract_fields(page):
    props = page.get("properties", {})

    title = (
        props.get("PTO Request Title", {}).get("title", [{}])[0]
        .get("text", {}).get("content", "Untitled")
    )

    pto_type = (
        props.get("PTO Type", {}).get("select", {}).get("name", "N/A")
    )

    date_range = props.get("Start Date", {}).get("date", {})
    start_date = date_range.get("start", "N/A")
    end_date = date_range.get("end", start_date) if date_range else start_date

    notes = (
        props.get("Additional Notes", {}).get("rich_text", [{}])[0]
        .get("text", {}).get("content", "None")
    )

    return title, pto_type, start_date, end_date, notes


def send_to_slack(title, pto_type, start_date, end_date, notes):
    msg = f"📌 *New PTO Request!*\n*Title:* {title}\n*Type:* {pto_type}\n*Dates:* {start_date} → {end_date}\n*Notes:* {notes}"
    requests.post(
        "https://slack.com/api/chat.postMessage",
        headers={
            "Authorization": f"Bearer {SLACK_BOT_TOKEN}",
            "Content-Type": "application/json"
        },
        json={
            "channel": SLACK_CHANNEL_ID,
            "text": msg
        }
    )

def poll_notion():
    print("✅ Notion poller running.")
    while True:
        try:
            pages = query_notion()
            for page in pages:
                page_id = page["id"]
                if page_id not in seen_pages:
                    seen_pages.add(page_id)
                    fields = extract_fields(page)
                    send_to_slack(*fields)
        except Exception as e:
            print("⚠️ Polling error:", e)
        time.sleep(30)

# --- Flask dummy app ---
app = Flask(__name__)

@app.route("/")
def index():
    return "👋 Notion poller is running.", 200

# --- Start poller in a thread ---
threading.Thread(target=poll_notion, daemon=True).start()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
