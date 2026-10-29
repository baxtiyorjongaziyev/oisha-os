---
name: soliq-ops
description: O'zbekiston soliq hisobotlari (JShDS 11101_20, Aylanma soliq 10104_36)ni tekshirish, o'sib boruvchi zanjirni hisoblash, E-IMZO bilan topshirish, KLS solishtirma dalolatnomasi va ortiqcha to'lovlarni qaytarish bo'yicha operatsion qo'llanma.
---

# Soliq-Ops: O'zbekiston Soliq Operatsiyalari Standarti

Ushbu skill JonBranding MCHJ va O'zbekiston yuridik shaxslari uchun `oldmy.soliq.uz` va `my.soliq.uz` portallari orqali oylik soliq majburiyatlarini avtonom tekshirish, hisoblash va topshirish bo'yicha yagona operatsion qo'llanmadir. Ushbu qo'llanma barcha AI agentlar (Codex, Claude, Cursor, Antigravity) tomonidan bir xil tarzda o'qilishi va ijro etilishi uchun standartlashtirilgan.

---

## 1. Asosiy Korporativ Ma'lumotlar va Kalendar

### Korxona rekvizitlari:
- **Korxona nomi:** "JonBranding" MCHJ
- **STIR / INN:** `312675253`
- **Bank hisobvarag'i:** `20208000107372064001`
- **Bank MFO:** `01180` ("TBC Bank" ATB)
- **Faoliyat turi:** Xizmat ko'rsatish (Aylanmadan olinadigan soliq stavkasi: 4%)

### Soliq kalendari va qat'iy muddatlar:

| Soliq turi | Forma kodi | Qonuniy muddat | Agent harakat sanasi | Davriyligi |
|---|---|---|---|---|
| **JShDS va Ijtimoiy soliq** | `11101_20` | Har oyning **15-sanasigacha** | Har oyning **1-sanasi** (oy boshlanishi bilanoq) | Oylik |
| **Aylanmadan olinadigan soliq** | `10104_36` | Har oyning **16-sanasigacha** | Har oyning **5-sanasi** (birlamchi aylanma auditi va yuborish) | Oylik |
| **INPS (Xalq banki pensiya)** | `101` | Har oyning **15-sanasigacha** | Har oyning **1-sanasi** (JShDS topshirilgach) | Oylik |

> [!NOTE]
> **Owner standarti (2026-10-14):** Soliq hisobotlarini kechiktirmasdan, yangi oy boshlanishi bilanoq (1-sana) topshirish standarti joriy qilindi. 1-sana: Xodimlar oyligi qat'iy bo'lgani sababli JShDS (`11101_20`) va INPS topshiriladi hamda KLS tekshiriladi; 5-sana: Aylanmadan olinadigan soliq (`10104_36`) tekshirilib yakunlanadi.

---

## 2. JShDS va Ijtimoiy Soliq (`11101_20`) Topshirish Protokoli

### A. O'sib boruvchi zanjir qoidasi (233-kodli xatolik profilaktikasi)
* O'zbekiston soliq tizimida JShDS va ijtimoiy soliq yil boshidan o'sib boruvchi (kumulyativ) tartibda hisoblanadi.
* **Qat'iy qoida:** `Joriy oy jami daromadi >= Oldingi oy jami daromadi`. Aks holda server `233 — "Общая сумма начисленных доходов не должна быть меньше чем за предыдущий месяц"` xatoligi bilan hisobotni qat'iyan rad etadi.
* Ketma-ketlik buzilsa, oylar qat'iy ravishda yil boshidan boshlab ketma-ketlikda to'g'rilab yuborilishi shart:
  - Masalan: `Iyun (27 271 000)` -> `Iyul (28 542 000)` -> `Avgust (29 813 000)` -> `Sentabr (31 084 000)`.

### B. Xodimlar reestri va Ilova (`.xltx` / `.xlsx`)
* Xodimlar daromadlari va soliq hisobi Ilova №4 orqali yuklanadi.
* Ilovadagi ustunlar: PINFL, lavozim, stavka, yil boshidan jami daromad, joriy oy daromadi, JShDS (12%) va Ijtimoiy soliq (12%).
* Portalda "Загрузить из файла" tugmasi orqali ilova yuklanadi va "Обновить ячейки" bosiladi.

### C. Portal orqali imzolash (Native JS submission)
* Oddiy HTML `form.submit()` ishlatilmaydi (server qabul qilmaydi).
* Portalning o'z yuborish funksiyasi chaqiriladi:
  ```javascript
  showFinancePackageClickAlert('ru', false, serialNumber, keyId, 'pfx', '11101_20');
  ```
* Bu funksiya avtomatik ravishda: `CheckWebSocket` -> `CAPIWS (load_key)` -> XML yig'ish (`CollectValues`) -> PKCS#7 imzolash (`create_pkcs7`) -> Yakuniy jo'natishni amalga oshiradi.
* Yuborilgach, "Принятые" bo'limida status **«Проведенный вовремя»** yoki **«Проведенный с опозданием»** ekanligi tekshiriladi.

---

## 3. Aylanmadan Olinadigan Soliq (`10104_36`) Protokoli

1. Har oyning 10-sanasidan keyin soliq portali E-faktura (ЭСФ), onlayn-NKM cheklari va bank hisobvaraqlaridagi aylanmalarni o'zi avtomatik yig'ib, "Черновики" bo'limida qoralama generatsiya qiladi.
2. **Tekshirish parametrlari:**
   - 010-satr: Jami tushum (ЭСФ + marketpleys + cheklar).
   - 060-satr: Soliq stavkasi (xizmat ko'rsatish va savdo uchun 4.00%).
   - 070-satr: Hisoblangan soliq (aylanma × 4%).
3. Qoralama ochiladi, tekshiriladi va "Отправить" orqali E-IMZO bilan imzolab jo'natiladi.

---

## 4. Solishtirma Dalolatnoma (KLS) va Ortiqcha To'lovlarni Boshqarish

1. **Holat auditi (`my.soliq.uz`):**
   - URL: `https://my.soliq.uz/remotes-services/personal-account-sheet/main`
   - Kod 36: Ijtimoiy soliq balansi
   - Kod 46: JShDS balansi
   - Kod 100: Aylanma soliq balansi
   - Kod 101: INPS (Xalq banki pensiya badali)
2. **Ortiqcha to'lovni qaytarish (Interaktiv xizmat №657):**
   - URL: `https://my.soliq.uz/remotes-services/refund-amount/main?interactiveId=657`
   - "Ортиқча тўланган суммани шахсий ҳисоб варағига қайтариш" tanlanadi.
   - Har bir soliq turi bo'yicha alohida ariza to'ldiriladi.
   - JonBranding Bank MFO (`01180`) va hisob raqami (`20208000107372064001`) ko'rsatilib, E-IMZO bilan tasdiqlanadi.
3. **Kartoteka-2 va avtomatik yechish:**
   - Soliq idorasi tomonidan hisob raqamga inkasso qo'yilgan bo'lsa, soliq ortiqcha to'lovi hisob raqamga qaytishi bilan TBC Bank avtomatlashtirilgan bank tizimi (ABS) navbatlilik asosida qarzdorlikni yechib, hisobni ochadi (Fuqarolik kodeksining 783-moddasi).

---

## 5. Browser Avtomatizatsiyasi va Ijro Mexanizmi (CDP / Chrome 9222)

Har qanday agent (Codex, Claude, Cursor, Antigravity) quyidagi Python uslubi orqali brauzer bilan to'g'ridan-to'g'ri aloqa o'rnata oladi:

```python
import json, urllib.request, asyncio, websockets

# 1. Ochilgan tablarni aniqlash
tabs = json.loads(urllib.request.urlopen("http://localhost:9222/json").read())
soliq_tab = next((t for t in tabs if "soliq.uz" in t.get("url", "")), None)

# 2. Brauzerda buyruq / JavaScript bajarish
async def run_cdp(ws_url, expr):
    async with websockets.connect(ws_url) as ws:
        msg = {
            "id": 1,
            "method": "Runtime.evaluate",
            "params": {"expression": expr, "returnByValue": True}
        }
        await ws.send(json.dumps(msg))
        resp = await ws.recv()
        return json.loads(resp).get("result", {}).get("result", {}).get("value")
```

---

## 6. Xatoliklar Profilaktikasi (Troubleshooting)

1. **Port 9222 ulanmayapti:**
   - Chrome `--remote-debugging-port=9222` parametri bilan ochilganini tekshiring.
   - Brauzerda "Allow remote debugging?" darchasi paydo bo'lsa, **Allow** bosilganini tasdiqlang.
2. **E-IMZO topilmadi (`WebSocket connection failed`):**
   - E-IMZO tray dasturi (yoki port 64443) ishlab turganini tekshiring.
3. **233-xatolik (Daromad kamayishi):**
   - Oldingi oylarning hisobotlaridagi kumulyativ summalarni KLS bilan solishtiring va oraliq qoralama/xatolarni ketma-ket qayta yuboring.
4. **Har bir operatsiyadan so'ng:**
   - Natijani `brain_log(action, detail)` orqali Obsidian xotirasiga muhrlang.
