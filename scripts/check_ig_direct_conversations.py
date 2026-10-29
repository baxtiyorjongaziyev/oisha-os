import os
import sys
import json
import requests
from dotenv import load_dotenv

sys.stdout.reconfigure(encoding='utf-8')
load_dotenv()

def main():
    pat = os.getenv('INSTAGRAM_PAGE_ACCESS_TOKEN')
    ig_id = os.getenv('INSTAGRAM_BUSINESS_ACCOUNT_ID', '17841404148272074')
    
    # 1. Fetch conversations from Instagram Graph API
    url = f"https://graph.facebook.com/v21.0/{ig_id}/conversations"
    params = {
        'platform': 'instagram',
        'fields': 'id,updated_time,participants,unread_count',
        'limit': 50,
        'access_token': pat
    }
    
    r = requests.get(url, params=params)
    print(f"IG Conversations HTTP status: {r.status_code}")
    if r.status_code != 200:
        print("Error:", r.text)
        return
        
    convs = r.json().get('data', [])
    print(f"Total IG Conversations retrieved: {len(convs)}")
    
    # Check messages for each conversation
    for i, c in enumerate(convs):
        cid = c.get('id')
        up_time = c.get('updated_time')
        participants = c.get('participants', {}).get('data', [])
        p_names = [f"{p.get('username')} ({p.get('id')})" for p in participants]
        
        # Fetch last 5 messages
        m_url = f"https://graph.facebook.com/v21.0/{cid}/messages"
        m_params = {
            'fields': 'id,created_time,from,to,message',
            'limit': 10,
            'access_token': pat
        }
        rm = requests.get(m_url, params=m_params)
        messages = rm.json().get('data', []) if rm.status_code == 200 else []
        
        print(f"\n[{i+1}] Thread {cid} | Participants: {', '.join(p_names)} | Updated: {up_time}")
        for m in reversed(messages):
            sender = m.get('from', {}).get('username')
            text = m.get('message', '').replace('\n', ' ')
            m_time = m.get('created_time')
            print(f"    - {m_time} | @{sender}: {text}")

if __name__ == '__main__':
    main()
