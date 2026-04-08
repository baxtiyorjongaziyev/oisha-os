import asyncio
from database import Database

async def mock_forward_to_crm(context, user_info, message_text, reply_text, quality):
    print(f"\n[MOCK CRM SEND] Quality: {quality}")
    print(f"User: {user_info['name']} ({user_info['phone']})")

async def test_lead_progression():
    db = Database("bot_database.db")
    sender_id = 999111222
    sender_name = "Test User"
    username = "testuser"
    
    # 1. User says hi, gives name and phone
    db.upsert_user(sender_id, sender_name, username, phone="+998901234567")
    
    # Reset status for test
    with db.get_connection() as conn:
        conn.cursor().execute("UPDATE users SET is_lead_forwarded=0 WHERE user_id=?", (sender_id,))
        conn.commit()

    print("Initial status:", db.get_user_info(sender_id)['is_lead_forwarded'])
    
    # 2. Simulate AI deciding it's an 'oddiy' lead
    lead_quality = "oddiy"
    text = "Men logotip xizmati bo'yicha yozgandim."
    reply_text = "[LEAD_REPORT:QUALITY=Oddiy]"
    
    forward_status = db.get_user_info(sender_id).get('is_lead_forwarded', 0)
    should_forward = False
    new_status = 0
    
    if lead_quality == "oddiy" and str(forward_status) != "1" and str(forward_status) != "2":
        should_forward = True
        new_status = 1
    elif lead_quality == "sifatli" and str(forward_status) != "2":
        should_forward = True
        new_status = 2

    if should_forward:
        user_info = {
            "id": sender_id,
            "name": sender_name,
            "username": username,
            "phone": "+998901234567"
        }
        await mock_forward_to_crm(None, user_info, text, reply_text, quality=lead_quality.capitalize())
        with db.get_connection() as conn:
            conn.cursor().execute("UPDATE users SET is_lead_forwarded=? WHERE user_id=?", (new_status, sender_id))
            conn.commit()
            
    print("Status after Oddiy:", db.get_user_info(sender_id)['is_lead_forwarded'])
    
    # 3. Simulate AI deciding it's now a 'sifatli' lead
    lead_quality = "sifatli"
    text = "Menga arxitektura firmam uchun qora rangda tezkor logotip kerak."
    reply_text = "[LEAD_REPORT:QUALITY=Sifatli]"
    
    forward_status = db.get_user_info(sender_id).get('is_lead_forwarded', 0)
    should_forward = False
    new_status = 0
    
    if lead_quality == "oddiy" and str(forward_status) != "1" and str(forward_status) != "2":
        should_forward = True
        new_status = 1
    elif lead_quality == "sifatli" and str(forward_status) != "2":
        should_forward = True
        new_status = 2

    if should_forward:
        user_info = {
            "id": sender_id,
            "name": sender_name,
            "username": username,
            "phone": "+998901234567"
        }
        if lead_quality == "sifatli" and str(forward_status) == "1":
            await mock_forward_to_crm(None, user_info, f"Yangilanish: Mijoz barcha ma'lumotlarni to'ldirdi!\nOldingi xabar: {text}", reply_text, quality="Sifatli (Yangilangan)")
        else:
            await mock_forward_to_crm(None, user_info, text, reply_text, quality=lead_quality.capitalize())

        with db.get_connection() as conn:
            conn.cursor().execute("UPDATE users SET is_lead_forwarded=? WHERE user_id=?", (new_status, sender_id))
            conn.commit()

    print("Status after Sifatli:", db.get_user_info(sender_id)['is_lead_forwarded'])

if __name__ == "__main__":
    asyncio.run(test_lead_progression())
