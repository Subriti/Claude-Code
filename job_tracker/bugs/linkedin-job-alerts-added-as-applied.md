- **Bug**: LinkedIn job alert/suggestion emails are incorrectly added to the applied jobs Excel sheet even though the user never applied to those jobs.

- **Root Cause**: The AI prompt in `ai_extractor.py` only checked `is_job_related` which was true for both job alerts and actual application confirmations. There was no distinction between "this email mentions a job" and "the user actually applied to this job." The broad `from:(linkedin.com ...)` search query in `main.py` pulled in all LinkedIn emails including recommendation/alert emails, and nothing downstream filtered them out.

- **Fix**: Added a new `is_application_confirmed` field to the AI extraction prompt with explicit instructions and examples for when it should be true (application confirmations, interview invites, offers, rejections) vs false (job alerts, suggestions, recommendations). Added a code-level gate in `main.py` that skips any email where `is_application_confirmed` is not true, preventing job alerts from being added to the spreadsheet.

- **Files Changed**:
  - `job_tracker/ai_extractor.py` — Added `is_application_confirmed` field to the prompt with detailed true/false criteria
  - `job_tracker/main.py` — Added check to skip emails where `is_application_confirmed` is false
