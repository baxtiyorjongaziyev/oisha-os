"""Oisha Connect: menejer Telegram akkauntini QR orqali xavfsiz ulash.

Himoyalar:
- kirish faqat QR orqali (kod/parol sahifaga yozilmaydi; 2FA parol saqlanmaydi);
- sessiya Fernet bilan shifrlanadi va menejer Telegram ID siga bogʻlanadi;
- ulangan akkaunt sahifaga kirgan menejerning oʻzi boʻlishi shart;
- chatlar standart holatda yopiq, menejer oʻzi tanlaydi;
- har bir amal jurnalga yoziladi, menejer uni koʻra oladi;
- "Uzish" sessiyani Telegram serverida ham yopadi (log_out).
"""
