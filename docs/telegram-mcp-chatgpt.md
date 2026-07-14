# Oisha Telegram MCP — ChatGPT ulanishi

## Xavfsizlik modeli

- O‘qish va qidirish amallari avtomatik bajariladi.
- Xabar yuborish, tahrirlash, o‘chirish va boshqa Telegram o‘zgarishlari egadan tasdiq kutadi.
- Tasdiq Oisha botidagi **Tasdiqlash** yoki **Bekor qilish** tugmasi orqali beriladi.
- Upstream va gateway faqat Oracle VM ichidagi loopback manzillarida ishlaydi.
- Nginx orqali 8765 yoki 8766 portlarini internetga ochmang.

## Kerakli environment nomlari


```env
TELEGRAM_MCP_ENABLED=true
TELEGRAM_MCP_SESSION_STRING=<alohida Telethon StringSession>
TELEGRAM_MCP_UPSTREAM_URL=http://127.0.0.1:8765/mcp
TELEGRAM_MCP_APPROVAL_TTL_SECONDS=900
```


`TELEGRAM_MCP_SESSION_STRING` va `USERBOT_SESSION_STRING` bir xil bo‘lmasligi shart. Qiymatlarni GitHub, log yoki chatga joylamang.

## O‘rnatish


```bash
cd /home/ubuntu/oisha-os
./venv/bin/pip install -r requirements.txt
sudo bash deploy/install_telegram_mcp.sh
```

## Tekshirish


```bash
systemctl is-active telegram-mcp-upstream.service
systemctl is-active oisha-telegram-mcp-gateway.service
ss -ltnp | grep -E '127.0.0.1:(8765|8766)'
curl -i http://127.0.0.1:8766/mcp
```

Ikkala port ham faqat `127.0.0.1`da tinglashi kerak.

## ChatGPT Secure MCP Tunnel

ChatGPT’dagi yangi plugin oynasida **Tunnel**ni tanlang va tunnel ko‘rsatmasidagi lokal MCP URL sifatida:


```text
http://127.0.0.1:8766/mcp
```

manzilidan foydalaning. To‘g‘ridan-to‘g‘ri `/telegram-mcp/sse` yoki 8765 portini kiritmang.

## Smoke test

1. `list_chats` — tasdiqsiz natija qaytarishi kerak.
2. Saved Messages’ga test xabari — `pending_approval` qaytarishi kerak.
3. Telegram’dagi **Tasdiqlash** bosilgandan keyin xabar bir marta ketishi kerak.
4. O‘sha test xabarini o‘chirish ham alohida tasdiq talab qilishi kerak.

## Rollback


```bash
sudo systemctl disable --now oisha-telegram-mcp-gateway.service
sudo systemctl disable --now telegram-mcp-upstream.service
```

So‘ng Telegram → Settings → Devices orqali faqat yangi MCP qurilma sessionini bekor qiling. Production Oisha userbot qurilmasiga tegmang.
