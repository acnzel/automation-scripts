import os
import json
import datetime
from typing import List, Dict
from dotenv import load_dotenv
import requests
from supabase import create_client, Client
import pytz

load_dotenv(".env")

supabase: Client = create_client(
    os.getenv("SUPABASE_URL", ""),
    os.getenv("SUPABASE_KEY", "")
)

SLACK_WEBHOOK_URL = os.getenv("DEV_REQUEST_SLACK_WEBHOOK_URL", "")
SLACK_CHANNEL = os.getenv("DEV_REQUEST_SLACK_CHANNEL_ID", "")
SLACK_BOT_TOKEN = os.getenv("SLACK_BOT_TOKEN", "")
TEAM_MEMBERS = {
    "따오": {
        "id": "U03TC2CQEVD",
        "phone": "010-5150-3541"
    },
    "워즈": {
        "id": "U054RK2GKK8",
        "phone": "010-4575-3742"
    },
    "로쿤": {
        "id": "D08BFBKP73L",
        "phone": "010-5031-8756"
    },
    "정남": {
        "id": "D089WENUMHP",
        "phone": "010-8551-0833"
    },
    "엔도": {
        "id": "U071QDWFQNL",
        "phone": "010-9963-8774"
    },
    "루니": {
        "id": "D089KE84D2Q",
        "phone": "010-5021-2987"
    },
    "벨": {
        "id": "U031W1YGMN2",
        "phone": "010-2714-1537"
    },
    "맥국": {
        "id": "D089HDYHMUP",
        "phone": "010-7767-4733"
    },
    "히로": {
        "id": "D089P8FGV0B",
        "phone": "010-3314-7155"
    }, 
    "키커": {
        "id": "D08957CNAJJ",
        "phone": "010-4929-9449"
    }, 
}

# 2025-2026 Holidays (excluding weekends)
HOLIDAYS = [
    # 2025 Holidays
    "2025-01-01",  # New Year's Day (수요일)
    "2025-01-28",  # Lunar New Year (화요일)
    "2025-01-29",  # Lunar New Year (수요일)
    "2025-01-30",  # Lunar New Year (목요일)
    "2025-05-05",  # Children's Day (월요일)
    "2025-06-06",  # Memorial Day (금요일)
    "2025-08-15",  # Liberation Day (금요일)
    "2025-10-03",  # National Foundation Day (금요일)
    "2025-10-06",  # Chuseok (월요일)
    "2025-10-07",  # Chuseok (화요일)
    "2025-10-08",  # Chuseok (수요일)
    "2025-10-09",  # Hangeul Day (목요일)
    "2025-12-25",  # Christmas Day (목요일)
    
    # 2026 Holidays
    "2026-01-01",  # New Year's Day (목요일)
    "2026-02-16",  # Lunar New Year (월요일)
    "2026-02-17",  # Lunar New Year (화요일)
    "2026-02-18",  # Lunar New Year (수요일)
    "2026-03-02",  # 3.1 (화요일)
    "2026-05-05",  # Children's Day (화요일)
    "2026-05-25",  # Buddha's Birthday (금요일)
    "2026-08-17",  # 광복절 (월요일)
    "2026-09-24",  # Chuseok (목요일)
    "2026-09-25",  # Chuseok (금요일)
    "2026-10-05",  # 개천절 (금요일)
    "2026-10-09",  # Hangeul Day (금요일)
    "2026-12-25",  # Christmas Day (금요일)
]

def get_kst_now() -> datetime.datetime:
    """Get current time in KST."""
    kst = pytz.timezone('Asia/Seoul')
    return datetime.datetime.now(kst)

def get_current_oncall() -> str:
    """오늘 날짜의 온콜 담당자가 있으면 반환, 없으면 None 반환"""
    today = get_kst_now().strftime("%Y-%m-%d")
    try:
        response = supabase.table("oncall_rotation").select("*").eq("date", today).order("id").limit(1).execute()
        if response.data:
            return response.data[0]["member"]
        return None  # 오늘 온콜 담당자가 없으면 None 반환
    except Exception as e:
        print(f"Error getting current oncall: {e}")
        return None

def get_last_oncall_member() -> str:
    """오늘 이전까지 가장 마지막으로 온콜을 수행한 사람을 반환"""
    today = get_kst_now().strftime("%Y-%m-%d")
    try:
        response = supabase.table("oncall_rotation").select("*").lt("date", today).order("date", desc=True).limit(1).execute()
        if response.data:
            return response.data[0]["member"]
        return None
    except Exception as e:
        print(f"Error getting last oncall member: {e}")
        return None

def schedule_monthly_oncall() -> None:
    today = get_kst_now()

    try:
        # Get the last on-call date from the database
        response = supabase.table("oncall_rotation").select("date, member").order("date", desc=True).limit(1).execute()

        if not response.data:
            # No existing schedule, create for current month
            print("No existing on-call schedule found, creating schedule for current month")
            target_year = today.year
            target_month = today.month
            last_oncall_member = list(TEAM_MEMBERS.keys())[0]  # Start from first member
        else:
            last_oncall_date_str = response.data[0]["date"]
            last_oncall_member = response.data[0]["member"]
            last_oncall_date = datetime.datetime.strptime(last_oncall_date_str, "%Y-%m-%d")

            # Calculate days until the end of the last scheduled month
            days_until_end_of_month = (last_oncall_date.replace(day=28) + datetime.timedelta(days=4)).replace(day=1) - last_oncall_date

            print(f"Last on-call date: {last_oncall_date_str}, Member: {last_oncall_member}")
            print(f"Days until end of month: {days_until_end_of_month.days}")

            # If last on-call date is within 30 days from today, schedule next month
            if days_until_end_of_month.days <= 30:
                # Calculate next month
                if last_oncall_date.month == 12:
                    target_year = last_oncall_date.year + 1
                    target_month = 1
                else:
                    target_year = last_oncall_date.year
                    target_month = last_oncall_date.month + 1

                print(f"Last on-call date is within 30 days, scheduling for next month: {target_year}-{target_month:02d}")
            else:
                print(f"Last on-call date is more than 30 days away, no need to schedule yet")
                return

        # Get the member list and find the next member in rotation
        member_list = list(TEAM_MEMBERS.keys())
        current_index = member_list.index(last_oncall_member)
        # Start from the next member after the last assigned
        member_index = (current_index + 1) % len(member_list)

        # Get the number of days in the target month
        if target_month == 12:
            next_month = datetime.datetime(target_year + 1, 1, 1)
        else:
            next_month = datetime.datetime(target_year, target_month + 1, 1)

        last_day = (next_month - datetime.timedelta(days=1)).day

        # Check if schedule already exists for this month
        first_day = f"{target_year}-{target_month:02d}-01"
        last_day_str = f"{target_year}-{target_month:02d}-{last_day:02d}"

        existing_schedule = supabase.table("oncall_rotation").select("*").gte("date", first_day).lte("date", last_day_str).execute()

        if existing_schedule.data:
            print(f"Schedule already exists for {target_year}-{target_month:02d}, skipping")
            return

        # Create schedule for the entire month
        schedule_data = []

        for day in range(1, last_day + 1):
            date_str = f"{target_year}-{target_month:02d}-{day:02d}"

            # Skip weekends and holidays
            check_date = datetime.datetime(target_year, target_month, day)
            is_weekend = check_date.weekday() >= 5
            is_holiday = date_str in HOLIDAYS

            if is_weekend or is_holiday:
                # Assign on-call person for weekends/holidays
                member = member_list[member_index]
                schedule_data.append({
                    "member": member,
                    "date": date_str
                })
                # Move to next member for next assignment
                member_index = (member_index + 1) % len(member_list)

        # Insert all schedule data at once
        if schedule_data:
            supabase.table("oncall_rotation").insert(schedule_data).execute()
            print(f"Successfully created on-call schedule for {target_year}-{target_month:02d}: {len(schedule_data)} assignments")

            # Log the schedule
            for assignment in schedule_data:
                print(f"  {assignment['date']}: {assignment['member']}")
        else:
            print(f"No weekend/holiday assignments needed for {target_year}-{target_month:02d}")

    except Exception as e:
        print(f"Error creating monthly on-call schedule: {e}")

def should_send_reminder() -> bool:
    """Check if we should send a reminder today."""
    today = get_kst_now()
    
    # 주말인지 확인
    if today.weekday() >= 5:  # 5 is Saturday, 6 is Sunday
        return True
    
    # 공휴일인지 확인
    today_str = today.strftime("%Y-%m-%d")
    if today_str in HOLIDAYS:
        return True
    
    return False

def update_channel_topic(current_oncall: str) -> None:
    """Update the Slack channel topic with current on-call person's information."""
    if not SLACK_BOT_TOKEN:
        print("Warning: SLACK_BOT_TOKEN not set, skipping channel topic update")
        return

    # 주말이나 공휴일인지 확인
    today = get_kst_now()
    today_str = today.strftime("%Y-%m-%d")
    is_weekend = today.weekday() >= 5
    is_holiday = today_str in HOLIDAYS

    if not (is_weekend or is_holiday):
        # 주중에는 토픽 제거
        topic = ""
    else:
        # 주말이나 공휴일에는 온콜 담당자 정보 토픽 업데이트
        phone = TEAM_MEMBERS[current_oncall]['phone']
        topic = f"현재 온콜 담당자: {current_oncall} ({phone})"
    
    try:
        response = requests.post(
            "https://slack.com/api/conversations.setTopic",
            headers={
                "Authorization": f"Bearer {SLACK_BOT_TOKEN}",
                "Content-Type": "application/json"
            },
            json={
                "channel": SLACK_CHANNEL,
                "topic": topic
            }
        )
        
        if not response.json().get("ok"):
            print(f"Error updating channel topic: {response.json().get('error')}")
        else:
            if topic:
                print(f"Successfully updated channel topic to: {topic}")
            else:
                print("Successfully removed channel topic")
    except Exception as e:
        print(f"Exception while updating channel topic: {str(e)}")

def send_slack_reminder(current_oncall: str) -> None:
    """Send reminder to Slack channel."""
    if not should_send_reminder():
        print("Skipping reminder - not a weekend or holiday")
        return
    
    if not current_oncall:
        print("No on-call person assigned for today. Skipping Slack notification and topic update.")
        return
    today = get_kst_now()
    today_str = today.strftime("%Y-%m-%d")
    
    # 주말이나 공휴일인지 확인
    is_weekend = today.weekday() >= 5
    is_holiday = today_str in HOLIDAYS
    
    # 주말이나 공휴일인지 확인
    if is_weekend and is_holiday:
        day_type = "주말이자 공휴일"
    elif is_weekend:
        day_type = "주말"
    else:
        day_type = "공휴일"
    
    # 멘션 문자열 생성 및 연락처 가져오기
    mention = f"<@{TEAM_MEMBERS[current_oncall]['id']}>"
    phone = TEAM_MEMBERS[current_oncall]['phone']
    
    message = {
        "channel": SLACK_CHANNEL,
        "text": f"🚨 *On-Call 알리미* 🚨\n({today_str} {day_type}) 온콜 담당자 : {mention} / 연락처 : {phone}",
        "blocks": [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": "🚨 On-Call 알리미 🚨",
                    "emoji": True
                }
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"({today_str} {day_type}) 온콜 담당자 : {mention} / 연락처 : {phone}"
                }
            }
        ]
    }
    
    print(f"Attempting to send Slack message to channel: {SLACK_CHANNEL}")
    print(f"Webhook URL: {SLACK_WEBHOOK_URL[:20]}...")  # 보안을 위해 URL 처음 20자만 출력
    
    try:
        response = requests.post(
            SLACK_WEBHOOK_URL,
            data=json.dumps(message),
            headers={"Content-Type": "application/json"}
        )
        print(f"Slack API Response Status: {response.status_code}")
        print(f"Slack API Response Body: {response.text}")
        
        if response.status_code != 200:
            print(f"Error sending Slack message: {response.text}")
        else:
            print("Successfully sent Slack message")
            update_channel_topic(current_oncall)
    except Exception as e:
        print(f"Exception while sending Slack message: {str(e)}")
        print(f"Message that failed to send: {json.dumps(message, indent=2)}")

if __name__ == "__main__":
    print("Starting oncall reminder script...")
    print(f"Current time (KST): {get_kst_now().strftime('%Y-%m-%d %H:%M:%S %Z')}")
    
    # 매달 1월 1일에 온콜 담당자 정해주기
    schedule_monthly_oncall()
    
    # 온콜 담당자 업데이트
    current_oncall = get_current_oncall()
    
    # 주말이나 공휴일에만 멘션 걸기
    if should_send_reminder():
        send_slack_reminder(current_oncall)
    else:
        update_channel_topic(current_oncall)    
    print("Script execution completed.")
