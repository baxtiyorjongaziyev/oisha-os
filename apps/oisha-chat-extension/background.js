// background.js
const API_BASE = "https://oisha.jonbranding.uz/api/telegram/extension";
// const API_BASE = "http://127.0.0.1:8765/api/telegram/extension"; // For local testing

chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
    if (request.action === "getHistory") {
        fetch(`${API_BASE}/history?phone=${request.phone}`)
            .then(res => res.json())
            .then(data => {
                sendResponse(data);
            })
            .catch(err => {
                console.error("History fetch error:", err);
                sendResponse({ success: false, error: err.toString() });
            });
        return true; // Keep message channel open for async response
    }
    
    if (request.action === "sendMessage") {
        fetch(`${API_BASE}/send`, {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify({
                chat_id: request.chatId,
                text: request.text
            })
        })
            .then(res => res.json())
            .then(data => {
                sendResponse(data);
            })
            .catch(err => {
                console.error("Send message error:", err);
                sendResponse({ success: false, error: err.toString() });
            });
        return true;
    }
});
