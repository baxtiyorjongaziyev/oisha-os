import os
import sys
import pickle
import logging
from google.oauth2.service_account import Credentials as ServiceAccountCredentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def share_calendar():
    # Kengroq scope kerak
    scopes = ["https://www.googleapis.com/auth/calendar"]
    creds = None

    token_path = "data/token.pickle"
    if os.path.exists(token_path):
        try:
            with open(token_path, "rb") as token:
                creds = pickle.load(token)
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
                with open(token_path, "wb") as token:
                    pickle.dump(creds, token)
            logger.info("Loaded credentials from data/token.pickle")
        except Exception as e:
            logger.error(f"Token error: {e}")
            creds = None

    if not creds:
        credentials_path = "data/service_account.json"
        if os.path.exists(credentials_path):
            creds = ServiceAccountCredentials.from_service_account_file(
                credentials_path, scopes=scopes
            )
            logger.info("Loaded credentials from data/service_account.json")
        else:
            logger.error("No credentials found.")
            return

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
        logger.info(f"Successfully shared calendar. Rule ID: {created_rule['id']}")
    except Exception as e:
        logger.error(f"Error sharing calendar: {e}")

if __name__ == "__main__":
    share_calendar()
