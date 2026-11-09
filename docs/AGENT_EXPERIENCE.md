# AGENT_EXPERIENCE

Tajriba jurnali. Har yozuv faqat tekshirilgan faktga asoslanadi: sana, muhit, buyruq/fayl yo'li.

---

## 2026-11-05 — Telegram Web'ni foydalanuvchi Chrome sessiyasi orqali o'qish (Windows)

**Muhit:** Windows 11, Chrome 156, OpenCode agent, Contabo VPS'dagi Hermes'dan alohida.

### ✅ Ishladi

1. **Profil nusxasi + CDP.** Foydalanuvchining ishlab turgan Chrome'iga (`--remote-debugging-port`siz) ulanib bo'lmaydi. Ishlaydigan yo'l:
   - `robocopy "%LOCALAPPDATA%\Google\Chrome\User Data" "<temp>\tg-chrome2" "Local State"`
   - `robocopy "%LOCALAPPDATA%\Google\Chrome\User Data\Default" "<temp>\tg-chrome2\Default" /E /XD Cache "Code Cache" GPUCache CacheStorage "Service Worker" blob_storage "File System"`
   - `Start-Process chrome.exe -ArgumentList "--remote-debugging-port=9226","--user-data-dir=<temp>\tg-chrome2","--no-first-run","--new-window","https://web.telegram.org/a/"`
   - `agent-browser --cdp 9226 <cmd>` yoki to'g'ridan-to'g'ri `curl http://127.0.0.1:9226/json/version`
   - Natija: Telegram Web akkauntga kirilgan holatda ochildi, chatlar va a'zolar ro'yxati o'qildi.

2. **Guruhga o'tish.** `https://web.telegram.org/a/#-100…` hash bilan ochish ishlamadi (hash tashlab yuboriladi). Ishlaydigan yo'l:
   - qidiruv maydoniga guruh nomini yozish → `agent-browser find text "<nom>" click` → URL o'zi `#-100…` bo'ladi.
   - A'zolar ro'yxati: o'ng paneldagi sarlavha ustiga bosish → "Group Info" → **Members** tab.

3. **Telegram guruh metasini bot orqali tekshirish (serverda).** `getChat`, `getChatMemberCount`, `getChatAdministrators`, `getChatMember` — bot a'zo bo'lsa ishlaydi va `left` holatini ham qaytaradi. Bu a'zolikni aniqlashning eng ishonchli yo'li.

### ❌ Ishlamadi

1. **`agent-browser --profile Default open …`** → `Chrome exited early (exit code: -1073741819)` (`0xC0000005`). Sabab: profil boshqa Chrome process tomonidan band (ProcessSingleton). Profil nusxasi bilan ham bir xil xato berdi — `agent-browser` o'z Chrome'ini profIL bilan ko'tarishda beqaror.
2. **Ishlab turgan Chrome'ga ulanish.** `--remote-debugging-port` bilan ishga tushirilmagan instansiyaga CDP orqali ulanishning yo'li yo'q. Chrome'ni yopib qayta ochish kerak (foydalanuvchi ishini buzadi).
3. **CDP sessiyasining uzoq umri.** Bir necha daqiqadan keyin debug Chrome `0xC0000005` bilan yiqildi va port yopildi (`/json/version` javob bermaydi). Uzoq sessiyada har qadamdan keyin `curl http://127.0.0.1:<port>/json/version` bilan tirikligini tekshirish kerak.
4. **`agent-browser eval` / `mouse wheel`** uzoq sessiyada `Operation timed out` bilan qaytadi. Virtual scroll (Telegram `MessageList`) sichqoncha g'ildiragi bilan ham surilmadi — tarixni chuqur o'qish uchun ishonchli yo'l topilmadi.
5. **Bir marta `robocopy` qilingan profil** (Local Storage + IndexedDB alohida ko'chirilgan) keyingi ochilishda QR-login sahifasini ko'rsatdi — sessiya yo'qoldi. Sabab tasdiqlanmagan (ehtimol LevelDB nomuvofiq snapshot). Butun `Default` papkasini bir yo'la ko'chirish ishladi.

### ➡️ Qoida

- Foydalanuvchi Chrome'iga ulanish kerak bo'lsa: **avval profilkan to'liq nusxa ol**, `robocopy` bilan bo'laklab emas; keyin alohida `--user-data-dir` + `--remote-debugging-port` bilan ko'tar.
- CDP Chrome beqaror: har muhim qadamdan keyin portni `curl` bilan tekshir; yiqilsa qayta ko'tar.
- Guruh a'zoligi va turini aniqlashda **bot API birlamchi manba**, brauzer faqat vizual tasdiq uchun.

---

## 2026-11-05 — Hermes cron job'ni masofadan tahrirlash (Contabo, `hermes cron edit`)

**Muhit:** `root@109.199.100.137`, Hermes CLI `sudo -u hermes /home/hermes/.local/bin/hermes`, Windows PowerShell'dan SSH.

### ✅ Ishladi

1. **Ko'p qatorli promptni uzatish.** `ssh host 'hermes cron edit ID --prompt "$(cat /tmp/f.txt)"'` — Windows SSH klienti qo'shtirnoqlarni buzadi, prompt so'zlarga bo'linadi (`unrecognized arguments: ish kuni soat …`).
   Ishlaydigan yo'l: skriptni lokal yozib, **base64** qilib yuborish:
   ```powershell
   $sh = (Get-Content .\apply.sh -Raw) -replace "`r`n", "`n"
   $b  = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($sh))
   ssh root@host "echo $b | base64 -d > /tmp/apply.sh; bash /tmp/apply.sh"
   ```
   Skript ichida `"$(cat /tmp/prompt.txt)"` normal ishlaydi.

2. **Promptni serverda tayyorlash.** Prompt matnini lokalda qayta yozish xato keltiradi (transkripsiya). To'g'ri yo'l: Python skript serverda `jobs.json` dan o'qib, `.replace()` qilib, `/tmp/prompt.txt` ga yozadi; keyin `hermes cron edit --prompt "$(cat /tmp/prompt.txt)"`.

3. **Readback.** O'zgarishdan keyin `jobs.json` dan `deliver`, `schedule`, `enabled`, `len(prompt)`, prompt boshi/oxirini qayta o'qib tasdiqlash.

### ❌ Ishlamadi

1. `ssh 'sudo -u hermes sqlite3 …'` → `sqlite3: command not found` (VPS'da yo'q). SQLite o'qish uchun `sudo -u hermes python3 -` ishlatiladi.
2. `ssh host $cmd` bilan PowerShell here-string ichida `<<'PY'` heredoc — Windows tomon quote buzilishi. Base64 yo'li ishonchli.

### ➡️ Qoida

- Hermes cron'ni masofadan tahrirlashda **har doim** base64 skript + serverda `$(cat file)`; to'g'ridan-to'g'ri `ssh '… --prompt "…"'` ishlatilmaydi.
- Har tahrirdan keyin `jobs.json.bak-<sana>-<mavzu>` zaxira va readback majburiy.

---

## 2026-11-09 — Jamoa (Airtable) record ID'lari va sotuvchi handle'lari

**Muhit:** `root@109.199.100.137`, jonli checkout `/home/ubuntu/oisha-os` (venv: `/home/ubuntu/oisha-os/venv`), Windows PowerShell'dan SSH.

### ✅ Ishladi

1. **Jamoa jadvalini o'qish.** Skriptni lokal yozib `scp` qilib, prod venv bilan ishga tushirish:
   `cd /home/ubuntu/oisha-os && PYTHONPATH=. venv/bin/python /tmp/jamoa_probe.py`.
   Skript ichida `AirtableSync(table_name="Jamoa").get_projects()` -> `id`, `Ism`, `Telegram`.
   Natija: `recDbMupPcviBctAd` = Rayxon Rahimova, `recndwD6R8Wk3CNtY` = Mumtozmaxal Normurodova.
   Lokal `data/airtable_all_*.json` fayllari Jamoa jadvalini o'z ichiga olmaydi.
2. **Airtable maydonini yangilash.** `update_project_fields(rec_id, {"Telegram": "@handle"})` -> `True`,
   keyin `get_projects(force_refresh=True)` bilan qayta o'qib tasdiqlash.
3. **Deploy.** `python scripts/deploy_contabo_direct.py <fayllar>` (dry-run hash) -> `--apply`;
   natija `DEPLOYED: file hashes verified, healthz=200`. Sog'liq: `http://127.0.0.1:8080/healthz/`
   (`8000/healthz` 404 beradi).

### ❌ Ishlamadi

1. **Lokal Airtable.** `.env` yo'q: `get_finance_records()` -> `[[]]`, log
   `[AIRTABLE] API key yoki Base ID yetishmayapti`.
2. **Handle'ni Bot API bilan tekshirish.** `getChat?chat_id=@username` bot ko'rmagan foydalanuvchi uchun
   `400 Bad Request: chat not found` qaytaradi — bu handle yo'qligini isbotlamaydi.
3. **SSH ichida ko'p qatorli `python -c`.** PowerShell qo'shtirnoqlarni buzadi (`Argument expected for the -c option`).
   Yechim: skript fayl + `scp` + `venv/bin/python /tmp/script.py`.
4. **PowerShell'da `git push`.** `exit code 1` ko'rsatadi (stderr chiqishi), lekin push o'tadi;
   tasdiq `git rev-parse HEAD` == `git rev-parse origin/<branch>`.
5. **Obsidian Local REST API** shu sessiyada `fetch failed` berdi; yozuv vault fayliga to'g'ridan-to'g'ri qo'shildi.

### ➡️ Qoida

- Jamoa record ID yoki handle kerak bo'lsa — taxmin qilinmaydi, prodda `Jamoa` jadvali o'qiladi va manba yoziladi.
- Airtable maydoni o'zgarsa, darhol Obsidian `20-Areas/Airtable_Operatsion_Tizimi_va_Ozgarishlar.md` ga yoziladi.
- `income_supervisor` map'lari o'zgarsa, `tests/test_income_supervisor.py` guard testlari yuritiladi.
- Prodda ishlaydigan checkout — `/home/ubuntu/oisha-os`; `/root/oisha-os` eski nusxa.
