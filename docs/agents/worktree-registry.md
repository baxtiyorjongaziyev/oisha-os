# Worktree reestri

Yagona markaz: o'chirilgan yoki saqlangan git worktree'lar qayerdaligi va ular ustidagi ishni qanday davom ettirish. Yangi worktree yaratilsa yoki o'chirilsa, shu yerga yoziladi. Faol qulflar `AGENTS.md` da; tugagan ish tarixi `handoff-log.md` da.

## Asosiy qoida

Ish papkada emas, branch'da saqlanadi. Worktree o'chirilsa ham branch va commitlar repoda qoladi. Qayta tiklash:

```
git worktree add <eski-yo'l> <branch>
```

Aynan eski yo'lga tiklansa, agentlarning shu papkaga bog'langan suhbat tarixi (Claude Code `~/.claude/projects/`, Codex, OpenCode) yana topiladi. Boshqa yo'lga tiklansa, kod bor, lekin eski suhbatni resume qilib bo'lmaydi.

## O'chirilgan (2026-11-06; tekshiruv: dirty=0, unpushed=0, main'ga merge qilingan)

| Eski yo'l | Branch | Oxirgi commit | Qayta tiklash |
|---|---|---|---|
| `C:/Users/baxti/AppData/Local/Temp/opencode/oisha-cal` | `main` (OpenCode vaqtinchalik) | 4ac62b3b, 2026-11-05, kalendar taklifi (#1005) | Kerak emas: `main` asosiy papkada bor. Yangi OpenCode ishi uchun yangi worktree oching. |
| `C:/Users/baxti/playground/oisha-os/.claude/worktrees/lead-egasiz-turibdi-417b8a` | `claude/telegram-bot-token-auth-06270b` | 40b88eed, 2026-11-05, openclaw gateway liveness test (#1010) | `git worktree add <yo'l> claude/telegram-bot-token-auth-06270b` |
| `C:/Users/baxti/playground/oisha-os/.claude/worktrees/reveo-website-ed1a6f` | `claude/remote-control-13c1de` | 40b88eed, 2026-11-05 (#1010) | `git worktree add <yo'l> claude/remote-control-13c1de` |

## Saqlangan (hali ish bor, o'chirilmagan)

| Yo'l | Branch | Nima uchun saqlandi |
|---|---|---|
| `C:/Users/baxti/playground/oisha-os` | `feat/amobot-daily-report-uzbek` | Asosiy ish papkasi. Telegram–amoCRM ko'prigi (`src/services/core/crm/tg_amo_bridge/`) shu yerda. |
| `.../.claude/worktrees/amocrmga-ulanganmisan-e4ce35` | `claude/amocrmga-ulanganmisan-e4ce35` | 1 ta merge qilinmagan commit: `feat(crm): daily stuck-stage lead report at 10:30` (d96d4706). |
| `C:/Users/baxti/Documents/Codex/2026-10-30/inspect-the-latest-failed-instagram-campaign/work/oisha-os` | `fix/instagram-get-timeout-retry` | 3 ta commit qilinmagan fayl; Codex ishi. |
| `C:/Users/baxti/playground/oisha-roster` | `fix/openclaw-gateway-test` | Alohida branch ustida ishlanayotgan worktree (nusxa emas). |
| `.../.claude/worktrees/charming-pasteur-c8d86f` | `claude/charming-pasteur-c8d86f` | Clean. Oxirgi commit c622cc47 (STT Gemini, #1021), main'ga merge qilingan. |
| `.../.claude/worktrees/oishani-architecture-audit-452904` | `feat/claude-code-action` | Clean. 2 ta CI commit (e5527d2e, 4fc2021a) — `main`/`development` ga merge qilinmagan. |
| `.../.claude/worktrees/oracle-free-tier-ssh-5520bd` | `claude/oracle-free-tier-ssh-5520bd` | Clean. Oxirgi commit b5aad43d (#1024), main'ga merge qilingan. |
| `C:/Users/baxti/playground/oisha-os-bridge` | `fix/gsheet-scopes-import` | Clean. da37ca16 `_GSHEET_SCOPES` fix; kontenti b5aad43d sifatida squash-merge qilingan, branch commitining o'zi main'da emas. |
| `C:/Users/baxti/playground/oisha-os_backup_` | `main` | Alohida eski klon, tarixi ajralgan (1127 oldinda / 1655 orqada, 793 o'zgargan fayl). Tekshirilmagan; o'chirmang. |

## Oisha bilan bog'liq, lekin alohida repolar (birlashtirilmaydi)

- `playground/jonbranding-web`, `projects/jonbranding-*` : veb-sayt va audit/PR papkalari.
- `playground/telegram-mcp` : tashqi repo `chigwell/telegram-mcp`, lokal sozlangan. Telethon 1.45.0 ga yangilangan (2026-11-06).
- `playground/salescoach-ai` : git remote yo'q; repodagi `salescoach-ai/` bilan farqi tekshirilmagan.
