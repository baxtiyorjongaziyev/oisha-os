import hashlib
import hmac
import time
from typing import Dict, Any

def verify_telegram_auth(data: Dict[str, Any], bot_token: str) -> bool:
    """
    Telegram Login ma'lumotlarini tekshirish (hash orqali).
    Data tarkibida: id, first_name, last_name, username, photo_url, auth_date, hash bo'lishi kerak.
    """
    received_hash = data.get('hash')
    if not received_hash:
        return False

    # 1. Ma'lumotlarni alifbo tartibida saralash (hash dan tashqari)
    data_check_list = []
    for key, value in sorted(data.items()):
        if key != 'hash' and value:
            data_check_list.append(f"{key}={value}")
    
    data_check_string = "\n".join(data_check_list)

    # 2. Secret Key yaratish (SHA256(bot_token))
    secret_key = hashlib.sha256(bot_token.encode()).digest()

    # 3. Hash hisoblash (HMAC-SHA256)
    computed_hash = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()

    # 4. Vaqtni tekshirish (masalan, 24 soat ichida)
    auth_date = int(data.get('auth_date', 0))
    if time.time() - auth_date > 86400:
        return False

    return computed_hash == received_hash
