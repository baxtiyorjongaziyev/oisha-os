
import re
import logging
from gcontacts import GoogleContactsSync

# Mocking logging for visibility
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_parsing():
    reply_text = "Salom Olim! Sizni taniganimdan xursandman. [CONTACT_INFO:name=Olim|phone=+998901112233|note=Toshkent, qurilish sohasida tadbirkor] [LEAD_REPORT:QUALITY=Sifatli]"
    
    print(f"Original reply: {reply_text}")
    
    contact_match = re.search(r'\[CONTACT_INFO:(.*?)\]', reply_text)
    if contact_match:
        try:
            contact_raw = contact_match.group(1)
            print(f"Found tag: {contact_raw}")
            c_data = {}
            for part in contact_raw.split('|'):
                if '=' in part:
                    k, v = part.split('=', 1)
                    c_data[k.strip()] = v.strip()
            
            print(f"Parsed data: {c_data}")
            
            if c_data.get('name') or c_data.get('phone'):
                print("Triggering create_contact...")
                # Note: This will actually try to call the API if service_account.json exists
                # sync = GoogleContactsSync("service_account.json")
                # sync.create_contact(
                #     first_name=c_data.get('name', 'Noma\'lum'),
                #     phone=c_data.get('phone', ''),
                #     note=c_data.get('note', 'Telegram orqali avtomatik saqlandi')
                # )
        except Exception as ce:
            print(f"Parsing error: {ce}")
    else:
        print("No CONTACT_INFO tag found!")

if __name__ == "__main__":
    test_parsing()
