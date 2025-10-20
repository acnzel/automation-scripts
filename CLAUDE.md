# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository Overview

This is a collection of automation scripts for monitoring and notification purposes. The scripts run as scheduled tasks and integrate with Supabase for data storage and Slack for notifications. The repository includes both Python automation scripts and a Node.js serverless function for Slack slash commands.

## Project Structure

```
automation-scripts/
├── automation/
│   ├── app_review_scraper.py          # Scrapes app reviews from Google Play and App Store
│   ├── plab_oncall_reminder.py        # Manages on-call rotation schedule and sends reminders
│   ├── dcinside_plabgallery_scraper.py # Scrapes DCInside gallery posts
│   └── longblack_today_article_scraper.py # Fetches daily Longblack articles
├── api/
│   └── oncall.js                      # Vercel serverless function for Slack /온콜리스트 command
├── requirements.txt                   # Python dependencies
├── package.json                       # Node.js dependencies
├── vercel.json                        # Vercel deployment configuration
└── VERCEL_SETUP.md                   # Detailed Vercel deployment guide
```

## Environment Setup

### Python Environment

```bash
# Install Python dependencies
pip install -r requirements.txt
```

### Node.js Environment (for Vercel API)

```bash
# Install Node.js dependencies
npm install
```

### Required Environment Variables

All scripts require a `.env` file with the following variables:

```
SUPABASE_URL=
SUPABASE_KEY=
```

Script-specific variables:
- **app_review_scraper.py**: `PLAB_SLACK_WEBHOOK_URL`, `MANAGER_SLACK_WEBHOOK_URL`, `IAMGROUND_SLACK_WEBHOOK_URL`, `PUZZLE_SLACK_WEBHOOK_URL`, `LETSGOALE_SLACK_WEBHOOK_URL`, `MATCHUP_SLACK_WEBHOOK_URL`
- **plab_oncall_reminder.py**: `DEV_REQUEST_SLACK_WEBHOOK_URL`, `DEV_REQUEST_SLACK_CHANNEL_ID`, `SLACK_BOT_TOKEN`
- **dcinside_plabgallery_scraper.py**: `DCINSIDE_SLACK_WEBHOOK_URL`
- **longblack_today_article_scraper.py**: `DEV_ARTICLE_SLACK_WEBHOOK_URL`

## Running Scripts

### Python Scripts

Each script can be run directly:

```bash
python automation/app_review_scraper.py
python automation/plab_oncall_reminder.py
python automation/dcinside_plabgallery_scraper.py
python automation/longblack_today_article_scraper.py
```

### Vercel API (Local Development)

```bash
# Start local development server
npm run dev

# Test the oncall endpoint
curl -X POST http://localhost:3000/api/oncall \
  -H "Content-Type: application/x-www-form-urlencoded"
```

### Vercel Deployment

```bash
# Deploy to production
vercel --prod
```

See `VERCEL_SETUP.md` for detailed deployment instructions.

## Architecture

### Common Patterns (Python Scripts)

All Python scripts follow a similar architecture:

1. **Data Source**: Fetch data from external sources (Google Play API, App Store RSS, web scraping)
2. **Deduplication**: Check Supabase to avoid processing duplicate entries
3. **Storage**: Save new entries to Supabase tables
4. **Notification**: Send formatted messages to Slack webhooks

### Script Details

#### app_review_scraper.py
- **Purpose**: Monitors app reviews across multiple platforms (Google Play, App Store)
- **Key Class**: `AppReviewScraper` - handles scraping for a single app
  - `review_exists()`: Checks if review already exists in database
  - `save_review_to_supabase()`: Saves new review to database
  - `send_to_slack()`: Sends formatted review notification
  - `process_google_play()`: Fetches reviews from Google Play using google-play-scraper
  - `process_app_store()`: Fetches reviews from App Store RSS feed
- **Supabase Tables**: `plab_review`, `manager_review`, `iamground_review`, `puzzle_review`, `letsgoale_review`, `matchup_review`
- **Configuration**: `APPS` dictionary defines all monitored applications with package names and app IDs
- **Data Flow**: Main script iterates through APPS dictionary, instantiating AppReviewScraper for each app

#### plab_oncall_reminder.py
- **Purpose**: Manages on-call rotation for weekends/holidays and sends reminders
- **Key Functions**:
  - `schedule_monthly_oncall()`: Auto-generates next month's schedule when within 30 days of month end. Uses round-robin assignment from TEAM_MEMBERS
  - `send_slack_reminder()`: Sends on-call notifications with mention and phone number
  - `update_channel_topic()`: Updates Slack channel topic with current on-call info (clears topic on weekdays)
  - `get_current_oncall()`: Retrieves today's on-call person
  - `get_last_oncall_member()`: Gets last assigned member for rotation continuity
  - `should_send_reminder()`: Determines if today is weekend or holiday
- **Supabase Table**: `oncall_rotation` (columns: id, member, date)
- **Schedule Logic**: Assigns on-call duties only for weekends and holidays in rotation, skipping weekdays
- **Timezone**: All operations use Asia/Seoul (KST) via pytz
- **Holidays**: Hardcoded list for 2025-2026 in YYYY-MM-DD format
- **Team Management**: TEAM_MEMBERS dictionary contains Slack user IDs and phone numbers

#### dcinside_plabgallery_scraper.py
- **Purpose**: Scrapes new posts from DCInside gallery and notifies via Slack
- **Key Functions**:
  - `get_posts()`: Fetches post list from gallery main page, iterates through each post to get details
  - `get_post_details()`: Fetches full post content from detail page including title, author, content, date
  - `normalize_to_date_str()`: Handles various date formats from DCInside (HH:MM for today, MM.DD for current year, YYYY.MM.DD for full date)
  - `normalize_post_id()`: Cleans post ID by removing query parameters and non-numeric characters
  - `is_post_exists()`: Checks if post already exists in database
  - `save_post()`: Upserts post to database
  - `send_to_slack()`: Sends formatted post notification with preview (truncated to 200 chars)
- **Supabase Table**: `dc_posts` (columns: id, post_id, title, url, author, date, content, created_at)
- **Rate Limiting**: 1 second delay between post detail fetches to avoid overwhelming the server
- **Web Scraping**: Uses BeautifulSoup with multiple selector strategies for robustness

#### longblack_today_article_scraper.py
- **Purpose**: Fetches daily featured article from Longblack website
- **Key Functions**:
  - `fetch_today_note_link()`: Scrapes Longblack homepage for today's article link
  - `save_to_supabase()`: Saves article URL with deduplication check
  - `notify_slack()`: Sends article link to Slack
- **Supabase Table**: `longblack_today_article` (columns: id, url, created_at)
- **Timezone**: Uses Asia/Seoul (KST)

#### api/oncall.js (Vercel Serverless Function)
- **Purpose**: Provides Slack slash command `/온콜리스트` to query on-call schedule
- **Key Functions**:
  - `getKSTNow()`: Returns current time in KST (UTC+9)
  - `formatDate()`: Converts Date to YYYY-MM-DD format
  - `getOncallSchedule()`: Queries Supabase for next 30 days of on-call assignments
  - `formatSlackMessage()`: Formats schedule data using Slack Block Kit with month grouping
  - `handler()`: Main serverless function handler (POST for Slack, GET returns test message)
- **Technology**: Node.js with @supabase/supabase-js
- **Response Format**: Slack Block Kit with in_channel visibility, grouped by month with Korean weekday labels
- **Deployment**: Vercel serverless function at `/api/oncall`

## Deployment

### GitHub Actions (Python Scripts)

Scripts run on automated schedules:

- **app_review_scraper.py**: Daily at 10:30 AM KST (`30 1 * * *` UTC)
- **plab_oncall_reminder.py**: Daily at 09:40 AM KST (`40 0 * * *` UTC)
- **dcinside_plabgallery_scraper.py**: Every 3 hours (`0 */3 * * *` UTC)

All workflows support manual trigger via `workflow_dispatch`.

### Vercel (API Endpoint)

The `/api/oncall` endpoint is deployed as a serverless function on Vercel. See `VERCEL_SETUP.md` for complete deployment instructions including:
- Environment variable configuration
- Slack slash command setup
- Local development and testing

## Modifying Scripts

### Adding a New App to Review Scraper

Edit the `APPS` dictionary in `app_review_scraper.py`:

```python
"new_app": {
    "app_name": "App Display Name",
    "table_name": "supabase_table_name",
    "slack_webhook_url": os.getenv("NEW_APP_SLACK_WEBHOOK_URL"),
    "google_package_name": "com.package.name",  # Required for Google Play
    "apple_app_id": 1234567890,                  # Required for App Store
    "count": 20                                  # Number of reviews to fetch
}
```

### Adding Team Members to On-Call Rotation

Edit the `TEAM_MEMBERS` dictionary in `plab_oncall_reminder.py`:

```python
"닉네임": {
    "id": "SLACK_USER_ID",      # Get from Slack member profile
    "phone": "010-XXXX-XXXX"
}
```

### Adding Holidays

Add dates to the `HOLIDAYS` list in `plab_oncall_reminder.py` in `YYYY-MM-DD` format:

```python
HOLIDAYS = [
    "2025-01-01",  # New Year's Day
    # ... add more holidays
]
```

## Database Schema

- **Review tables** (`*_review`): `platform_review_id` (text), `platform_type` (text), `user_name` (text), `rating` (int), `review` (text), `created_at` (timestamp)
- **oncall_rotation**: `id` (int), `member` (text), `date` (text/date in YYYY-MM-DD)
- **dc_posts**: `id` (int), `post_id` (int, unique), `title` (text), `url` (text), `author` (text), `date` (text), `content` (text), `created_at` (timestamp)
- **longblack_today_article**: `id` (int), `url` (text, unique), `created_at` (text/date)

## Korean Language

This codebase primarily serves Korean users. Comments and strings may be in Korean. Slack messages are formatted in Korean. When modifying user-facing messages, maintain Korean language for consistency.

## Common Development Patterns

### Deduplication Strategy
All scripts check for existing entries before saving to avoid duplicates:
- Reviews: Check by `platform_review_id` + `platform_type`
- DC Posts: Check by `post_id` (normalized)
- Longblack: Check by `url`
- Oncall: Upsert is not used; schedule generation checks for existing month

### Error Handling
Scripts use try-except blocks and continue processing remaining items on individual failures. Errors are logged to stdout/stderr for GitHub Actions visibility.

### Timezone Handling
All datetime operations use KST (Asia/Seoul) via pytz to ensure consistent scheduling regardless of server timezone.
