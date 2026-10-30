# Oisha CRM: amoCRM bilan parallel ishlash

2026-10-19. Owner so'rovi: 5 sotuvchi, avval amoCRM bilan birga ishlash,
keyin ichki CRMga bosqichma-bosqich o'tish. Bu hujjat production ishga
tushirilgani yoki migratsiya yakunlanganini tasdiqlamaydi.

## Birinchi versiya

- Web doska: `/api/crm/parallel/console`; mavjud `/crm` sahifasidan havola.
- amoCRM asosiy savdo manbasi. Bitimlar, kontaktlar, vazifalar, foydalanuvchilar
  va voronkalar mavjud DatabasePool orqali ichki bazaga ko'chiriladi.
- Nom va shu voronkadagi bosqichni o'zgartirish qo'llab-quvvatlanadi.
  Saqlash avval durable outbox'ga yoziladi; UI bu holatni tasdiq deb ko'rsatmaydi.
- Worker avval amoCRM holatini qayta o'qiydi, o'zgarish kiritadi, yana o'qib
  natijani tekshiradi. Oldingi holat o'zgargan bo'lsa conflict chiqaradi.
- Takroriy request UUID bir xil natijaga bog'lanadi; bir bitimda bir vaqtning
  o'zida bitta faol operatsiya. Bekor qilingan operatsiya claim qilinmaydi.
- PATCH natijasi noaniq bo'lsa avtomatik qayta yuborilmaydi. Keyingi tekshiruv
  faqat o'qiydi: qiymat mos bo'lsa applied, aks holda conflict.
- Qaydlar va status o'tishlari append-only audit triggerlariga yoziladi.
- Source ishlamasa eski nusxa va uning tekshiruv vaqti ko'rinadi.
  Nol qiymatlar unavailable o'rniga ishlatilmaydi.

## O'qish va sinxronlash

Worker har 60 soniyada ishlaydi; UI har 15 soniyada mavjud nusxani yangilaydi.
23:00–07:00 Toshkent vaqtida queued writeback yuborilmaydi; ichki o'qish va
noaniq natijani faqat o'qib tekshirish davom etadi. UI kechiktirish sababini ko'rsatadi.
Har entity turi alohida checkpointga ega. Bir siklda har turdan ko'pi bilan
20 × 250 yozuv olinadi; keyingi sahifa DB'da saqlanadi. Tugallanmagan yoki
xato bergan entity checkpointi oldinga surilmaydi.

O'zgarishlar `updated_at[from]` va `order[id]=asc` bilan olinadi. Yuqori
sana chegarasi berilmaydi: import paytida o'zgargan yozuv sahifalardan
yo'qolib qolmasligi kerak. Checkpoint — o'tish boshlangan vaqt; 120 soniyalik
overlap takrorlarni ID orqali upsert qiladi. Har 24 soatda eski yozuvlarni
ham qayta oladigan to'liq o'tish bor. Bu source'dagi har bir o'chirish
mahalliy nusxada aks etganining isboti emas.

AmoCRM account ID birinchi ulanishda bog'lanadi. Boshqa accountga o'tib
qolinsa import va writeback to'xtaydi. Account URL faqat source'dagi
tekshirilgan subdomaindan tuziladi.

## Xavfsizlik va rollar

- Eski API autentifikatsiyasi va RBAC qayta ishlatiladi.
- Owner/Admin: barcha ruxsat etilgan bitimlar; seller: faqat aniq
  mappingdagi amoCRM responsible_user_id yozuvlari.
- Sotuvchining Telegram/email subject'i amoCRM raqami deb taxmin qilinmaydi.
  Mapping bo'lmasa kirish 403 bilan to'xtaydi.
- Mapping bir nechta sotuvchini bir xil responsible ID'ga bog'lasa ular bir xil
  bitimlar to'plamini ko'radi. Alohida ko'rinish uchun aniq alohida assignment kerak.
- Browser mutatsiyalari Origin hamda X-Oisha-CRM headerini talab qiladi.
  Service bearer uchun Origin bo'lmasligi mumkin; autentifikatsiya baribir majburiy.
- API javoblari no-store. HTML CSP inline scriptni, tashqi scriptni va framingni bloklaydi.
  Mijoz matnlari DOMga textContent orqali chiqadi.
- Kontakt, task va lead JSON private DB'da saqlanadi; DB backup va access siyosati
  production chiqarishda amaldagi talablar bilan tekshirilishi kerak.

## Aktivlashtirish

Bu flaglar sir emas. Hech qanday token browserga chiqarilmaydi.
Mavjud serverning amoCRM runtime autentifikatsiyasi ishlatiladi; yangi token nusxasi yo'q.

1. Testdan o'tgan kodni mavjud API release jarayoni orqali joylash.
2. Avval `OISHA_CRM_PARALLEL_ENABLED=1`,
   `OISHA_CRM_PARALLEL_WRITEBACK=0` bilan faqat o'qishni yoqish.
3. `OISHA_CRM_SELLER_MAP_JSON` ni haqiqiy Oisha subject → amoCRM user ID
   mappingi bilan sozlash. Besh sotuvchining identifikatorlari tasdiqlanmaguncha
   mappingni taxminan to'ldirmaslik.
4. API service'ni restart qilib startup/lifespan workerini tekshirish.
   Lokal userbot ishga tushirilmaydi.
5. Source/ichki yozuvlar, kontakt aloqalari, vazifalar, voronkalarni solishtirish.
   UI'dagi loaded_total source jami degani emas; joriy nusxadagi mos yozuvlar soni.
6. Aniq belgilangan sintetik bitimda tekshiruv, so'ng
   `OISHA_CRM_PARALLEL_WRITEBACK=1` bilan editni yoqish.
7. Yangi sahifadan nom/bosqich o'zgartirib, source va outbox read-back'ni
   tekshirish. Aloqa uzilishi, parallel edit va restartni ham tekshirish.
8. Rollback: writeback flagini 0 qilish, service restart, sending/uncertain
   operatsiyalarni read-back qilish. Flag o'chishi avval yuborilgan PATCHni bekor qilmaydi.

## Hali ko'chirishdan oldin tugatiladigan ishlar

- Yangi bitim/kontakt yaratish, vazifa tahriri va izoh yozish bu versiyada yo'q.
  Bu amallar amoCRM orqali davom etadi; keyin source ID'li alohida oqimlar qo'shiladi.
- O'chirishlar mirror qilinmaydi. Source'da o'chirilgan tarixiy yozuv nusxada qolishi
  mumkin. Read-before-write 404'ni conflictga aylantiradi, lekin deletion feed/tombstones
  qo'shilmaguncha barcha o'chirishlar aks etdi deb bo'lmaydi.
- Qo'ng'iroq audiosi va to'liq chat tarixi bu versiyada ko'chirilmaydi.
  Instagram, Telegram/WhatsApp, telefon, Meta, sayt va CAPI mavjud amoCRM oqimida qoladi.
- Izohlar source'dan so'nggi 50 ta qilib o'qiladi. Ular to'liq tarix eksporti emas.
  Vazifalarda ochiqlar birinchi; 100 dan ortiq bo'lsa cheklov ko'rsatiladi.
- API'da remote atomic compare-and-swap yo'q. GET va PATCH orasida boshqa
  tizim tahrir kiritsa tor race qoladi. Shu sababli pul, responsible va murakkab
  custom field'larni writeback qilish ochilmagan.
- Kunlik rescan yangi copy yaratadi, lekin backup/restore testi o'rnini bosmaydi.
- Mustaqil CRMga o'tishdan oldin source jamlari, aloqalar, maxsus maydonlar,
  tarix/audio, integratsiyalar, seller access va restore tekshiruvi yakunlanadi.
  amoCRM shundan keyingina o'chiriladi.

API kontrakti: [amoCRM bitimlar API](https://www.amocrm.ru/developers/content/crm_platform/leads-api),
[vazifalar API](https://www.amocrm.ru/developers/content/crm_platform/tasks-api).
