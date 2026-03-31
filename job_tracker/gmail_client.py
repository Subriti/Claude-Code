import base64
import pickle
from email.utils import parsedate_to_datetime
from pathlib import Path

from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']


class GmailClient:
    def __init__(self, credentials_path='credentials.json', token_path='token.pickle'):
        self.credentials_path = credentials_path
        self.token_path = token_path
        self.service = self._authenticate()

    def _authenticate(self):
        creds = None
        token = Path(self.token_path)
        if token.exists():
            with open(token, 'rb') as f:
                creds = pickle.load(f)

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(
                    self.credentials_path, SCOPES)
                creds = flow.run_local_server(port=0)
            with open(token, 'wb') as f:
                pickle.dump(creds, f)

        return build('gmail', 'v1', credentials=creds)

    def search_emails(self, query, max_results=100):
        result = self.service.users().messages().list(
            userId='me', q=query, maxResults=max_results
        ).execute()
        return result.get('messages', [])

    def get_email(self, msg_id):
        return self.service.users().messages().get(
            userId='me', id=msg_id, format='full'
        ).execute()

    def get_thread_id(self, message):
        return message.get('threadId', '')

    def get_header(self, message, name):
        headers = message.get('payload', {}).get('headers', [])
        for h in headers:
            if h['name'].lower() == name.lower():
                return h['value']
        return ''

    def get_subject(self, message):
        return self.get_header(message, 'subject')

    def get_sender(self, message):
        return self.get_header(message, 'from')

    def get_date(self, message):
        raw = self.get_header(message, 'date')
        try:
            dt = parsedate_to_datetime(raw)
            return dt.strftime('%Y-%m-%d')
        except Exception:
            return ''

    def get_body(self, message):
        """Extract the best available plain text from an email."""
        payload = message.get('payload', {})

        def decode(data):
            return base64.urlsafe_b64decode(data + '==').decode('utf-8', errors='ignore')

        def extract(part):
            mime = part.get('mimeType', '')
            if mime == 'text/plain':
                data = part.get('body', {}).get('data', '')
                if data:
                    return decode(data)
            # Recurse into multipart
            for sub in part.get('parts', []):
                text = extract(sub)
                if text:
                    return text
            # Fallback: return HTML if no plain text found
            if mime == 'text/html':
                data = part.get('body', {}).get('data', '')
                if data:
                    return decode(data)
            return ''

        return extract(payload)
