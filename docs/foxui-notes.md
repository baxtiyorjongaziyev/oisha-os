# FoxUI — Oisha-OS uchun qisqa qo'llanma

> Manba: https://foxui.dev, `llms.txt`, registry (`/r/*.json`), v0.99.8 (2026-10-27 holati).
> FoxUI — O'zbekistonda yaratilgan dizayn tizimi: 288 komponent, 377 token, oddiy HTML + CSS + kichik JS.

## Ulash (plain HTML)

```html
<link rel="stylesheet" href="https://foxui.dev/assets/foxui.css">
<script type="module" src="foxui/foxui.js"></script>  <!-- lokal nusxa, pastga qarang -->
<html data-fx-theme="amethyst">   <!-- amber|amethyst|emerald|graphite|hilos|ocean|pdp|rose|siyoh -->
```

> `foxui.css` hosted manzildan ishlaydi, lekin `https://foxui.dev/assets/foxui.js` boshqa domenda
> **ishlamaydi** (ES modul, CORS header yo'q). JS'ni CLI bilan lokal o'rnating. JS'siz grafiklar
> oddiy jadval bo'lib ko'rinadi, saralash ishlamaydi — qolgan hammasi CSS bilan ishlaydi.

CLI (Pro): `npx foxui init --theme amethyst --style round`, `npx foxui add chart datagrid`,
`npx foxui check` (tekshirish), `npx foxui mcp` (AI agent uchun MCP server).

> Litsenziya: obuna (Free / Pro $10 / Team $39). CSS/JS faylini repoga **ko'chirmang** —
> hosted manzildan ulang yoki Pro litsenziya bilan CLI orqali o'rnating.

## Qoidalar (FoxUI'ning o'zi talab qiladi)

1. Yangi UI yozishdan oldin tayyor komponentni qidiring (`/r/index.json`).
2. Rang/oraliq/radius — faqat `--fx-*` tokenlar.
3. Yozgandan keyin `npx foxui check` yoki MCP `validate_snippet`.

## Konventsiyalar

- Ildiz klass: `.fx-<nom>` (`.fx-card`, `.fx-stat`); qismlar BEM: `.fx-stat__value`.
- Variantlar klass bilan emas, atribut bilan: `data-variant`, `data-size`, `data-tone`
  (`success|warning|error|info`), `data-color` (`yellow|pink|blue|coral|green|purple`), `data-state`.
- Holat ko'pincha ARIA orqali: `aria-current="page"`, `aria-pressed`, `aria-busy` (skelet), `aria-sort`.
- JS kerak bo'lgan komponentlarda `data-fx-*` belgisi bor (`data-fx-table`, `data-fx-chart`, `data-fx-shell`).

## Tokenlar (namunalar)

`--fx-space-1…`, `--fx-radius-surface`, `--fx-bg-surface`, `--fx-text-primary|secondary`,
`--fx-elevation-0…5`, `--fx-viz-seq-1…7` / `--fx-viz-div-1…7` (grafik palitra),
`--fx-spring-*` (harakat), `--fx-bp-compact…xl` (breakpoint).

## Global rejimlar

| Atribut | Vazifa |
|---|---|
| `data-fx-motion="calm\|none"` | animatsiyani kamaytirish/o'chirish |
| `data-fx-contrast="more"` | yuqori kontrast |
| `data-fx-material="glass"` | shisha effekt (faqat overlay) |
| `data-fx-adaptive` | mobilda menyular bottom-sheet bo'ladi |

## Oisha uchun eng kerakli komponentlar

| Vazifa | Komponent | Markup |
|---|---|---|
| Ilova karkasi | shell + nav | `.fx-shell > .fx-shell__side > nav.fx-nav > a.fx-nav__item[aria-current]` |
| KPI | stat + delta | `.fx-stat > .fx-stat__label / __value / __hint`, `.fx-delta[data-dir=up][data-tone=good]` |
| Jadval | table / datagrid | `table.fx-table[data-fx-table]`, `th[aria-sort] > button.fx-table__sort`, `td[data-type=num]` |
| Holat | status / badge | `span.fx-status[data-tone]`, `span.fx-badge[data-tone][data-style=solid]` |
| Tugma | button | `button.fx-btn[data-variant=primary\|ghost\|danger\|tonal]`, `.fx-btn-group` |
| Grafik | chart | `figure.fx-chart[data-fx-chart][data-type=line\|bar\|donut\|spark] > table.fx-chart__data` |
| AI / tasdiqlash | composer, approval prompt, reasoning, tool-call card | Telegram MCP owner-approval oqimi uchun |
| Boshqa | kanban, gantt, audit log, timeline, command palette | — |

> Shell tuzilmasi qat'iy: `.fx-shell` ichida `aside.fx-shell__side`, `header.fx-shell__top`,
> `main.fx-shell__main` bo'lishi shart — aks holda grid buziladi va kontent ko'rinmay qoladi.

Grafiklar ma'lumotni oddiy `<table>` dan o'qiydi — backend faqat HTML jadval chiqarsa yetarli.

## Prototip

`prototypes/foxui/erp-dashboard.html` — ERP dashboard namunasi (shell, KPI, grafik, jadval).
Brauzerda to'g'ridan-to'g'ri oching; hozircha statik ma'lumot, faqat CSS ulangan (JS lokal o'rnatilgach ulanadi).
