
import gspread
from google.oauth2.service_account import Credentials
import os
import sys

def diag():
    spreadsheet_id = "1OkML2fp3NMocZzm8kPfeE1B9X3SO2V8yYidv7N4iJjM" # Örnek ID, .env dan olinadi
    creds_path = "credentials.json"
    
    if not os.path.exists(creds_path):
        print(f"Error: {creds_path} not found!")
        return

    scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    try:
        creds = Credentials.from_service_account_file(creds_path, scopes=scopes)
        client = gspread.authorize(creds)
        print("Auth OK")
        
        # Try to open
        try:
            ss = client.open_by_key(spreadsheet_id)
            print(f"Spreadsheet opened: {ss.title}")
            sheet = ss.get_worksheet(0)
            print(f"Worksheet 0 found: {sheet.title}")
        except Exception as e:
            print(f"Spreadsheet Error: {e}")
            
    except Exception as e:
        print(f"Auth Error: {e}")

if __name__ == "__main__":
    diag()
