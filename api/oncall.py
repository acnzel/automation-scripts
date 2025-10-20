import os
import json
from datetime import datetime, timedelta
from http.server import BaseHTTPRequestHandler
from supabase import create_client
import pytz

# Supabase 클라이언트 초기화
supabase = create_client(
    os.environ.get("SUPABASE_URL", ""),
    os.environ.get("SUPABASE_KEY", "")
)

def get_kst_now():
    """현재 한국 시간을 반환"""
    kst = pytz.timezone('Asia/Seoul')
    return datetime.now(kst)

def format_date(date):
    """날짜를 YYYY-MM-DD 형식으로 변환"""
    return date.strftime("%Y-%m-%d")

def get_oncall_schedule():
    """오늘부터 한 달 이내의 온콜 스케줄 조회"""
    today = get_kst_now()
    end_date = today + timedelta(days=30)

    try:
        response = supabase.table('oncall_rotation') \
            .select('*') \
            .gte('date', format_date(today)) \
            .lte('date', format_date(end_date)) \
            .order('date') \
            .execute()

        if response.data:
            return response.data
        return []
    except Exception as e:
        print(f"Error getting schedule from Supabase: {e}")
        return []

def format_slack_message(schedule_data):
    """Slack 메시지 포맷으로 변환"""
    if not schedule_data:
        return {
            'response_type': 'in_channel',
            'text': '📅 향후 30일간 예정된 온콜 스케줄이 없습니다.'
        }

    # Block Kit 형식으로 메시지 구성
    blocks = [
        {
            'type': 'header',
            'text': {
                'type': 'plain_text',
                'text': '📅 온콜 스케줄 (향후 30일)',
                'emoji': True
            }
        },
        {
            'type': 'divider'
        }
    ]

    # 요일 한글 매핑
    weekday_map = {
        0: '월',
        1: '화',
        2: '수',
        3: '목',
        4: '금',
        5: '토',
        6: '일'
    }

    kst = pytz.timezone('Asia/Seoul')

    for item in schedule_data:
        # YYYY-MM-DD 형식의 날짜를 파싱 (KST 기준)
        date_obj = datetime.strptime(item['date'], '%Y-%m-%d')
        date_obj = kst.localize(date_obj)

        weekday = date_obj.weekday()
        weekday_str = weekday_map[weekday]

        # 날짜와 담당자 표시
        blocks.append({
            'type': 'section',
            'text': {
                'type': 'mrkdwn',
                'text': f"• `{item['date']} ({weekday_str})` - {item['member']}"
            }
        })

    # 푸터 추가
    now = get_kst_now()
    timestamp = now.strftime("%Y-%m-%d %H:%M:%S KST")

    blocks.extend([
        {
            'type': 'divider'
        },
        {
            'type': 'context',
            'elements': [
                {
                    'type': 'mrkdwn',
                    'text': f"_마지막 업데이트: {timestamp}_"
                }
            ]
        }
    ])

    return {
        'response_type': 'in_channel',
        'blocks': blocks
    }

class handler(BaseHTTPRequestHandler):
    """Vercel Serverless Function 핸들러"""

    def do_GET(self):
        """GET 요청 처리 (테스트용)"""
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.end_headers()

        response = {
            'message': 'Oncall Schedule Webhook is running!',
            'usage': "This endpoint is designed for Slack slash command '/온콜리스트'"
        }

        self.wfile.write(json.dumps(response, ensure_ascii=False).encode('utf-8'))

    def do_POST(self):
        """POST 요청 처리 (Slack slash command)"""
        try:
            # 온콜 스케줄 조회
            schedule = get_oncall_schedule()

            # Slack 메시지 포맷으로 변환
            slack_response = format_slack_message(schedule)

            # 응답 전송
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(slack_response, ensure_ascii=False).encode('utf-8'))

        except Exception as e:
            print(f"Error in handler: {e}")

            # 에러 응답
            self.send_response(500)
            self.send_header('Content-type', 'application/json')
            self.end_headers()

            error_response = {
                'response_type': 'ephemeral',
                'text': f'⚠️ 오류가 발생했습니다: {str(e)}'
            }

            self.wfile.write(json.dumps(error_response, ensure_ascii=False).encode('utf-8'))
