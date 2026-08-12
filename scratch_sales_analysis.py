import os
from dotenv import load_dotenv
import libsql_client
import google.generativeai as genai

load_dotenv()

genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
model = genai.GenerativeModel("gemini-2.5-flash")

client = libsql_client.create_client_sync(url=os.getenv("TURSO_DATABASE_URL"), auth_token=os.getenv("TURSO_AUTH_TOKEN"))

rs = client.execute("SELECT call_id, transcript FROM call_analyses WHERE transcript IS NOT NULL AND transcript != '' ORDER BY created_at DESC LIMIT 20")

transcripts_text = []
for row in rs.rows:
    call_id, transcript = row[0], row[1]
    if len(transcript) > 200: # skip very short ones which might be invalid
        transcripts_text.append(f"--- CALL ID {call_id} ---\n{transcript}\n")

if not transcripts_text:
    print("No valid transcripts found to analyze.")
    exit(0)

prompt = """
Siz 'Jon Branding' agentligining malakali sotuv bo'limi boshlig'i va biznes-analitikisiz.
Quyida oxirgi qo'ng'iroqlarning (mijozlar va menejerlar o'rtasida) transkriptlari berilgan.
Sizning vazifangiz ularni chuqur tahlil qilib, quyidagi tuzilmada hisobot (sales strategy report) tayyorlash:

1. Asosiy Xatolar va Tushish Nuqtalari: Menejerlar qayerda mijozni ushlab qola olmayapti? (Ob'yeksiyalar bilan ishlash, narxni aytish, taqdimot, va hk.)
2. Muvaffaqiyatli Taktikalar (agar bo'lsa): Qaysi yondashuvlar yaxshi ishlamoqda?
3. Konversiyani Oshirish Uchun 3 ta Aniq Maslahat: Har bir menejer qo'llashi kerak bo'lgan script yoki qoida.
4. Xulosa.

Javobni Markdownda chiroyli qilib formatlang. Tahlil faqat O'zbek tilida bo'lsin.

TRANSKRIPTLAR:
""" + "\n".join(transcripts_text)

print("Analyzing with Gemini...")
response = model.generate_content(prompt)
print("=== ANALYSIS START ===")
print(response.text)
print("=== ANALYSIS END ===")
