## Bug 1: Duplicate jobs instead of status updates

- **Bug**: Same job (same company + title) added as a new row when its status changes, instead of updating the existing row.
- **Root Cause**: Deduplication relied solely on `thread_id` matching and AI-based `find_matching_job()`. Different emails about the same application (e.g., confirmation vs rejection) have different thread IDs, so the thread-based check missed them. The AI match was only attempted when `is_status_update` was true.
- **Fix**: Added a local `_dedup_key(company, job_title)` function that normalises company+title (lowercase, stripped) and checks all existing rows before adding. This runs unconditionally, not just when `is_status_update` is flagged. When a match is found, `update_status()` is called with the newer status, the email date as `updated_date`, and any better location/description values. The `update_status()` method in `excel_manager.py` was extended to accept optional `updated_date`, `location`, and `description` parameters.
- **Files Changed**: `main.py`, `excel_manager.py`

## Bug 2: Email date range goes beyond 2025

- **Bug**: `--full` mode scanned all-time email history, wasting tokens and time on pre-2025 emails.
- **Root Cause**: `--full` passed an empty `date_filter` string, which meant no Gmail date constraint.
- **Fix**: Added `MIN_DATE_FILTER = 'after:2025/01/01'` constant and used it as the date filter for `--full` mode instead of an empty string.
- **Files Changed**: `main.py`

## Bug 3: Indeed "Unknown Company"

- **Bug**: Jobs applied via Indeed showed "Unknown" as the company name because the AI didn't extract the hiring company from Indeed's email format.
- **Root Cause**: The AI prompt lacked specific guidance for Indeed email patterns where the company name is embedded in phrases like "Your application was sent to [Company]".
- **Fix**: Added explicit Indeed-specific extraction patterns to the AI prompt in `ai_extractor.py`, and a directive to never return "Indeed" or "Unknown" when the actual company name appears in the email.
- **Files Changed**: `ai_extractor.py`

## Bug 4: University/academic applications not filtered

- **Bug**: University/academic application emails (admissions, scholarships, etc.) were being processed as job applications.
- **Root Cause**: No filtering existed to distinguish academic applications from job applications.
- **Fix**: Added `_ACADEMIC_RE` regex pattern and `_is_academic_email()` function in `main.py` that checks subject + body for academic-specific phrases (e.g., "university admission", "scholarship application", "PhD application"). Matching emails are skipped before the AI analysis step.
- **Files Changed**: `main.py`
