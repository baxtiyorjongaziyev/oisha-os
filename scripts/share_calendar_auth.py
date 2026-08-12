import os
import sys
import pickle
import logging
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def share_calendar():
    scopes = ["https://www.googleapis.com/auth/calendar"]
    creds = None
    token_path = "data/token.pickle"
    creds_json = "data/credentials.json"

    if os.path.exists(token_path):
        try:
            with open(token_path, "rb") as token:
                creds = pickle.load(token)
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
        except Exception as e:
            logger.error(f"Token refresh failed, will re-auth: {e}")
            creds = None

    if not creds or not creds.valid:
        if not os.path.exists(creds_json):
            logger.error(f"Missing {creds_json}")
            return
        print("Brovseringizda Google avtorizatsiyasi ochilmoqda...")
        flow = InstalledAppFlow.from_client_secrets_file(creds_json, scopes)
        creds = flow.run_local_server(port=0)
        with open(token_path, "wb") as token:
            pickle.dump(creds, token)

    service = build("calendar", "v3", credentials=creds)

    rule = {
        'scope': {
            'type': 'user',
            'value': 'xayrullayevna006@gmail.com',
        },
        'role': 'writer'
    }

    try:
        created_rule = service.acl().insert(calendarId='primary', body=rule).execute()
        print(f"MUVAFFAQIYATLI: Kalendar xayrullayevna006@gmail.com manziliga ulashildi. (Rule ID: {created_rule['id']})")
    except Exception as e:
        print(f"XATOLIK: {e}")

if __name__ == "__main__":
    share_calendar()
