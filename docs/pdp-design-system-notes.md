# PDP Design System — Oisha-OS uchun qisqa qo'llanma

> Manba: https://design.pdp.uz (`/llms.txt`, `/ds/ai/task/web-app.md`, `/ds/ai/CLAUDE.md`), DS v0.15.108,
> paket `@pdp/design-system@0.15.105` (2026-10-27 holati).
> PDP ekotizimining dizayn tizimi: 6 brend (EcoSystem, Academy, School, University, Online, Junior),
> bitta umumiy token/komponent to'plami, vazifaga qarab "kit"larga bo'lingan.

## AI uchun kirish nuqtasi

FoxUI'dan farqli o'laroq, PDP AI agentlar uchun maxsus yozilgan:

- Router: https://design.pdp.uz/llms.txt — vazifaga mos **bitta** task guide'ni tanlaysiz.
- ERP/CRM/dashboard uchun: https://design.pdp.uz/ds/ai/task/web-app.md
- Grafiklar (30 punktli tekshiruv): https://design.pdp.uz/ds/ai/task/dashboard-charts.md
- Barcha retseptlar: https://design.pdp.uz/ds/ai/index.md, bittasi: `https://design.pdp.uz/ds/ai/r/<nom>.md`
- Repo uchun tayyor CLAUDE.md bo'lagi: https://design.pdp.uz/ds/ai/CLAUDE.md

## Ulash

```html
<html lang="uz" data-brand="ecosystem" data-theme="light">
<link rel="stylesheet" href="https://design.pdp.uz/ds/fonts/fonts.css">
<link rel="stylesheet" href="https://design.pdp.uz/ds/tokens/ecosystem.css">
<link rel="stylesheet" href="https://design.pdp.uz/ds/css/v0.15.105/pdp-base.css">
<link rel="stylesheet" href="https://design.pdp.uz/ds/css/v0.15.105/pdp-components.css">
<script defer src="https://design.pdp.uz/ds/css/v0.15.105/pdp-components.js"></script>
```

- Versiyani **pin** qiling (`/v0.15.105/`); `/ds/css/` — "latest", faqat sinash uchun. npm: `@pdp/design-system@0.15.105`.
- CSS/JS'ni repoga ko'chirmang — PDP qoidasi.
- `pdp-components.js` (oddiy script, `window.PDPUI`) boshqa domendan **ishlaydi**: menyular, filtr, qator tanlash,
  shell yig'ish (Ctrl/⌘+B), kalendar, grafiklar (`[data-eco-chart]`). U faqat UI holatini boshqaradi;
  ma'lumotni siz `eco:select`, `eco:filter`, `eco:lp-sort`, `eco:lp-page` … eventlari orqali yuklaysiz.
  SPA'da qatorlarni qayta chizgandan keyin `window.PDPUI.refresh(root)`.
- **Cheklovlar (tekshirildi):** ikonka sprite (`/ds/icons/pdp-icons.svg`) va shriftlar (woff2) CORS bermaydi —
  boshqa domendan ikonka ko'rinmaydi, shrift fallback'ga tushadi. Productionda spriteni o'z serverdan inline qiling
  (`<svg><use href="#i-<nom>"/></svg>`).

## Qat'iy qoidalar

1. Komponent o'ylab topilmaydi — faqat retseptdan. Yo'q bo'lsa eng yaqinini oling va `<!-- PDP-DS: missing <nima> -->` qo'ying.
2. Faqat paketda bor klasslar (`eco-*`). Retseptda "demo-only" deb belgilangan klasslarning CSS'i yo'q.
3. HEX/rgb/hsl yo'q, o'z gradient/soyangiz yo'q — faqat `var(--eco-*)` tokenlar.
4. Ikonkalar faqat PDP sprite'dan (`i-*`), emoji yo'q.
5. Har ekranda bitta primary tugma; har ro'yxat/jadvalda loading (skeleton), empty, error holatlari.
6. Matn o'zbek (lotin), `o‘`/`g‘` da ‘ (U+2018); sana `DD.MM.YYYY`; pul `1 200 000 so‘m`.
7. Mahsulot UI uchun Brandbook, SMM, Print, Slides kitlaridan olinmaydi.

## Brend va tema

- ERP/CRM/admin → `data-brand="ecosystem"`; `data-theme="light"` (dark ham shu tokenlar bilan).
- Tokenlar: `/ds/tokens/<brend>.css`, JSON: `/ds/tokens/ecosystem.json`.

## Asosiy bloklar (ERP)

| Vazifa | Klass / retsept |
|---|---|
| Ilova karkasi (S3 rail + panel) | `.eco-shell.eco-shell--deep.eco-shell--rail` → `__rail`, `__side`, `__main > __head` — `page-shell-live.md` |
| Yon menyu | `a.eco-nav-item[aria-current=page]`, `.eco-nav-item__count`, guruhlar `.eco-shell__section` |
| Tepa panel | `.eco-shell__head`: toggle, `.eco-shell__crumb`, KPI pill `.eco-stat` |
| Bosh sahifa | `.eco-overview` → `__head`, `__grid`, `__card`, `__hero`, `__big` — `overview-live.md` |
| Ro'yxat sahifasi | `.eco-listpage` (`data-lp-*`) — `listpage-live.md` |
| Jadval | `.eco-table-card`, toolbar, `.eco-bulkbar` — `datatable-demo.md` |
| Grafik | `<div class="eco-chart" data-eco-chart='{"type":"line","x":[…],"series":[…]}'>` — JSON bilan |
| Tugma | `.eco-btn eco-btn--primary\|secondary\|tertiary\|ghost`, `--sm`, `--icon` |
| Holat (jadvalda) | `.eco-status eco-status--success\|warning\|error\|neutral` (shakl + rang + so'z) |
| Holat (alohida) | `.eco-badge eco-badge--success eco-badge--dot` |

**Holat lug'ati** (o'zingiz rang o'ylab topmang): Faol, To‘langan, Bajarildi → success; Kutilmoqda → pending (soat ikonkasi);
Tekshiruvda, To‘lov kutilmoqda, Muddati yaqin → warning; Bekor qilindi, Muddati o‘tgan → error;
Yakunlangan, Qoralama, Nofaol, Arxiv → neutral. Bitta ustunda `.eco-status` va `.eco-badge` aralashtirilmaydi.

## FoxUI bilan solishtirish

| | FoxUI | PDP DS |
|---|---|---|
| Litsenziya | Bepul foydalanish ochiq (Free tarif; Pro — qo'shimcha) | Bepul, ochiq CDN (pinned) |
| JS boshqa domendan | Ishlamaydi (ES modul, CORS yo'q) | Ishlaydi (oddiy script) |
| Grafiklar | `<table>` dan | JSON atributdan, tooltip + klaviatura bilan |
| AI qo'llanma | `llms.txt` + MCP (Pro) | `llms.txt` + task guide + har blokka retsept |
| Brend | Neytral, 16 tema | PDP brendlari (6 ta) — **boshqa kompaniyaning brendi** |

> Ikkala tizim ham bepul foydalanishga ochiq (egasi tasdiqlagan, 2026-10-27). PDP'ning brend belgilari
> (logo, `mark-*`) o'rniga Oisha/Jon Branding nomi va belgisini qo'ying — tokenlar va komponentlar qoladi.

## Prototip

`prototypes/pdp/erp-direktor.html` — "Direktor paneli" (S3 rail shell + overview), PDP'ning `page-shell-live.md`
retseptidan, matnlar Oisha'ga moslangan, raqamlar demo. Grafik va menyular ishlaydi; ikonkalar CORS sababli ko'rinmaydi.

## Oisha ERP ranglari (egasi tasdiqlagan, 2026-10-27)

| Rang | Ulush | Qayerda |
|---|---|---|
| Oq `#FFFFFF` | 60% | fon, kartalar, panel |
| Qora `#111111` | 30% | matn, rail, asosiy (primary) tugma |
| Ko'k `#1D4ED8` | 10% | aksent: tanlangan menyu, havola, fokus, grafik chizig'i |
| Signal | qolgani | faqat holat: success (yashil), warning (sariq), error (qizil) — PDP'dan o'zgarishsiz |

Amalga oshirish: `prototypes/pdp/oisha-theme.css` — PDP `--eco-*` tokenlarini ustidan yozadi,
`pdp-components.css` dan **keyin** ulanadi. Yangi rang kerak bo'lsa — faqat shu faylga, sahifalarda HEX yozilmaydi.
Ko'k bezak emas: bir ekranda ko'k elementlar 10% dan oshmasin; yashil faqat "yaxshi holat" ma'nosida.
