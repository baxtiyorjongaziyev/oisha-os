# Claude + Obsidian + NotebookLM — Workflow

## Sessiya boshida Claude nima qiladi

1. `docs/context/SESSION_CONTEXT.md` o'qiydi — joriy holat
2. Kerakli fayllarnigina o'qiydi (hammani emas)
3. Kontekstni conversationdan emas, fayldan oladi → **token tejaldi**

## Sessiya oxirida Claude nima qiladi

1. `SESSION_CONTEXT.md` yangilaydi (yangi holat, tugallangan tasklar)
2. Muhim qarorlarni yozadi
3. Keyingi session uchun pending tasklar qoldiradi

## Obsidian sozlash

Obsidian → Open Folder as Vault → `oisha-os/docs/` tanlang

Kerakli pluginlar:
- **Dataview** — task va status tracking
- **Git** — auto sync with repo

## NotebookLM sozlash

1. `docs/context/NOTEBOOKLM_EXPORT.md` ni yuklab oling
2. NotebookLM → New notebook → Add source → faylni yuklang
3. Yangi bilim qo'shilganda Claude `NOTEBOOKLM_EXPORT.md` ni yangilaydi

## Qoida

> Agar ma'lumot `SESSION_CONTEXT.md` da bo'lsa — Claude uni conversation da qaytamaydi.
> Bu token tejash uchun.
