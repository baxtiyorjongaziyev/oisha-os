tabs = list_tabs()
tg_tab = next((t for t in tabs if "web.telegram.org" in (t.get("url") or "")), None)
if tg_tab:
    tid = tg_tab.get("targetId") or tg_tab.get("target_id")
    print(f"Switching to Telegram tab: {tid}")
    switch_tab(tid)
    wait_for_load()
    import time
    time.sleep(1)
    
    # Navigate within telegram to BotFather
    print("Navigating to BotFather...")
    js("window.location.hash = '#@BotFather'")
    time.sleep(3)
    
    # Read the latest messages in BotFather chat
    msgs = js("""
    (() => {
        const bubbles = Array.from(document.querySelectorAll('.message-content, .text-content, .bubble-content'));
        return bubbles.slice(-10).map(b => b.innerText.trim()).filter(Boolean);
    })()
    """)
    print(f"Found {len(msgs)} messages in BotFather chat.")
    for m in msgs:
        # Check if message contains token pattern without printing the full token
        lines = m.split('\\n')
        for l in lines:
            if 'token to access' in l.lower() or 'api:' in l.lower() or 'jonairobot' in l.lower():
                print("Matched line in BotFather:", l[:35] + "...")
else:
    print("Telegram tab not found!")
