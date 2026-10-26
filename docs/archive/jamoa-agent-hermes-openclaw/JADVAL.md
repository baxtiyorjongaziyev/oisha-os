# Guruh uchun kunlik jadval

Vaqtlar **Toshkent vaqti (Asia/Tashkent)** bo'yicha. Server vaqt zonasi shunga o'rnatilgan bo'lishi kerak (README, 0-qadam).

**Asosiy qoida:** guruhga botlar o'z tashabbusi bilan **kuniga ko'pi bilan 2 ta** xabar yozadi. Qolgan vaqtda ular faqat @mention yoki reply qilinganda javob beradi.

## Haftalik ko'rinish

| Vaqt | Kun | Kim yozadi | Xabar | Qayerga |
|---|---|---|---|---|
| 09:00 | Dushanba | Navbatchi (OpenClaw) | **Haftalik start:** shu haftaning 1–3 ta asosiy maqsadi | Guruh |
| 09:00 | Seshanba–Juma | Navbatchi (OpenClaw) | **Ertalabki start:** bugungi vazifa, to'siqlar, yordam kerakmi | Guruh |
| 17:30 | Dushanba–Payshanba | Navbatchi (OpenClaw) | **Kun yakuni:** har kim bitta qatorda bugungi natijasini yozadi | Guruh |
| 16:00 | Juma | Hamroh (Hermes) | **Haftalik retro:** nima yaxshi bo'ldi, nima qiyin bo'ldi, nimani o'zgartiramiz + «bu hafta o'rganganlarim» | Guruh |
| 17:00 | Juma | Hamroh (Hermes) | **O'z-o'zini tahlil hisoboti:** o'zgargan skill'lar, yangi bilimlar, xatolar, tasdiq kerak bo'lgan takliflar | **Faqat egaga (DM)** |
| — | Shanba–Yakshanba | — | Jim | — |

## Nega aynan shunday

- **Navbatchi kundalik ritmni ushlab turadi.** U qisqa va bir xil formatdagi xabarlarni yozadi, bu OpenClaw'ning kuchli tomoni (jadval va yo'naltirish).
- **Hamroh haftalik chuqur xulosani yozadi.** U hafta davomida kuzatgan suhbatlardan foydalanadi va o'rganganini jamoaga ochiq ko'rsatadi.
- **O'z-o'zini tahlil hisoboti faqat egaga boradi.** Bot nimani o'rgangani va qaysi skill'larini o'zgartirganini hafta sayin ko'rib turasiz. Noto'g'ri o'rganganini vaqtida tuzatasiz.
- **Juma kuni kechki «kun yakuni» yo'q.** Uning o'rnini retro egallaydi, shunda jumada ham 2 ta xabardan oshmaydi.
- **Javoblar reply emas, oddiy xabar.** Botga reply qilish uni javob berishga majbur qiladi. 6 kishi javob yozsa, bot ham 6 marta javob beradi va guruh shovqinga to'ladi. Oddiy xabarlarga botlar javob bermaydi, lekin Hamroh ularni kuzatib, haftalik retroda va savollarga javob berishda ishlatadi.

## Xabarlar qanday ko'rinadi (namuna)

**Ertalabki start (Navbatchi):**
> Xayrli tong, jamoa! ☀️
> 1. Bugungi asosiy vazifangiz nima?
> 2. Biror to'siq bormi?
> 3. Kimdandir yordam kerakmi?
> Javobingizni shu guruhga oddiy xabar qilib yozing (reply shart emas).
> Yordam kerak bo'lsa @NavbatchiBot yoki @HamrohBot deb yozing.

**Kun yakuni (Navbatchi):**
> Kun yakunlanmoqda. Har kim bitta qatorda yozsin: bugun nima tugadi va ertaga nima davom etadi? Oddiy xabar qilib yozing.

**Haftalik retro (Hamroh):**
> Hafta yakuni 🔁
> Bu hafta 3 ta mijoz loyihasi bo'yicha ish bo'ldi, eng ko'p savol hisobotlar formati haqida tushdi.
> 1. Nima yaxshi bo'ldi?
> 2. Nima qiyin bo'ldi?
> 3. Keyingi hafta nimani o'zgartiramiz?
>
> **Bu hafta o'rganganlarim:** hisobotlar endi payshanba kuni topshiriladi; «KP» — tijoriy taklif degani.

## Jadvalni o'zgartirish

Buyruqlar [hermes/cron.sh](hermes/cron.sh) va [openclaw/cron.sh](openclaw/cron.sh) fayllarida. Faylni o'zgartirgandan keyin eski vazifani o'chiring (`hermes cron list` / `openclaw cron list` dan ID'sini oling), so'ng `sudo bash ornatish.sh` ni qayta ishga tushiring. Vaqt cron formatida yoziladi:

```
daqiqa  soat  oy_kuni  oy  hafta_kuni
  0      9      *      *     2-5        → Seshanba–Juma, 09:00
  30    17      *      *     1-4        → Dushanba–Payshanba, 17:30
```

Hafta kunlari: 1 = Dushanba … 5 = Juma, 6 = Shanba, 0 = Yakshanba.
