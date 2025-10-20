import os
import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from urllib.parse import urlparse, parse_qs
import json
from datetime import datetime
import re
import sys
from supabase import create_client, Client
import time

load_dotenv(".env")

# Configuration
SLACK_WEBHOOK_URL = os.getenv("DCINSIDE_SLACK_WEBHOOK_URL", "")
DC_GALLERY_URL = "https://gall.dcinside.com/mgallery/board/lists/?id=plabfootball"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124"
}

# Initialize Supabase client
supabase: Client = create_client(
    os.getenv("SUPABASE_URL", ""),
    os.getenv("SUPABASE_KEY", "")
)

def normalize_to_date_str(raw):
    """Normalize various DCInside date displays to YYYY-MM-DD.

    - List shows HH:MM for today → return today's date
    - List shows MM.DD or MM-DD → use current year
    - Detail page often shows YYYY.MM.DD HH:MM:SS → extract date part
    - Fallback to today's date on parse failure
    """
    try:
        if not raw:
            return datetime.now().date().isoformat()

        s = str(raw).strip()

        # If it looks like time-only (e.g., 12:34), use today's date
        if re.search(r"\b\d{1,2}:\d{2}\b", s):
            return datetime.now().date().isoformat()

        # Unify delimiters
        cleaned = re.sub(r"[\./]", "-", s)

        # Extract YYYY-MM-DD if present
        m = re.search(r"(\d{4}-\d{1,2}-\d{1,2})", cleaned)
        if m:
            y, mth, d = [int(x) for x in m.group(1).split('-')]
            return f"{y:04d}-{mth:02d}-{d:02d}"

        # Extract MM-DD (no year) → assume current year
        m = re.search(r"\b(\d{1,2})-(\d{1,2})\b", cleaned)
        if m:
            mm, dd = int(m.group(1)), int(m.group(2))
            year = datetime.now().year
            return f"{year:04d}-{mm:02d}-{dd:02d}"

        # Try common formats as a fallback
        for fmt in ("%Y-%m-%d", "%Y.%m.%d", "%m-%d", "%m.%d", "%Y/%m/%d"):
            try:
                dt = datetime.strptime(s, fmt)
                if "%Y" in fmt:
                    return dt.date().isoformat()
                return dt.replace(year=datetime.now().year).date().isoformat()
            except Exception:
                pass

        # Last resort: today
        return datetime.now().date().isoformat()
    except Exception:
        return datetime.now().date().isoformat()

def get_post_details(post_url):
    """Fetch post detail page to extract title, author, content, and a full date if available.

    Returns dict: {
        'title': str | None,
        'author': str | None,
        'content': str | None,
        'date': 'YYYY-MM-DD' | None
    }
    """
    content, normalized_date, detail_title, detail_author = None, None, None, None
    try:
        response = requests.get(post_url, headers=HEADERS)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, 'html.parser')

        # Extract title (try multiple selectors for robustness)
        title_selectors = [
            'span.title_subject',
            'div.title_subject',
            'h3.title_headtext',
            'h3.title',
        ]
        for sel in title_selectors:
            el = soup.select_one(sel)
            if el and el.get_text(strip=True):
                detail_title = el.get_text(strip=True)
                break

        # Extract author (try multiple strategies)
        author_selectors = [
            'span.nickname',
            'span.gall_writer',
            'span.ub-writer',
            'div.gall_writer',
        ]
        for sel in author_selectors:
            el = soup.select_one(sel)
            if el:
                # Prefer data-nick if present
                nick = el.get('data-nick') or el.get_text(strip=True)
                if nick:
                    detail_author = nick.strip()
                    break

        # Extract content
        content_div = soup.select_one('div.write_div')
        if content_div:
            for img in content_div.find_all('img'):
                img.decompose()
            content = content_div.get_text(strip=True, separator='\n')

        # Extract date from detail page (usually has full date)
        date_el = soup.select_one('span.gall_date')
        if date_el:
            normalized_date = normalize_to_date_str(date_el.get_text(strip=True))

        return {
            'title': detail_title,
            'author': detail_author,
            'content': content,
            'date': normalized_date,
        }
    except Exception as e:
        print(f"Error fetching post details: {e}", file=sys.stderr)
        return {
            'title': detail_title,
            'author': detail_author,
            'content': content,
            'date': normalized_date,
        }

def get_post_content(post_url):
    # Deprecated: content is fetched via get_post_details
    try:
        return get_post_details(post_url).get('content')
    except Exception:
        return None

def get_posts():
    try:
        response = requests.get(DC_GALLERY_URL, headers=HEADERS)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        posts = []
        
        # Find all post rows
        post_rows = soup.select('tr.ub-content')
        
        for row in post_rows:
            try:
                # Extract post url
                title_element = row.select_one('td.gall_tit a')
                if not title_element:
                    continue
                post_url = "https://gall.dcinside.com" + title_element['href']
                qs = parse_qs(urlparse(post_url).query)
                post_id = normalize_post_id(qs.get("no", [None])[0])
                if not post_id:
                    continue
                
                # Get post details (title, author, content, date)
                details = get_post_details(post_url)

                # Use only detail values (no fallback to list for title/author/date)
                title = details.get('title')
                author = details.get('author')
                content = details.get('content')
                date = details.get('date')
                
                posts.append({
                    'post_id': post_id,
                    'title': title or '',
                    'url': post_url,
                    'author': author or '',
                    'date': date or normalize_to_date_str(None),
                    'content': content,
                    'created_at': datetime.now().isoformat()
                })
                
                # Be nice to the server
                time.sleep(1)
                
            except Exception as e:
                print(f"Error parsing post: {e}", file=sys.stderr)
                continue
                
        return posts
    except Exception as e:
        print(f"Error fetching posts: {e}", file=sys.stderr)
        return []

def is_post_exists(post_id):
    try:
        pid = normalize_post_id(post_id)
        if not pid:
            print("[exists] normalize -> None", file=sys.stderr)
            return False
        resp = (
            supabase.table('dc_posts')
            .select('id', count='exact', head=True)
            .eq('post_id', pid)
            .execute()
        )
        print(f"[exists] pid={pid} count={resp.count}", file=sys.stderr)
        return (resp.count or 0) > 0
    except Exception as e:
        print(f"Error checking post existence: {e}", file=sys.stderr)
        return False

def normalize_post_id(raw):
    if raw is None:
        return None
    s = str(raw)
    # & 뒤 꼬리 제거
    s = s.split('&', 1)[0]
    # 숫자 뒤 꼬리 제거 (더 안전)
    s = re.sub(r'[^0-9].*$', '', s)
    return int(s) or None

def save_post(post) -> bool:
    try:
        post['post_id'] = normalize_post_id(post.get('post_id'))
        post['created_at'] = datetime.utcnow().isoformat() + 'Z'
        r = (supabase
             .table('dc_posts')
             .upsert(post, on_conflict='post_id')
             .execute())
        print(f"[save] upsert ok id={post['post_id']} resp={getattr(r, 'count', None)}", file=sys.stderr)
        return True
    except Exception as e:
        print(f"Error saving post: {e}", file=sys.stderr)
        return False

def send_to_slack(post):
    # 본문이 너무 길 경우 잘라서 표시
    content_preview = post['content'][:200] + '...' if post['content'] and len(post['content']) > 200 else post['content']
    
    message = {
        "blocks": [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": "📢 새로운 게시글이 등록되었습니다",
                    "emoji": True
                }
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*{post['title']}*"
                }
            },
            {
                "type": "section",
                "fields": [
                    {
                        "type": "mrkdwn",
                        "text": f"*작성자:*\n{post['author']}"
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*작성일:*\n{post['date']}"
                    }
                ]
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*본문:*\n{content_preview}"
                }
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"<{post['url']}|게시글 보기>"
                }
            },
            {
                "type": "divider"
            }
        ]
    }
    
    try:
        response = requests.post(
            SLACK_WEBHOOK_URL,
            data=json.dumps(message),
            headers={'Content-Type': 'application/json'}
        )
        response.raise_for_status()
        print(f"Successfully sent post to Slack: {post['title']}")
    except Exception as e:
        print(f"Error sending to Slack: {e}", file=sys.stderr)

def main():
    try:
        current_posts = get_posts()
        
        for post in current_posts:
            if not is_post_exists(post['post_id']):
                if save_post(post):           # 저장이 성공했을 때만
                    send_to_slack(post)       # 슬랙 전송
    except Exception as e:
        print(f"Error in main: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
