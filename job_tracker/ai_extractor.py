import json
import time
import anthropic


_OVERLOAD_DELAYS = [10, 20, 40, 60, 90]  # seconds between retries on 529


class AIExtractor:
    def __init__(self, api_key=None):
        # max_retries handles transient network errors; overload retries handled manually
        self.client = anthropic.Anthropic(api_key=api_key, max_retries=2)
        self.model = 'claude-sonnet-4-6'

    def _create_with_retry(self, **kwargs):
        """Call messages.create with long-backoff retries for 529 overload errors."""
        for attempt, delay in enumerate(_OVERLOAD_DELAYS, start=1):
            try:
                return self.client.messages.create(**kwargs)
            except anthropic.APIStatusError as e:
                if e.status_code != 529:
                    raise
                print(f'  ! API overloaded (attempt {attempt}/{len(_OVERLOAD_DELAYS)}), '
                      f'retrying in {delay}s...')
                time.sleep(delay)
        # Final attempt — let any exception propagate
        return self.client.messages.create(**kwargs)

    def analyze_email(self, subject, sender, body, date):
        """
        Analyze a single email. Returns a dict or None.

        Returned fields:
          is_job_related   bool
          company          str | null
          job_title        str | null
          location         str | null
          description      str | null   (1-2 sentence summary)
          status           "Applied" | "Interview Scheduled" | "Offer Received"
                           | "Rejected" | "Withdrawn" | null
          is_status_update bool  (True = updates an existing app, False = new)
        """
        prompt = f"""You are a job-application tracker. Analyze the email below and extract
structured data about any job application it refers to.

--- EMAIL ---
Subject : {subject}
From    : {sender}
Date    : {date}
Body (first 3000 chars):
{body[:3000]}
--- END EMAIL ---

Return ONLY a valid JSON object (no markdown, no prose) with these exact keys:
{{
  "is_job_related": <true|false>,
  "company": <string or null>,
  "job_title": <string or null>,
  "location": <string or null>,
  "description": <1-2 sentence job description or null>,
  "status": <"Applied"|"Interview Scheduled"|"Offer Received"|"Rejected"|"Withdrawn"|null>,
  "is_status_update": <true|false>
}}

Rules:
- is_job_related must be true only if the email is clearly about a job application.
- company: look everywhere — subject line, email body, sender domain, and "From" name.
  For job-board emails (Indeed, LinkedIn, Glassdoor, ZipRecruiter, etc.) the hiring
  company is usually mentioned in the subject or body, NOT the job board itself.
  Use the hiring company name, not the job board name.
- job_title: extract the exact role title from the subject or body.
- location: look for city/state, country, or "Remote" in the body. Use null if absent.
- status "Applied" = confirmation of submission; "Interview Scheduled" = invitation
  or confirmation of an interview; "Offer Received" = job offer extended;
  "Rejected" = rejection/not moving forward; "Withdrawn" = candidate withdrew.
- is_status_update = true if the email changes the status of an EXISTING application
  (interview invite, rejection, offer) rather than confirming a fresh new submission."""

        response = self._create_with_retry(
            model=self.model,
            max_tokens=600,
            messages=[{'role': 'user', 'content': prompt}]
        )
        try:
            return json.loads(response.content[0].text.strip())
        except (json.JSONDecodeError, IndexError):
            return None

    def find_matching_job(self, extracted, existing_jobs):
        """
        Given extracted email data and a list of tracked jobs, return the
        0-based index of the matching job, or None.
        """
        if not existing_jobs:
            return None

        jobs_list = '\n'.join(
            f"{i}. {j['company']} | {j['job_title']} | {j['location']}"
            for i, j in enumerate(existing_jobs)
        )

        prompt = f"""I need to match a job-related email to an existing tracked application.

Email company : {extracted.get('company')}
Email title   : {extracted.get('job_title')}

Tracked applications (index | company | title | location):
{jobs_list}

Return ONLY valid JSON: {{"match_index": <integer index or null>}}
Match on company name similarity AND job title similarity.
Use null if no clear match exists."""

        response = self._create_with_retry(
            model=self.model,
            max_tokens=80,
            messages=[{'role': 'user', 'content': prompt}]
        )
        try:
            result = json.loads(response.content[0].text.strip())
            return result.get('match_index')
        except Exception:
            return None