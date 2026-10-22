# Davomat uchun mijoz IP tekshiruvi

Tekshiruv sanasi: 2026-10-22. Vazifa 1. Bu hujjat prod Wi-Fi belgilash sinovi muvaffaqiyatli o'tganini bildirmaydi.

## Tekshirilgan dalillar

- Repo `deploy/nginx-oisha.conf` faylining `/api/` blokida `X-Real-IP $remote_addr` va `X-Forwarded-For $proxy_add_x_forwarded_for` mavjud.
- [PR #936 deploy jurnali](https://github.com/baxtiyorjongaziyev/oisha-os/actions/runs/39749227796) 08:39:42 UTC da `/etc/nginx/sites-enabled/oisha.conf` ni ko'rsatgan. Undagi backendga yo'naltiruvchi bloklarda `X-Real-IP $remote_addr` bor. Bu diskdagi o'sha paytdagi konfiguratsiya dalili, hozir yuklangan konfiguratsiya dalili emas.
- Deploy `sites-available/oisha` ni yangilaydi, jurnal esa `sites-enabled/oisha.conf` ni ham ko'rsatadi. Faol symlink nishoni va HTTPS blokini tekshirmasdan repo faylini ko'chirish muammoni tuzatgan deb bo'lmaydi.
- `network.client_ip()` faqat loopback peer bergan sarlavhalarni oladi. Boshqa peer o'z IP manzili bilan tekshiriladi. Xususiy, buzilgan yoki yo'q IP rad etiladi.
- Lokal SSH urinishida host kaliti tekshiruvi o'tmadi. Ishonchli host kalitisiz tekshiruv o'chirilmadi. Prod'dagi joriy `nginx -T`, Caddy holati va HR endpoint javobi tekshirilmagan.

## Operator tekshiruvi

1. Ishonchli SSH kanalida `sudo nginx -T` orqali aynan `oisha.jonbranding.uz` HTTPS serveri, `/api/` location va upstreamni tekshiring. Maxfiy konfiguratsiyani chatga ko'chirmang.
2. Faol Nginx location mijoz bergan `X-Real-IP` ni `$remote_addr` bilan almashtirishi kerak. Uvicorn proxy middleware peer IP ni avval o'zgartirishi mumkinligini ham hisobga oling. Keng proxy trust ro'yxatini qo'shmang.
3. Ofis Wi-Fi ichida HR sessiyasi bilan `GET /api/attendance/admin/office-wifi` ni oching. `your_ip` haqiqiy ofis public IP siga mos kelishini tekshiring. VPN/mobil internetni o'chiring. IP ni ommaviy hisobotga yozmang.
4. `your_ip=null` yoki POST javobi `422 office_ip_unknown` bo'lsa, haqiqiy proxy zanjirini aniqlang. Faqat faol konfiguratsiyani zaxiralab, kerakli locationga yuqoridagi sarlavhalarni qo'shing; `sudo nginx -t` muvaffaqiyatidan so'ng reload qiling. SSH ishonch chegarasini bo'shatmang.
5. Owner ofisda "Ofis Wi-Fi'ni shu yerdan belgilash" ni bosadi. So'ng GET qayta o'qilib, saqlangan tarmoq va `you_are_on_office_wifi=true` tekshiriladi. Tugma bosilgani muvaffaqiyat isboti emas.
6. Tashqi tarmoqdan soxta `X-Real-IP` bilan yuborilgan xodim so'rovi ofis sifatida qabul qilinmasligini tekshiring. Haqiqiy davomatga sintetik belgi yozmang.

## Ochiq masala

`punch()` ofis tarmog'i hali sozlanmaganida `None` qabul qilib GPS bilan ishlaydi. Shu sabab "Wi-Fi majburiy" talabi faqat ofis tarmog'i ro'yxatga olingach bajariladi. Bu mavjud xatti-harakat; IP trust ushbu auditda o'zgartirilmadi. Ishga tushirishdan oldin owner ofis Wi-Fi'sini belgilashi zarur.
