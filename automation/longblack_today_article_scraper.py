import requests
from bs4 import BeautifulSoup
import datetime
import pytz
from supabase import create_client, Client
import os
from dotenv import load_dotenv
import json

# Load environment variables
load_dotenv(".env")

SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")
SLACK_WEBHOOK_URL = os.getenv("DEV_ARTICLE_SLACK_WEBHOOK_URL", "")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

def get_kst_today():
    return datetime.datetime.now(pytz.timezone("Asia/Seoul")).strftime("%Y-%m-%d")

def fetch_today_note_link():
    url = "https://www.longblack.co/"
    headers = {
        "User-Agent": "Mozilla/5.0"
    }

    response = requests.get(url, headers=headers)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")
    link_container = soup.find("div", class_="today-note-link")
    if link_container:
        anchor = link_container.find("a", href=True)
        if anchor:
            return anchor["href"]
    return None

def save_to_supabase(article_url: str):
    today = get_kst_today()

    # 중복 방지
    existing = supabase.table("longblack_today_article").select("*").eq("url", article_url).execute()
    if existing.data:
        print("Today's article already exists in Supabase.")
        return False

    # 저장
    supabase.table("longblack_today_article").insert({
        "url": article_url,
        "created_at": today
    }).execute()
    print("Saved to Supabase.")
    return True

def notify_slack(article_url: str):
    message = {
        "text": f"☕️ *Longblack 오늘의 노트 읽으러 가기* ☕️ \n{article_url}"
    }

    response = requests.post(
        SLACK_WEBHOOK_URL,
        data=json.dumps(message),
        headers={"Content-Type": "application/json"}
    )

    if response.status_code == 200:
        print("Slack notification sent.")
    else:
        print(f"Failed to send Slack message: {response.text}")

def main():
    print("🔍 Fetching today’s Longblack article...")
    article_url = fetch_today_note_link()
    if not article_url:
        print("⚠️ 오늘의 노트 링크를 찾지 못했습니다.")
        return

    if save_to_supabase(article_url):
        notify_slack(article_url)

if __name__ == "__main__":
    main()