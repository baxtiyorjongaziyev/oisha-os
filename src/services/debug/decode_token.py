import json
import base64

def decode_jwt(token):
    try:
        header, payload, signature = token.split('.')
        # Add padding if needed
        payload += '=' * (-len(payload) % 4)
        decoded_payload = base64.b64decode(payload).decode('utf-8')
        return json.loads(decoded_payload)
    except Exception as e:
        return {"error": str(e)}

with open('amocrm_token.json', 'r') as f:
    data = json.load(f)
    token = data.get('access_token', '')
    payload = decode_jwt(token)
    print(json.dumps(payload, indent=4))
