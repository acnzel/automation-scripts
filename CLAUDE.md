# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository Overview

This is a collection of automation scripts for monitoring and notification purposes. The scripts run on GitHub Actions schedules and integrate with Supabase for data storage and Slack for notifications.

## Project Structure

```
automation/
├── app_review_scraper.py          # Scrapes app reviews from Google Play and App Store
├── plab_oncall_reminder.py        # Manages on-call rotation schedule and sends reminders
├── dcinside_plabgallery_scraper.py # Scrapes DCInside gallery posts
└── longblack_today_article_scraper.py # Fetches daily Longblack articles
```

## Environment Setup

### Installing Dependencies

```bash
pip install -r requirements.txt
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

Each script can be run directly:

```bash
python automation/app_review_scraper.py
python automation/plab_oncall_reminder.py
python automation/dcinside_plabgallery_scraper.py
python automation/longblack_today_article_scraper.py
```

## Architecture

### Common Patterns

All scripts follow a similar architecture:

1. **Data Source**: Fetch data from external sources (Google Play API, App Store RSS, web scraping)
2. **Deduplication**: Check Supabase to avoid processing duplicate entries
3. **Storage**: Save new entries to Supabase tables
4. **Notification**: Send formatted messages to Slack webhooks

### Script Details

#### app_review_scraper.py
- **Purpose**: Monitors app reviews across multiple platforms (Google Play, App Store)
- **Key Class**: `AppReviewScraper` - handles scraping for a single app
- **Supabase Tables**: `plab_review`, `manager_review`, `iamground_review`, `puzzle_review`, `letsgoale_review`, `matchup_review`
- **Configuration**: `APPS` dictionary defines all monitored applications

#### plab_oncall_reminder.py
- **Purpose**: Manages on-call rotation for weekends/holidays and sends reminders
- **Key Functions**:
  - `schedule_monthly_oncall()`: Auto-generates next month's schedule when within 30 days
  - `send_slack_reminder()`: Sends on-call notifications
  - `update_channel_topic()`: Updates Slack channel topic with current on-call info
- **Supabase Table**: `oncall_rotation`
- **Schedule Logic**: Assigns on-call duties only for weekends and holidays in rotation
- **Timezone**: All operations use Asia/Seoul (KST)
- **Holidays**: Hardcoded list for 2025-2026

#### dcinside_plabgallery_scraper.py
- **Purpose**: Scrapes new posts from DCInside gallery and notifies via Slack
- **Key Functions**:
  - `get_posts()`: Fetches post list from gallery
  - `get_post_details()`: Fetches full post content including title, author, content
  - `normalize_to_date_str()`: Handles various date formats from DCInside
- **Supabase Table**: `dc_posts`
- **Rate Limiting**: 1 second delay between post detail fetches

#### longblack_today_article_scraper.py
- **Purpose**: Fetches daily featured article from Longblack website
- **Supabase Table**: `longblack_today_article`

### GitHub Actions Workflows

Scripts run on automated schedules:

- **app_review_scraper.py**: Daily at 10:30 AM KST (`30 1 * * *` UTC)
- **plab_oncall_reminder.py**: Daily at 09:40 AM KST (`40 0 * * *` UTC)
- **dcinside_plabgallery_scraper.py**: Every 3 hours (`0 */3 * * *` UTC)

All workflows can be triggered manually via `workflow_dispatch`.

## Modifying Scripts

### Adding a New App to Review Scraper

Edit the `APPS` dictionary in `app_review_scraper.py`:

```python
"new_app": {
    "app_name": "App Display Name",
    "table_name": "supabase_table_name",
    "slack_webhook_url": os.getenv("NEW_APP_SLACK_WEBHOOK_URL"),
    "google_package_name": "com.package.name",
    "apple_app_id": 1234567890,
    "count": 20
}
```

### Adding Team Members to On-Call Rotation

Edit the `TEAM_MEMBERS` dictionary in `plab_oncall_reminder.py`:

```python
"닉네임": {
    "id": "SLACK_USER_ID",
    "phone": "010-XXXX-XXXX"
}
```

### Adding Holidays

Add dates to the `HOLIDAYS` list in `plab_oncall_reminder.py` in `YYYY-MM-DD` format.

## Database Schema Notes

- **Review tables**: `platform_review_id`, `platform_type`, `user_name`, `rating`, `review`, `created_at`
- **oncall_rotation**: `id`, `member`, `date`
- **dc_posts**: `id`, `post_id`, `title`, `url`, `author`, `date`, `content`, `created_at`
- **longblack_today_article**: `id`, `url`, `created_at`

## Korean Language

This codebase primarily serves Korean users. Comments and strings may be in Korean. Slack messages are formatted in Korean.
