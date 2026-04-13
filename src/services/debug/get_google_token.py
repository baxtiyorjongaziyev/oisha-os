
import os
import pickle
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request

# If modifying these SCOPES, delete the file token.pickle.
SCOPES = [
    "https://www.googleapis.com/auth/contacts",
    "https://www.googleapis.com/auth/directory.readonly",
    "https://www.googleapis.com/auth/calendar.events"
]

def main():
    """Shows basic usage of the People API.
    Lists the name of the first 10 connections.
    """
    creds = None
    # The file token.pickle stores the user's access and refresh tokens, and is
    # created automatically when the authorization flow completes for the first
    # time.
    if os.path.exists('token.pickle'):
        with open('token.pickle', 'rb') as token:
            creds = pickle.load(token)
    
    # If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not os.path.exists('credentials.json'):
                print("Error: 'credentials.json' topilmadi!")
                print("Iltimos, Google Cloud Console dan 'OAuth 2.0 Client IDs' (Desktop App) yaratib, uni 'credentials.json' nomi bilan saqlang.")
                return

            flow = InstalledAppFlow.from_client_secrets_file(
                'credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        
        # Save the credentials for the next run
        with open('token.pickle', 'wb') as token:
            pickle.dump(creds, token)
        
        print("\n[OK] 'token.pickle' muvaffaqiyatli yaratildi!")
        print("Endi bot shaxsiy kontaktlaringizga kirish huquqiga ega.")

if __name__ == '__main__':
    main()
