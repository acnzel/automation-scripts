import os
import json
from datetime import datetime
from http.server import BaseHTTPRequestHandler
from urllib.parse import parse_qs
from supabase import create_client
import pytz
import requests
from concurrent.futures import ThreadPoolExecutor
import time

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

def parse_command_text(text):
    """
    슬랙 명령어 텍스트를 파싱하여 두 멤버 이름을 추출
    예: "엔도 로쿤" -> ["엔도", "로쿤"]
    """
    if not text:
        return None

    # 공백으로 분리
    members = text.strip().split()

    # 정확히 2명의 이름이 있어야 함
    if len(members) != 2:
        return None

    return members

def get_nearest_future_schedule(member_name, today_str):
    """특정 멤버의 오늘 이후 가장 가까운 온콜 스케줄 조회"""
    try:
        response = supabase.table('oncall_rotation') \
            .select('*') \
            .eq('member', member_name) \
            .gte('date', today_str) \
            .order('date') \
            .limit(1) \
            .execute()

        if response.data and len(response.data) > 0:
            return response.data[0]
        return None
    except Exception as e:
        print(f"Error getting schedule for {member_name}: {e}")
        return None

def swap_schedules(original_schedule1, original_schedule2):
    """두 스케줄의 담당자를 서로 바꿈"""
    try:
        # 원본 멤버 이름을 미리 저장 (참조 문제 방지)
        member1 = original_schedule1['member']
        member2 = original_schedule2['member']

        print(f"Swapping: {member1} (id={original_schedule1['id']}) <-> {member2} (id={original_schedule2['id']})")

        # 첫 번째 스케줄 업데이트: schedule1에 member2 할당
        result1 = supabase.table('oncall_rotation') \
            .update({'member': member2}) \
            .eq('id', original_schedule1['id']) \
            .execute()
        print(f"Updated schedule {original_schedule1['id']} to {member2}")

        # 두 번째 스케줄 업데이트: schedule2에 member1 할당
        result2 = supabase.table('oncall_rotation') \
            .update({'member': member1}) \
            .eq('id', original_schedule2['id']) \
            .execute()
        print(f"Updated schedule {original_schedule2['id']} to {member1}")

        return True
    except Exception as e:
        print(f"Error swapping schedules: {e}")
        import traceback
        traceback.print_exc()
        return False

def format_slack_response(success, member1, member2, schedule1, schedule2, error_msg=None):
    """Slack 응답 메시지 포맷"""
    if not success:
        return {
            'response_type': 'in_channel',
            'text': f'⚠️ 온콜 일정 변경에 실패했습니다.\n\n{error_msg}'
        }

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

    # 날짜 파싱 및 요일 계산
    date1_obj = datetime.strptime(schedule1['date'], '%Y-%m-%d')
    date1_obj = kst.localize(date1_obj)
    weekday1 = weekday_map[date1_obj.weekday()]

    date2_obj = datetime.strptime(schedule2['date'], '%Y-%m-%d')
    date2_obj = kst.localize(date2_obj)
    weekday2 = weekday_map[date2_obj.weekday()]

    # Block Kit 형식으로 메시지 구성
    blocks = [
        {
            'type': 'header',
            'text': {
                'type': 'plain_text',
                'text': '✅ 온콜 일정이 변경되었습니다',
                'emoji': True
            }
        },
        {
            'type': 'divider'
        },
        {
            'type': 'section',
            'text': {
                'type': 'mrkdwn',
                'text': f"*{member1}*와 *{member2}*의 일정이 교체되었습니다."
            }
        },
        {
            'type': 'section',
            'fields': [
                {
                    'type': 'mrkdwn',
                    'text': f"*{schedule1['date']} ({weekday1})*\n{schedule1['member']} → *{member2}*"
                },
                {
                    'type': 'mrkdwn',
                    'text': f"*{schedule2['date']} ({weekday2})*\n{schedule2['member']} → *{member1}*"
                }
            ]
        },
        {
            'type': 'divider'
        },
        {
            'type': 'context',
            'elements': [
                {
                    'type': 'mrkdwn',
                    'text': f"_변경 시각: {get_kst_now().strftime('%Y-%m-%d %H:%M:%S KST')}_"
                }
            ]
        }
    ]

    return {
        'response_type': 'in_channel',
        'blocks': blocks
    }

def send_delayed_response(response_url, member1, member2, today_str):
    """
    짧은 지연 후 실제 처리를 수행하고 response_url로 결과 전송
    이 함수는 즉시 반환되고, 내부에서 별도로 처리
    """
    try:
        # 약간의 지연을 주어 메인 응답이 먼저 전송되도록 함
        time.sleep(1.5)

        print(f"Starting swap process for {member1} and {member2}")

        # 각 멤버의 가장 가까운 미래 스케줄 조회
        schedule1 = get_nearest_future_schedule(member1, today_str)
        schedule2 = get_nearest_future_schedule(member2, today_str)

        # 스케줄 존재 여부 확인
        if not schedule1:
            error_response = format_slack_response(
                False, member1, member2, None, None,
                f"'{member1}'의 향후 온콜 일정을 찾을 수 없습니다."
            )
            print(f"Schedule not found for {member1}, sending error response")
            result = requests.post(response_url, json=error_response, timeout=10)
            print(f"Response sent, status code: {result.status_code}")
            return

        if not schedule2:
            error_response = format_slack_response(
                False, member1, member2, None, None,
                f"'{member2}'의 향후 온콜 일정을 찾을 수 없습니다."
            )
            print(f"Schedule not found for {member2}, sending error response")
            result = requests.post(response_url, json=error_response, timeout=10)
            print(f"Response sent, status code: {result.status_code}")
            return

        # 원본 스케줄 정보 저장 (응답 메시지용)
        original_schedule1 = {
            'id': schedule1['id'],
            'date': schedule1['date'],
            'member': schedule1['member']
        }
        original_schedule2 = {
            'id': schedule2['id'],
            'date': schedule2['date'],
            'member': schedule2['member']
        }

        print(f"Found schedules - {member1}: {schedule1['date']}, {member2}: {schedule2['date']}")

        # 스케줄 교체
        success = swap_schedules(schedule1, schedule2)
        print(f"Swap result: {success}")

        # 응답 생성
        slack_response = format_slack_response(
            success, member1, member2,
            original_schedule1, original_schedule2,
            "데이터베이스 업데이트 중 오류가 발생했습니다." if not success else None
        )

        # response_url로 결과 전송
        print(f"Sending result to response_url")
        result = requests.post(response_url, json=slack_response, timeout=10)
        print(f"Response sent successfully, status code: {result.status_code}")

    except Exception as e:
        print(f"Error in background processing: {e}")
        import traceback
        traceback.print_exc()

        error_response = {
            'response_type': 'in_channel',
            'text': f'⚠️ 오류가 발생했습니다: {str(e)}'
        }

        try:
            requests.post(response_url, json=error_response, timeout=10)
            print(f"Error response sent")
        except Exception as req_error:
            print(f"Failed to send error response: {req_error}")

class handler(BaseHTTPRequestHandler):
    """Vercel Serverless Function 핸들러"""

    def do_GET(self):
        """GET 요청 처리 (테스트용)"""
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.end_headers()

        response = {
            'message': 'Swap Oncall Webhook is running!',
            'usage': "This endpoint is designed for Slack slash command '/온콜바꿔'"
        }

        self.wfile.write(json.dumps(response, ensure_ascii=False).encode('utf-8'))

    def do_POST(self):
        """POST 요청 처리 (Slack slash command)"""
        executor = None
        try:
            # POST 데이터 읽기
            content_length = int(self.headers.get('Content-Length', 0))
            post_data = self.rfile.read(content_length).decode('utf-8')

            # URL-encoded 데이터 파싱
            params = parse_qs(post_data)

            # 명령어 텍스트 추출 (예: "엔도 로쿤")
            command_text = params.get('text', [''])[0]

            # response_url 추출 (백그라운드 작업 결과를 보낼 URL)
            response_url = params.get('response_url', [''])[0]

            print(f"Received command: {command_text}")
            print(f"Response URL: {response_url}")

            # 멤버 이름 파싱
            members = parse_command_text(command_text)

            if not members:
                error_response = format_slack_response(
                    False, None, None, None, None,
                    "사용법: /온콜바꿔 [멤버1] [멤버2]\n예: /온콜바꿔 엔도 로쿤"
                )
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps(error_response, ensure_ascii=False).encode('utf-8'))
                return

            member1, member2 = members

            # 현재 날짜 가져오기
            today = get_kst_now()
            today_str = format_date(today)

            # ThreadPoolExecutor를 사용하여 백그라운드 작업 시작
            executor = ThreadPoolExecutor(max_workers=1)
            future = executor.submit(send_delayed_response, response_url, member1, member2, today_str)

            print(f"Background task submitted")

            # 즉시 200 응답 반환 (Slack 3초 타임아웃 방지)
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()

            immediate_response = {
                'response_type': 'in_channel',
                'text': f'⏳ {member1}와 {member2}의 온콜 일정을 변경하고 있습니다...'
            }
            self.wfile.write(json.dumps(immediate_response, ensure_ascii=False).encode('utf-8'))

            print(f"Immediate response sent")

            # future가 완료될 때까지 기다림 (최대 10초)
            # 이렇게 하면 serverless function이 종료되기 전에 작업이 완료됨
            try:
                future.result(timeout=10)
                print(f"Background task completed")
            except Exception as e:
                print(f"Background task error: {e}")

        except Exception as e:
            print(f"Error in handler: {e}")
            import traceback
            traceback.print_exc()

            # 에러 응답
            self.send_response(500)
            self.send_header('Content-type', 'application/json')
            self.end_headers()

            error_response = {
                'response_type': 'ephemeral',
                'text': f'⚠️ 오류가 발생했습니다: {str(e)}'
            }

            self.wfile.write(json.dumps(error_response, ensure_ascii=False).encode('utf-8'))

        finally:
            # Executor 정리
            if executor:
                executor.shutdown(wait=False)
