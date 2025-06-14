from flask import Flask, request
import os, requests
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

NOTION_TOKEN = os.getenv("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")
NOTION_DATABASE_ID = os.getenv("21237a247b59807090bff4fdff6906e8")
SLACK_BOT_TOKEN = os.getenv("SLACK_BOT_TOKEN")
SLACK_CHANNEL_ID = os.getenv("C091GPWSE84")

NOTION_HEADERS = {
    "Authorization": f"Bearer {NOTION_TOKEN}",
    "Notion-Version": "2022-06-28",
    "Content-Type": "application/json"
}

def send_to_slack(message):
    requests.post(
        "https://slack.com/api/chat.postMessage",
        headers={
            "Authorization": f"Bearer {SLACK_BOT_TOKEN}",
            "Content-Type": "application/json"
        },
        json={
            "channel": SLACK_CHANNEL_ID,
            "text": message
        }
    )

@app.route("/notion-webhook", methods=["POST"])
def notion_webhook():
    data = request.json
    if data.get("event") == "page.created":
        page_id = data["resource"]["id"]
        r = requests.get(f"https://api.notion.com/v1/pages/{page_id}", headers=NOTION_HEADERS)
        props = r.json().get("properties", {})

        title = props.get("PTO Request Title", {}).get("title", [{}])[0].get("text", {}).get("content", "Untitled")
        pto_type = props.get("PTO Type", {}).get("select", {}).get("name", "N/A")
        start_date = props.get("Start Date", {}).get("date", {}).get("start", "N/A")
        end_date = props.get("End Date", {}).get("date", {}).get("start", "N/A")
        notes = props.get("Additional Notes", {}).get("rich_text", [{}])[0].get("text", {}).get("content", "None")

        message = (
            f"📌 *New PTO Request!*\n"
            f"*Title:* {title}\n"
            f"*Type:* {pto_type}\n"
            f"*Dates:* {start_date} → {end_date}\n"
            f"*Notes:* {notes}"
        )
        send_to_slack(message)
    return "", 200
