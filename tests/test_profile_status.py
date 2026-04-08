import asyncio
import re
from database import Database

def check_status_injection(chat_history):
    is_new_user = True
    if len(chat_history) > 0:
        is_new_user = False
    return "YANGI MIJOZ" if is_new_user else "ESKI MIJOZ (AVVAL MULOQOT QILGAN)"

def test_logic():
    print("Test 1: Empty history ->", check_status_injection([]))
    print("Test 2: With history ->", check_status_injection([("user", "hi")]))
    
    db = Database("bot_database.db")
    # Simulate upserting a new user
    sender_id = 999333444
    db.upsert_user(sender_id, "Ahror", "ahror99")
    info = db.get_user_info(sender_id)
    print("Upserted user info:", info)

if __name__ == "__main__":
    test_logic()
