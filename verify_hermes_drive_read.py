from pathlib import Path
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

token = Path('/home/hermes/.hermes/google_token.json')
creds = Credentials.from_authorized_user_file(str(token), ['https://www.googleapis.com/auth/drive.readonly'])
service = build('drive', 'v3', credentials=creds, cache_discovery=False)
folder_id = '1yn5cWrxUvND7iYO79-KK5zUfKU4JvuM0'
result = service.files().list(
    q=f"'{folder_id}' in parents and trashed = false",
    fields='files(id,name,mimeType)',
    pageSize=100,
).execute()
files = result.get('files', [])
print(f'FOLDER_READ_OK count={len(files)}')
for item in files[:10]:
    print(f"{item['name']}\t{item['mimeType']}")
