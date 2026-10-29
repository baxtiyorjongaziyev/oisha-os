tabs = list_tabs()
print("All open tabs:")
for t in tabs:
    print(f" - [{t.get('targetId') or t.get('target_id')}] {t.get('title')} -> {t.get('url')}")

# 1. Switch to Google AI Studio tab
ai_tab = next((t for t in tabs if "aistudio.google.com" in (t.get("url") or "")), None)
if ai_tab:
    tid = ai_tab.get("targetId") or ai_tab.get("target_id")
    print(f"\nSwitching to AI Studio tab: {tid}")
    switch_tab(tid)
    wait_for_load()
    import time
    time.sleep(2)
    print("Page title:", js("document.title"))
    print("Current URL:", js("window.location.href"))
    
    # Check for API key rows or buttons
    elements = js("""
    (() => {
        const textElements = Array.from(document.querySelectorAll('button, a, tr, div')).map(el => {
            const txt = (el.innerText || '').trim();
            const aria = el.getAttribute('aria-label') || '';
            return { tag: el.tagName, text: txt.slice(0, 100), aria };
        }).filter(e => e.text.includes('API') || e.text.includes('Key') || e.aria.includes('Key') || e.text.includes('Create') || e.text.includes('Get'));
        return textElements.slice(0, 30);
    })()
    """)
    import json
    print("AI Studio elements:\n", json.dumps(elements, indent=2))
else:
    print("AI Studio tab not found, creating new tab...")
    new_tab("https://aistudio.google.com/app/apikey")
