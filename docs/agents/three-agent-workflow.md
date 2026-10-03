# Uch agent bilan ishlash tartibi

2026-10-02. Hozir VS Code ichida ochilgan Oisha OS uchun tayyorlandi.

## Rollar

- Codex: implementer. Bitta aniq task, cheklangan scope, kod va tegishli tekshiruvlar.
- Claude Code: reviewer. Kodni o'zgartirmasdan diff, regressiya, xavfsizlik va test dalillarini tekshiradi. Plan mode'da boshlaydi.
- Antigravity: analyst. Talab, arxitektura, UI va tekshiruv ssenariylarini tayyorlaydi. Implementer tugamaguncha shu fayllarga yozmaydi.

Rollar model sifati reytingi emas; taskga qarab almashtiriladi. Uchala agent avtomatik bir-birining chatini ko'rmaydi. Ushbu hujjat tashkiliy qoida; universal texnik yozish qulfi emas.

## Har bir task

1. AGENTS.md, CLAUDE.md, docs/oisha-prd.md va tegishli docs/agents/ qoidalarini o'qi. GEMINI.md dagi eski stack/status uchun yangi manbalarni tekshir.
2. Muammo, qabul mezoni, o'zgarishi mumkin bo'lgan fayllar va tekshiruvni yoz.
3. git status va mavjud Locks'ni tekshir. Boshqa agentning o'zgarishini saqla. Kichik feat/ yoki fix/ branch ishlat; main'ga bevosita push qilma.
4. Bir checkoutda faqat bitta implementer yozadi. Ikkinchi mustaqil implementer kerak bo'lsa, alohida Git worktree va branch yarat; har worktree alohida VS Code oynasida ochiladi. Worktree'ga .env va Telegram session ko'chirma.
5. Eng kichik yetarli o'zgarishni qil. Tegishli test/lint/build o'tkaz; PR uchun repo pre-flight'ini ham bajar. Lokal test production ishlashini isbotlamaydi.
6. Reviewer aniq file/line, muammo va ta'sir bilan qaytadi. Implementer tuzatadi va zarur tekshiruvni takrorlaydi.
7. docs/agents/handoff-log.md oxiriga task, branch, o'zgargan fayllar, buyruqlar/natija va ochiq ishlarni yoz. Lock'ni bo'shat.

RTK bilan shell buyruqlarini boshlang. Sirlarni o'qimang va chat/logga yozmang. Lokal userbotni ishga tushirmang. Deploy, merge va tashqi tizim mutatsiyalarida repo owner qoidalariga amal qiling.

## Boshlang'ich promptlar

Codex: AGENTS.md va docs/agents/three-agent-workflow.md ni o'qi. Sen ushbu taskning yagona implementerisan. Task: <vazifa>. Qabul mezoni: <natija>. Scope: <fayllar>. Holatni tekshir, kichik patch qil, tegishli tekshiruv o'tkaz va handoff yoz.

Claude: AGENTS.md va docs/agents/three-agent-workflow.md ni o'qi. Faqat review qil, fayllarni o'zgartirma. Task: <vazifa>. Diff va handoffni tekshir. Aniq regressiya, xavfsizlik yoki test bo'shlig'ini file/line va dalil bilan ber. Muammo topilmasa shuni ayt.

Antigravity: AGENTS.md va docs/agents/three-agent-workflow.md ni o'qi. Task: <vazifa>. Hozir faqat tahlil qil, fayllarni o'zgartirma. Talab, minimal yechim, risk va qabul ssenariylarini ber. Brauzer tekshiruvi tashqi yozuv yoki xabar yuborishni talab qilsa owner qoidasiga amal qil.

## VS Code tugmalari

- Ctrl+Alt+1: Codex
- Ctrl+Alt+2: Claude Code
- Ctrl+Alt+3: rasmiy Google Antigravity

Workspace watcher/search node_modules, .venv, cache va build fayllarini chetlab o'tadi. Auto Save o'chirilgan; diffni tekshirish osonroq. Claude yangi chatlari Plan mode'da boshlaydi. Antigravity yangi xabar yuborilganda pending editlarni avtomatik qabul qilmaydi.

Rasmiy extensionlar: openai.chatgpt, anthropic.claude-code, google.google-antigravity. Boshqa AI extensionlar o'chirilmagan. Account login va real chat javobi shu sozlash davomida tekshirilmagan.
