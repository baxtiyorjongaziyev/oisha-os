import os
import json
import sqlite3
import datetime
from google import genai
from dotenv import load_dotenv

# Konfiguratsiya
load_dotenv()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
OBSIDIAN_INBOX_PATH = r"C:\Users\baxti\OneDrive\Документы\Obsidian Vault\00-Inbox\AI Promises Tracker.md"
DB_PATH = r"C:\Users\baxti\playground\oisha-os\data\oisha.db" # Yoki Turso URL

PROMPT = """
You are the AI Promises Tracker for Oisha-OS.
Analyze the following recent tasks, activities, and communication logs.
Extract any "Dropped Balls", Unfulfilled Promises, or Pending Agreements.

Format your output EXACTLY as a markdown list:
- **[Person/Client Name]**: What was promised or left pending. (Context)
- ...

If nothing is found, return "Bugun uchun qolib ketgan va'dalar yo'q."

Data:
{data}
"""

def fetch_recent_data():
    """Oisha ma'lumotlar bazasidan oxirgi 24 soatdagi muhim loglarni oladi."""
    try:
        # SQLite bazadan o'qiymiz (Agar Turso bo'lsa, libsql klientidan foydalaniladi)
        if not os.path.exists(DB_PATH):
            return "No local db found. Simulating data fetch from AmoCRM/Telegram."
            
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT title, description FROM tasks WHERE status='Pending' LIMIT 10")
        rows = cursor.fetchall()
        
        data = "\n".join([f"Task: {r[0]} - {r[1]}" for r in rows])
        return data if data else "No pending tasks found in DB."
    except Exception as e:
        return f"Error fetching data: {e}"

def generate_insights(data):
    if not GEMINI_API_KEY:
        return "- **Xato**: GEMINI_API_KEY topilmadi."
        
    client = genai.Client(api_key=GEMINI_API_KEY)

    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=PROMPT.format(data=data),
        )
        return response.text
    except Exception as e:
        return f"- **API Xatosi**: {e}"

def write_to_obsidian(content):
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    
    # Fayl sarlavhasi
    header = f"""---
type: ai-digest
date: {datetime.datetime.now().strftime('%Y-%m-%d')}
---
# 🧠 AI Promises Tracker

*Avtomatik sintez qilingan vaqt: {now}*

"""
    
    os.makedirs(os.path.dirname(OBSIDIAN_INBOX_PATH), exist_ok=True)
    
    with open(OBSIDIAN_INBOX_PATH, "w", encoding="utf-8") as f:
        f.write(header + content + "\n\n---\n*Bu fayl Oisha-OS `local_brain_synthesizer.py` tomonidan avtomatik yangilanadi.*")

import time

def main():
    print("🚀 24/7 Avtomatik Rivojlanuvchi Miya ishga tushdi...")
    while True:
        print(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] Sintez jarayoni boshlandi...")
        data = fetch_recent_data()
        
        insights = generate_insights(data)
        
        if "Bugun uchun qolib ketgan" not in insights and "Error" not in insights:
            write_to_obsidian(insights)
            print("✅ Yangi kelishuvlar Obsidian'ga yozildi.")
        else:
            print("Zaruriy o'zgarish yo'q. Kutmoqdaman...")
            
        time.sleep(3600) # Har 1 soatda avtomatik tekshirib boradi

if __name__ == "__main__":
    main()
