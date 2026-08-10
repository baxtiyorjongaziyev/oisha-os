# MetaSell konversiya sikli

> Maqsad: qo'ng'iroq tahlili **sotuvchi konversiyasini oshirishga** xizmat qilsin —
> hisobot uchun ball to'plash uchun emas.

## Muammo nima edi

`CallAnalyzer` har bir AmoCRM qo'ng'irog'ini 6 bosqichli rasmiy rubrik bo'yicha
baholardi va natijani AmoCRM notasiga chiroyli qilib yozardi. Lekin bazaga
**faqat matnli ustunlar** tushardi:

```
Yozilardi : call_id, lead_id, category, summary, client_mood, next_steps,
            transcript, audio_url, caller_phone, task_id, analyzed_at, source
Yozilmasdi: overall_score, manager_name, strengths, weaknesses, outcome,
            duration_seconds
```

Murabbiylik qatlami — `SalesQualityCoach` (kunlik 20:00 hisoboti, haftalik ideal
skript, playbook takliflari) va `/api/ai/metasell-dashboard` — **aynan shu
yozilmagan 6 ta ustunni** o'qiydi.

Natija: ballar hisoblanardi, AmoCRM notasida ko'rinardi va **yo'qolardi**.
Murabbiy bo'sh jadval ustida ishlardi, shuning uchun sotuvchi konversiyasiga
hech qanday ta'sir qila olmasdi.

## Yechim: uch qism

### 1. Sxema bir joyda — `call_analyses_schema.py`

`call_analyses` jadvali endi bitta joyda, to'liq ustunlar bilan e'lon qilinadi.
Mavjud bazaga yetishmayotgan ustunlar idempotent `ALTER TABLE` orqali qo'shiladi
(namuna: `hisobchi_schema.py`). Migratsiya "fail-soft": yiqilsa ham qo'ng'iroq
tahlili to'xtamaydi.

### 2. Ball bazaga yetib boradi — `call_analyzer.py`

Tahlil prompti endi murabbiy uchun kerakli maydonlarni ham so'raydi
(`kuchli_tomonlar`, `zaif_tomonlar`, `etirozlar`, `natija`), va `_log_call_analysis`
to'liq qatorni saqlaydi: `overall_score`, `manager_name`/`manager_id`,
`duration_seconds`, bosqich ballari (`scores`), `strengths`, `weaknesses`,
`objections`, `outcome`, `converted`.

Menejer ismi AmoCRM `responsible_user_id` orqali aniqlanadi — ismsiz qo'ng'iroqni
hech kimga bog'lab bo'lmaydi, shuning uchun u konversiya statistikasiga kirmaydi.

### 3. Konversiya dvigateli — `metasell_conversion.py`

Kunlik hisobot sotuvchilarni **ball** bo'yicha saflaydi. Lekin ball pul
keltirmaydi: menejer 88 ball olib ham bitta uchrashuv kelisha olmasligi mumkin.
Bu modul boshqa savolga javob beradi:

> **Aynan qaysi bosqich shu sotuvchida bitimni yo'qotmoqda?**

Metodologiya ataylab sodda va shaffof:

```
konversiya     = playbook CONVERTING_OUTCOMES bilan tugagan qo'ng'iroqlar ulushi
bosqich_farqi  = o'rtacha_ball(konvertirlangan) − o'rtacha_ball(konvertirlanmagan)
o'sish_nuqtasi = eng katta musbat farqli bosqich (playbook og'irligi hisobga olingan)
```

Ya'ni sotuvchining **o'z** yutgan va yutqazgan qo'ng'iroqlari solishtiriladi.
Bu taxmin emas — dalil.

**Namuna yetarli bo'lmasa modul jim turadi.** Yolg'on ishonch bilan noto'g'ri
maslahat berish konversiyani pasaytiradi, shuning uchun:

| Holat | Xatti-harakat |
|---|---|
| < 6 ta baholangan qo'ng'iroq | Diagnoz yo'q, sabab aytiladi |
| Bir guruh bo'sh (hammasi yutgan/yutqazgan) | Eng past bosqich, "bu dalil emas" izohi bilan |
| Bosqich farqi < 5 ball | "Muammo texnikada emas" deb rostini aytadi |

## Natija: sotuvchi nima ko'radi

Ballar ro'yxati emas, **shu hafta bitta vazifa**:

```
🎯 KONVERSIYA KARTOCHKASI — Aziz Karimov

Qo'ng'iroqlar: 8 ta
Konversiya: 50% (4 ta keyingi qadamga chiqdi)
O'rtacha ball: 75/100

📌 SHU HAFTA BITTA VAZIFA: Yakunlash va keyingi qadam

Nega aynan shu: Konvertirlangan qo'ng'iroqlarda 'Yakunlash va keyingi qadam'
bo'yicha o'rtacha 92 ball, konvertirlanmaganlarida 30 — farq 62 ball.

Mashq: Hech bir qo'ng'iroqni keyingi qadamsiz tugatmang. Yakunda aniq taklif
qiling: 'Kelasi seshanba soat 15:00 da uchrashamizmi?'

Mo'ljal: shu bosqich tuzatilsa konversiya ~16% ga oshishi mumkin.
```

Rahbariyat uchun eng qimmat signal — **ball yuqori, konversiya past**:

```
⚠️ Ball yuqori, konversiya past (skript bajarilyapti, bitim yopilmayapti):
  • Bek Yusupov — 88 ball, 0% konversiya
```

Ball bo'yicha Bek "kunning eng yaxshi sotuvchisi". Konversiya bo'yicha —
jamoaning eng qimmat muammosi. Aynan shu farqni ko'rsatish uchun bu modul yozildi.

## Natija taksonomiyasi

Konversiya mezoni `sales_playbook.py` da — baholashning yagona manbasida:

| Kalit | Konversiya? |
|---|---|
| `uchrashuv_kelishildi` | ✅ |
| `material_yuborish` | ✅ |
| `kp_yuborish` | ✅ |
| `tolov_kelishildi` | ✅ |
| `qayta_qongiroq`, `oylab_koradi`, `rad_etdi`, `aniqlanmadi` | ❌ |

Mezon o'zgarsa — faqat `sales_playbook.py` o'zgaradi.

## Interfeyslar

| Kanal | Manzil | Vaqt |
|---|---|---|
| Telegram — jamoa hisoboti | `BackgroundMonitor._job_conversion_weekly` | Dushanba 10:05 |
| Telegram — sotuvchi kartochkalari | shu job, rahbarga | Dushanba 10:05 |
| API — jamoa manzarasi | `GET /api/ai/conversion/overview?days=30` | — |
| API — bitta sotuvchi | `GET /api/ai/conversion/seller-card?manager=<ism>` | — |

## Guardrail

Bu modul **hech narsani avtomatik o'zgartirmaydi**. Playbook (`sales_playbook.py`)
faqat odam qo'li bilan o'zgaradi — mavjud `SalesQualityCoach` qoidasi bilan bir xil.

## Testlar

```bash
SKIP_LIVE=1 python -m pytest tests/test_metasell_conversion.py \
                            tests/test_call_analysis_persistence.py -q
```

`test_call_analysis_persistence.py` regressiya qo'riqchisi: murabbiy o'qiydigan
ustunlar ro'yxati qisqarsa test yiqiladi — ya'ni bu uzilish qaytib kelmaydi.
