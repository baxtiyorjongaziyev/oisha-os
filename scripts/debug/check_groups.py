import os
import pickle
import logging
from googleapiclient.discovery import build
import google.auth.transport.requests

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_groups():
    creds = None
    if os.path.exists("token.pickle"):
        with open("token.pickle", "rb") as token:
            creds = pickle.load(token)

    if not creds:
        print("No credentials found")
        return

    service = build('people', 'v1', credentials=creds)

    group_name = "TEZ NATIJA 5"
    resource_name = None

    try:
        # 1. Barcha guruhlarni olish
        results = service.contactGroups().list().execute()
        groups = results.get('contactGroups', [])
        
        for group in groups:
            if group.get('name') == group_name:
                resource_name = group.get('resourceName')
                print(f"Topildi: {resource_name}")
                break
        
        # 2. Agar yo'q bo'lsa, yaratish
        if not resource_name:
            print("Guruh topilmadi, yaratilmoqda...")
            new_group = service.contactGroups().create(body={
                "contactGroup": {
                    "name": group_name
                }
            }).execute()
            resource_name = new_group.get('resourceName')
            print(f"Yaratildi: {resource_name}")
            
    except Exception as e:
        print(f"Xato: {e}")

if __name__ == '__main__':
    test_groups()
