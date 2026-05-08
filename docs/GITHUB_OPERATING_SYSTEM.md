# GitHub Operating System

Bu repo GitHubni faqat kod saqlash uchun emas, loyiha boshqaruvi uchun ham ishlatadi.

## Kundalik oqim

1. Har bir muammo yoki yangi funksiya `Issue` bo'ladi.
2. Har bir kod o'zgarishi alohida branch va `Pull Request` orqali yuradi.
3. `Actions` test, security scan va deployni tekshiradi.
4. `Projects` ishlarni `Backlog`, `Ready`, `In Progress`, `Review`, `Done` ustunlarida boshqaradi.
5. `Security and quality` Dependabot, CodeQL va secret scanning orqali xavfni ko'rsatadi.
6. Stable holatlar `Release` qilib belgilanadi.

## Label standarti

- `Type:*` - ish turi.
- `Prio:*` - muhimlik.
- `Proj:*` - qaysi modulga tegishli.
- `Status:*` - ish holati.

## Branch standarti

- `codex/<qisqa-vazifa>` - Codex qilgan ishlar.
- `claude/<qisqa-vazifa>` - Claude qilgan ishlar.
- `hotfix/<qisqa-xato>` - production xatolari.

## Pull Request qoidasi

- PR kichik bo'lsin.
- Test va rollback yozilsin.
- Production deploy faqat health checkdan o'tgandan keyin.
- Secret, token, 2FA, session string PR ichida bo'lmasin.

## GitHub imkoniyatlari bo'yicha foydalanish

- `Issues`: real biznes muammo yoki texnik bug yoziladi.
- `Pull requests`: kod review va CI natijasi shu yerda ko'riladi.
- `Actions`: test, deploy, security scan, userbot deploy.
- `Projects`: ishlarni haftalik sprint bo'yicha boshqarish.
- `Security`: Dependabot, CodeQL, secret scanning.
- `Releases`: muhim stable versiyalar.
- `Discussions`: katta g'oyalar va qarorlar uchun.
- `Insights`: commit/activity va ishlash ritmini ko'rish.

