"""
Job Application Tracker
-----------------------
Scans Gmail for job-application emails, extracts structured data using
Claude AI, and maintains an Excel spreadsheet with status updates.

Usage:
    python main.py              # loop mode — scans current month every SCAN_INTERVAL_MINUTES
    python main.py --once       # single scan, current month only (fast rescan)
    python main.py --full       # single scan, all time (use for first-time historical import)
"""

import os
import sys
import time
from datetime import datetime

import schedule
from dotenv import load_dotenv

from ai_extractor import AIExtractor
from excel_manager import ExcelManager
from gmail_client import GmailClient

load_dotenv()

# Comprehensive queries covering all common job-application email patterns.
# Gmail search syntax: https://support.google.com/mail/answer/7190
# {DATE} is replaced at runtime with e.g. "after:2026/03/01" or "" for full history.
SEARCH_QUERIES = [
    # Application confirmations — broad subject match
    'subject:("application") (received OR submitted OR confirmed OR confirmation) -from:me {DATE}',
    'subject:("your application") -from:me {DATE}',
    'subject:("you applied") -from:me {DATE}',
    'subject:("application for") -from:me {DATE}',
    # "Thank you for applying/interest" variants
    '(subject:("thank you for applying") OR subject:("thanks for applying") OR subject:("thank you for your interest")) {DATE}',
    # Major ATS platforms (confirmation emails come from these domains)
    'from:(workday.com OR greenhouse.io OR lever.co OR ashbyhq.com OR icims.com OR taleo.net OR smartrecruiters.com OR jobvite.com OR bamboohr.com OR rippling.com) {DATE}',
    # Major job boards
    'from:(linkedin.com OR indeed.com OR glassdoor.com OR ziprecruiter.com OR wellfound.com OR dice.com) {DATE}',
    # Interview invites — many subject patterns
    '(subject:("interview") OR subject:("speak with you") OR subject:("chat with you") OR subject:("call with you") OR subject:("meet with you")) (application OR role OR position OR team OR opportunity) -from:me {DATE}',
    # Job offers
    '(subject:("offer letter") OR subject:("job offer") OR subject:("offer of employment") OR subject:("pleased to offer") OR subject:("excited to offer")) -from:me {DATE}',
    # Rejections — all common phrasings
    '(subject:("unfortunately") OR subject:("not selected") OR subject:("not be moving") OR subject:("not moving forward") OR subject:("other direction") OR subject:("other candidates") OR subject:("filled the position") OR subject:("position has been filled") OR subject:("decided to move")) -from:me {DATE}',
    # Status / next-steps updates
    '(subject:("application update") OR subject:("application status") OR subject:("update on your application") OR subject:("next steps")) (application OR interview OR position OR role) -from:me {DATE}',
]


def _now():
    return datetime.now().strftime('%Y-%m-%d %H:%M:%S')


def _current_month_filter():
    """Returns a Gmail date filter string for the start of the current month."""
    today = datetime.now()
    return f'after:{today.year}/{today.month:02d}/01'


def scan_emails(gmail: GmailClient, extractor: AIExtractor, excel: ExcelManager,
                date_filter: str = ''):
    scope = f'current month ({date_filter})' if date_filter else 'all time'
    print(f'\n[{_now()}] Starting email scan ({scope})...')
    new_count = update_count = skip_count = 0
    seen_threads: set[str] = set()

    for query_template in SEARCH_QUERIES:
        query = query_template.replace('{DATE}', date_filter).strip()
        messages = gmail.search_emails(query, max_results=100)

        for msg_ref in messages:
            try:
                message = gmail.get_email(msg_ref['id'])
            except Exception as e:
                print(f'  ! Error fetching {msg_ref["id"]}: {e}')
                continue

            thread_id = gmail.get_thread_id(message)

            # Skip threads we have already processed in this run or in the sheet
            if thread_id in seen_threads or excel.has_thread_id(thread_id):
                seen_threads.add(thread_id)
                skip_count += 1
                continue
            seen_threads.add(thread_id)

            subject = gmail.get_subject(message)
            sender  = gmail.get_sender(message)
            date    = gmail.get_date(message)
            body    = gmail.get_body(message)

            print(f'  ? Analyzing: {subject[:70]}')
            time.sleep(0.5)  # avoid burst-triggering overload

            result = extractor.analyze_email(subject, sender, body, date)
            if not result or not result.get('is_job_related'):
                continue

            company     = result.get('company')    or 'Unknown Company'
            job_title   = result.get('job_title')  or 'Unknown Role'
            location    = result.get('location')   or 'Unknown'
            description = result.get('description') or ''
            status      = result.get('status')     or 'Applied'

            existing_jobs = excel.get_all_jobs()

            # If this email updates an existing application, find and update it
            if result.get('is_status_update') and existing_jobs:
                match_idx = extractor.find_matching_job(result, existing_jobs)
                if match_idx is not None:
                    excel.update_status(match_idx, new_status=status, thread_id=thread_id)
                    old = existing_jobs[match_idx]
                    print(f'  ↑ Updated : {old["company"]} — {old["job_title"]} → {status}')
                    update_count += 1
                    continue

            # Otherwise add a new row
            excel.add_job(
                company=company,
                job_title=job_title,
                location=location,
                description=description,
                status=status,
                applied_date=date,
                thread_id=thread_id,
            )
            new_count += 1

    print(f'[{_now()}] Scan complete — {new_count} added, {update_count} updated, {skip_count} skipped.\n')


def build_clients():
    gmail = GmailClient(
        credentials_path=os.getenv('GMAIL_CREDENTIALS_PATH', 'credentials.json'),
        token_path=os.getenv('GMAIL_TOKEN_PATH', 'token.pickle'),
    )
    extractor = AIExtractor(api_key=os.getenv('ANTHROPIC_API_KEY'))
    excel = ExcelManager(filepath=os.getenv('EXCEL_PATH', 'job_applications.xlsx'))
    return gmail, extractor, excel


def main():
    full_history = '--full' in sys.argv
    interval = int(os.getenv('SCAN_INTERVAL_MINUTES', '60'))

    gmail, extractor, excel = build_clients()

    if full_history:
        # One-time deep scan over all history — intended for initial import
        scan_emails(gmail, extractor, excel, date_filter='')
        return

    # All other modes (--once or loop) only scan the current month
    date_filter = _current_month_filter()

    if '--once' in sys.argv:
        scan_emails(gmail, extractor, excel, date_filter=date_filter)
        return

    print(f'Job Tracker running. Scanning every {interval} min. Ctrl-C to stop.')
    scan_emails(gmail, extractor, excel, date_filter=date_filter)

    schedule.every(interval).minutes.do(
        scan_emails, gmail, extractor, excel, date_filter
    )
    while True:
        schedule.run_pending()
        time.sleep(30)


if __name__ == '__main__':
    main()
