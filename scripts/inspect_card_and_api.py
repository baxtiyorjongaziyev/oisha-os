switch_tab("27C7253C87FD42DFAABD934CBB0B80D1")
import json

res = js("""(() => {
    // 1. Find cards with id or clickable attributes
    const cards = Array.from(document.querySelectorAll('*')).filter(el => {
        return el.innerText && el.innerText.includes('#jo_') && el.children.length > 2;
    });

    const sampleCard = cards[0];
    let cardInfo = null;
    if (sampleCard) {
        cardInfo = {
            tagName: sampleCard.tagName,
            className: sampleCard.className,
            innerHTML: sampleCard.innerHTML.substring(0, 500),
            attributes: Array.from(sampleCard.attributes).map(a => ({ name: a.name, value: a.value }))
        };
    }

    // 2. Check all script tags to see endpoints
    const scriptSrcs = Array.from(document.querySelectorAll('script')).map(s => s.src).filter(Boolean);

    // 3. Check for API token and perform a test fetch to common endpoints
    const token = localStorage.getItem('awp_token');
    
    return {
        cardsFound: cards.length,
        sampleCard: cardInfo,
        scriptSrcs: scriptSrcs,
        hasToken: !!token
    };
})()""")

print(json.dumps(res, indent=2, ensure_ascii=False))
