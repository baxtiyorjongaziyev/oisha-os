# Third-party agent skills

Upstream skill'lar shu papkaga **o'zgarishsiz** (verbatim) ko'chirilgan, 2026-10-03.
Qaysi vosita qayerdan o'qiydi:

| Vosita | Papka |
|---|---|
| Claude Code | `.claude/skills/` (manba — faqat shu yerda tahrirlang) |
| Codex | `.agents/skills/` (`$skill-nomi` bilan chaqiriladi) |
| Antigravity | `.agents/skills/` (eski `.agent/skills/` ham qo'llab-quvvatlanadi) |
| Cursor | ikkalasi ham |

`.agents/skills/` — `.claude/skills/` ning haqiqiy nusxasi (symlink emas: Windows'da git symlink'ni
matn faylga aylantiradi). O'zgartirgandan keyin: `python scripts/sync_agent_skills.py`.
`tests/test_agent_skills_sync.py` nusxa eskirsa CI'ni qizil qiladi. `.claude/agents/poteto-agent.md`
faqat Claude Code uchun (Codex/Antigravity subagent formati boshqa).

Har bir skill papkasida `LICENSE.upstream` bor. Yangilash: upstream repo'ni shu commit'dan
keyingisiga `git clone --depth 1` qilib, papkani qayta ko'chiring va diff'ni o'qing.

| Skill papka(lar)i | Upstream | Commit | Litsenziya | Ishga tushirish |
|---|---|---|---|---|
| `caveman`, `ultracave`, `megacave` | [JuliusBrussee/caveman](https://github.com/JuliusBrussee/caveman) `skills/` | `aeb45e2` | MIT | `/caveman` (`lite`/`full`/`ultra`), `/caveman ultra`, `/caveman wenyan`; to'xtatish: "stop caveman" |
| `poteto-mode`, `principle-*` (24), `how`, `why`, `architect`, `swarm`, `arena`, `interrogate`, `unslop`, `technical-writing`, `no-comments`, `benchmark-checklist`, `show-me-your-work`, `figure-it-out`, `reflect`, `setup-pstack`; `../agents/poteto-agent.md` | [cursor/plugins](https://github.com/cursor/plugins) `pstack/` (Lauren Tan, "poteto") | `23e4138` | MIT | `/poteto-mode` (sozlash: `/setup-pstack`) |
| `vibe-security` | [raroque/vibe-security-skill](https://github.com/raroque/vibe-security-skill) | `850938f` | MIT | `/vibe-security` yoki "audit this for security" |
| `no-ai-slop` | [petergyang/no-ai-slop](https://github.com/petergyang/no-ai-slop) `skills/` | `000650b` | MIT | `/no-ai-slop` + matn |
| `ponytail` | [DietrichGebert/ponytail](https://github.com/DietrichGebert/ponytail) `skills/` | `c982cd4` | MIT | `/ponytail` (`lite`/`full`/`ultra`); to'xtatish: "stop ponytail" |
| `mattpocock-code-review`, `implement`, `tdd`, `setup-matt-pocock-skills` | [mattpocock/skills](https://github.com/mattpocock/skills) `skills/engineering/` | `d81f3a1` | MIT | Avval bir marta `/setup-matt-pocock-skills`; keyin `/mattpocock-code-review main`, `/implement`, `/tdd` |
| `hyperframes`, `hyperframes-core`, `-cli`, `-animation`, `-audio`, `-creative`, `-keyframes`, `-registry`, `-studio` | [heygen-com/hyperframes](https://github.com/heygen-com/hyperframes) `skills/` | `8c81efb` | Apache-2.0 | `/hyperframes` (Node + `npx hyperframes` kerak) |
| `design-taste-frontend` | [Leonxlnx/taste-skill](https://github.com/Leonxlnx/taste-skill) `skills/taste-skill/` | `ce26fc2` | MIT | `/design-taste-frontend` |
| `impeccable` | [pbakaus/impeccable](https://github.com/pbakaus/impeccable) `.claude/skills/impeccable/` | `e103efe` | Apache-2.0 | `/impeccable audit <target>`, `/impeccable polish`, va h.k. |
| `autoresearch` | [uditgoenka/autoresearch](https://github.com/uditgoenka/autoresearch) `.claude/skills/autoresearch/` | `050e30d` | MIT | `/autoresearch` (Metric/Verify bilan), `/autoresearch:debug`, `:fix`, `:security` |
| `unlazy` | [Leonxlnx/unlazy](https://github.com/Leonxlnx/unlazy) | `1667149` | MIT | `/unlazy`, "tree N", "gates" |

## Mahalliy o'zgarishlar (verbatim'dan farqi)

- `mattpocock-code-review/SKILL.md`: `name: code-review` → `name: mattpocock-code-review`.
  Sabab: Claude Code'ning o'zida `/code-review` bor; nom to'qnashuvi bo'lmasin. Papka nomi ham shunga mos.
- `../agents/poteto-agent.md`: `tools:` ro'yxati qo'shildi (MCP vositalarisiz). Sabab: cheklovsiz
  background subagent Telegram/AmoCRM MCP mutatsiyalarini meros qilib olardi; repo qoidasi ularni
  faqat owner tasdig'i bilan ruxsat etadi.
- pstack'ning `tdd` skill'i o'rnatilmagan: `implement` chaqiradigan Matt Pocock `tdd` bilan nomi bir xil.
- Upstream testlari (`tests/`, `*.test.ts`), `.github/` va unlazy'ning `research/`, `CHANGELOG.md`, `CONTRIBUTING.md` fayllari ko'chirilmagan.

## Repo qoidalari ustun

Bu skill'lar `CLAUDE.md` / `AGENTS.md` ni bekor qilmaydi. Ziddiyat bo'lsa repo qoidasi yutadi, masalan:
- Faqat `pnpm` (taste-skill'dagi `npm install` misollari o'rniga).
- poteto-mode'ning "Just do it / any MCP tool" avtonomiyasi Telegram/AmoCRM mutatsiyalariga
  taalluqli emas: ular owner tasdig'i va quiet-hours gate'laridan o'tadi.
- Hook o'rnatuvchi skriptlar (`unlazy/scripts/install-hooks.mjs`, `/impeccable hooks on`) faqat Owner roziligi bilan.
- `impeccable/scripts/impeccable` birinchi ishga tushishda o'z GitHub release'idan binar yuklaydi (sha256 tekshiruvi bilan).

## O'rnatilmaganlar

- **Open Design** ([nexu-io/open-design](https://github.com/nexu-io/open-design)) — skill emas, alohida
  desktop/web ilova (local daemon + SQLite). Uning `.claude/skills/` ichida faqat `od-contribute`
  (Open Design'ning o'z reposiga hissa qo'shish uchun) bor. Ilova sifatida alohida o'rnatiladi.
