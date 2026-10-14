## 📝 Tavsif (Description)
Qisqacha nima o'zgardi va qaysi vazifa hal qilindi?

Fixes #(issue_raqami)

---

## 🔍 O'zgarishlar Turi (Type of Change)
- [ ] 🐛 Bug fix (ishlamayotgan funksiyani tuzatish)
- [ ] ✨ New feature (yangi imkoniyat qo'shish)
- [ ] ♻️ Refactoring (kod tuzilishini yaxshilash, funksiya o'zgarmagan)
- [ ] 🛡️ Security patch (xavfsizlik va ruxsatlar bilan bog'liq tuzatish)
- [ ] 📚 Documentation (hujjatlar va yo'riqnomalar yangilanishi)
- [ ] ⚙️ CI/CD / DevOps (GitHub Actions, Docker, Systemd konfiguratsiyasi)

---

## 🧪 Sinov va Tekshiruv Dalili (Verification & Test Proof)
Quyidagi komandalar lokal ravishda muvaffaqiyatli o'tdimi?

- [ ] Bytecode tekshiruvi:
  ```bash
  python -m py_compile src/main.py src/api_server.py src/database.py
  ```
- [ ] Tezkor testlar (Fast Gate):
  ```bash
  SKIP_LIVE=1 python -m pytest -q tests/test_api_server_security.py
  ```
- [ ] Xavfsizlik skaneri (Bandit):
  ```bash
  bandit -r src/ -ll -x src/services/debug/ --quiet
  ```

---

## ✅ Nazorat Ro'yxati (Pre-flight Checklist)
- [ ] Kod standartlariga amal qilindi (`docs/agents/code-standards.md`: fayl ≤ 400 qator, funksiya ≤ 60 qator).
- [ ] Hech qanday maxfiy kalit (token, parol, session string) commitga kiritilmadi.
- [ ] `AGENTS.md` qoidalari buzilmadi.
- [ ] Handoff yozuvi yangilandi (`docs/agents/handoff-log.md`).
- [ ] `main` ga to'g'ridan-to'g'ri emas, feature branch orqali ochildi.
