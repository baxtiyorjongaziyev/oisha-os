switch_tab("27C7253C87FD42DFAABD934CBB0B80D1")
import json

res = js("""(() => {
    // 1. Get basic info
    const info = {
        title: document.title,
        url: window.location.href,
        columns: [],
        deals: [],
        scripts: [],
        links: []
    };

    // 2. Check for kanban columns and cards
    const colEls = document.querySelectorAll('.kanban-col, .kanban-column, [data-status], .column, [class*="column"], [class*="stage"]');
    colEls.forEach(c => {
        info.columns.push({
            className: c.className,
            textSnippet: c.innerText.substring(0, 100).replace(/\\n/g, ' ')
        });
    });

    // 3. Check deals / cards
    const cardEls = document.querySelectorAll('.kanban-card, .card, [class*="card"], [class*="lead"], [class*="item"]');
    info.totalCardsFound = cardEls.length;
    cardEls.forEach((card, idx) => {
        if (idx < 10) {
            info.deals.push({
                className: card.className,
                text: card.innerText.substring(0, 150).replace(/\\n/g, ' | ')
            });
        }
    });

    // 4. Check for any audio elements or links
    const audios = document.querySelectorAll('audio, [src*=".mp3"], [src*=".wav"], [href*=".mp3"], [href*=".wav"], [class*="audio"], [class*="record"], [class*="call"]');
    info.audioElementsFound = audios.length;

    // 5. Check localStorage keys (names only, not secrets)
    info.localStorageKeys = Object.keys(localStorage);

    // 6. Text snippet of document body
    info.bodySnippet = document.body.innerText.substring(0, 1500);

    return info;
})()""")

print(json.dumps(res, indent=2, ensure_ascii=False))
