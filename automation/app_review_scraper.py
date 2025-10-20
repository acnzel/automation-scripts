from dotenv import load_dotenv
from google_play_scraper import reviews, Sort
from supabase import create_client
import json
import os
import requests
import xml.etree.ElementTree as ET

load_dotenv(".env")

APPS = {
    "plab": {
        "app_name": "플랩풋볼",
        "table_name": "plab_review",
        "slack_webhook_url": os.getenv("PLAB_SLACK_WEBHOOK_URL"),
        "google_package_name": "com.myplaycompany.plab",
        "apple_app_id": 6608972481,
        "count": 20
    },
    "manager": {
        "app_name": "플랩풋볼-매니저",
        "table_name": "manager_review",
        "slack_webhook_url": os.getenv("MANAGER_SLACK_WEBHOOK_URL"),
        "google_package_name": "com.myplaycompany.plabmanager",
        "apple_app_id": 6468979995,
        "count": 20
    },
    "iamground": {
        "app_name": "아이엠그라운드-국민-풋살-어플",
        "table_name": "iamground_review",
        "slack_webhook_url": os.getenv("IAMGROUND_SLACK_WEBHOOK_URL"),
        "google_package_name": "kr.iamground.android",
        "apple_app_id": 1254343213,
        "count": 20
    },
    "puzzle": {
        "app_name": "퍼즐플레이",
        "table_name": "puzzle_review",
        "slack_webhook_url": os.getenv("PUZZLE_SLACK_WEBHOOK_URL"),
        "google_package_name": "com.pzcnc.pzsports",
        "apple_app_id": 1660698667,
        "count": 20
    },
    "letsgoale": {
        "app_name": "레츠고알레",
        "table_name": "letsgoale_review",
        "slack_webhook_url": os.getenv("LETSGOALE_SLACK_WEBHOOK_URL"),
        "google_package_name": "kr.goale.app",
        "apple_app_id": 6451382722,
        "count": 20
    },
    "matchup": {
        "app_name": "매치업",
        "table_name": "matchup_review",
        "slack_webhook_url": os.getenv("MATCHUP_SLACK_WEBHOOK_URL"),
        "google_package_name": "kr.co.matchup",
        "apple_app_id":1463155313,
        "count": 20
    }    
}

class AppReviewScraper:
    def __init__(self, app_name, table_name, slack_webhook_url, google_package_name, apple_app_id, count=10):
        self.app_name = app_name
        self.table_name = table_name
        self.slack_webhook_url = slack_webhook_url
        self.google_package_name = google_package_name
        self.apple_app_id = apple_app_id
        self.count = count
        
        self.supabase = create_client(
            os.getenv("SUPABASE_URL"),
            os.getenv("SUPABASE_KEY")
        )

    def review_exists(self, review_id, platform_type):
        result = self.supabase.table(self.table_name) \
            .select('platform_review_id') \
            .eq('platform_review_id', review_id) \
            .eq('platform_type', platform_type) \
            .execute()
        return len(result.data) > 0

    def save_review_to_supabase(self, review_id, platform, user, rating, review, created_at):
        self.supabase.table(self.table_name).insert({
            'platform_type': platform,
            'user_name': user,
            'rating': rating,
            'review': review,
            'created_at': created_at,
            'platform_review_id': review_id
        }).execute()

    def get_star_rating(self, rating):
        try:
            rating = int(rating)
            return "⭐️" * rating
        except Exception:
            return ""

    def send_to_slack(self, platform, name, rating, content, created_at):
        stars = self.get_star_rating(rating)
        created_line = f"\n🕒 작성일: {created_at}" if created_at else ""
        msg = (
            f"📱 *{platform} 리뷰 도착!*\n"
            f"🧚‍♀️ 이름: {name}\n"
            f"⭐️ 평점: {stars} (*{rating}점*)\n"
            f"💬 내용: {content}\n"
            f"{created_line}"
        )
        headers = {'Content-Type': 'application/json; charset=utf-8'}
        requests.post(self.slack_webhook_url, data=json.dumps({"text": msg}), headers=headers)

    def process_google_play(self):
        new_reviews, _ = reviews(self.google_package_name, lang='ko', country='kr', count=self.count, sort=Sort.NEWEST)
        for r in new_reviews:
            review_id = r['reviewId']
            if self.review_exists(review_id, "google_play"):
                continue
            created_at = r['at'].isoformat()
            self.save_review_to_supabase(review_id, "google_play", r['userName'], r['score'], r['content'], created_at)
            self.send_to_slack("Google Play", r['userName'], r['score'], r['content'], created_at)

    def process_app_store(self):
        if not self.apple_app_id:
            print(f"⚠️ App ID가 없어 RSS 호출을 건너뜁니다: {self.app_name}")
            return

        rss_url = f"https://itunes.apple.com/kr/rss/customerreviews/page=1/id={self.apple_app_id}/sortby=mostrecent/xml"

        try:
            response = requests.get(rss_url)
            response.raise_for_status()
            root = ET.fromstring(response.content)
        except Exception as e:
            print(f"❌ RSS 리뷰 요청 실패: {e}")
            return

        ns = {'atom': 'http://www.w3.org/2005/Atom', 'im': 'http://itunes.apple.com/rss'}
        entries = root.findall('atom:entry', ns)

        if not entries or len(entries) <= 1:
            print("ℹ️ 리뷰 항목이 없습니다 (또는 첫 번째는 앱 메타 정보입니다).")
            return

        for entry in entries[1:]:  # 첫 번째 entry는 앱 설명, 제외
            try:
                review_id = entry.find('atom:id', ns).text
                user = entry.find('atom:author/atom:name', ns).text
                rating = int(entry.find('im:rating', ns).text)
                title = entry.find('atom:title', ns).text or ""
                body = entry.find('atom:content', ns).text or ""
                created_at = entry.find('atom:updated', ns).text
                content = f"{title}\n{body}".strip()

                if self.review_exists(review_id, "app_store"):
                    continue

                self.save_review_to_supabase(review_id, "app_store", user, rating, content, created_at)
                self.send_to_slack("App Store", user, rating, content, created_at)
            except Exception as e:
                print(f"⚠️ 리뷰 파싱 중 오류 발생: {e}")

    def run(self):
        self.process_google_play()
        self.process_app_store()


if __name__ == "__main__":
    for app_name, app_config in APPS.items():
        print(f"\nProcessing {app_name}...")
        scraper = AppReviewScraper(**app_config)
        scraper.run() 