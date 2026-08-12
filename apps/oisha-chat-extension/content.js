// content.js
console.log("Oisha Telegram Chat Extension loaded.");

let currentPhone = null;
let currentChatId = null; // Telegram Chat ID if known

// Create the UI
function createChatUI() {
    // Inject the main panel
    const panel = document.createElement("div");
    panel.id = "oisha-chat-panel";
    
    panel.innerHTML = `
        <div id="oisha-chat-header">
            <div id="oisha-chat-header-title">
                <svg width="20" height="20" viewBox="0 0 24 24" fill="white"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm4.64 6.8c-.15 1.58-.8 5.42-1.13 7.19-.14.75-.42 1-.68 1.03-.58.05-1.02-.38-1.58-.75-.88-.58-1.38-.94-2.23-1.5-.99-.65-.35-1.01.22-1.59.15-.15 2.71-2.48 2.76-2.69a.2.2 0 00-.05-.18c-.06-.05-.14-.03-.21-.02-.09.02-1.49.95-4.22 2.79-.4.27-.76.41-1.08.4-.36-.01-1.04-.2-1.55-.37-.63-.2-1.12-.31-1.08-.66.02-.18.27-.36.74-.55 2.92-1.27 4.86-2.11 5.83-2.51 2.78-1.16 3.35-1.36 3.73-1.36.08 0 .27.02.39.12.1.08.13.19.14.27-.01.06.01.24 0 .24z"/></svg>
                Oisha Telegram
            </div>
            <div id="oisha-chat-toggle">−</div>
        </div>
        <div id="oisha-chat-messages">
            <div style="text-align:center; color:#888; font-size:12px; margin-top:20px;">Mijoz raqami qidirilmoqda...</div>
        </div>
        <div id="oisha-chat-input-area">
            <input type="text" id="oisha-chat-input" placeholder="Xabar yozing..." disabled />
            <button id="oisha-chat-send" disabled>
                <svg width="20" height="20" viewBox="0 0 24 24" fill="white"><path d="M2.01 21L23 12 2.01 3 2 10l15 2-15 2z"/></svg>
            </button>
        </div>
    `;
    document.body.appendChild(panel);

    // Inject minimized button
    const minimized = document.createElement("div");
    minimized.id = "oisha-chat-minimized";
    minimized.innerHTML = `<svg width="30" height="30" viewBox="0 0 24 24" fill="white"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm4.64 6.8c-.15 1.58-.8 5.42-1.13 7.19-.14.75-.42 1-.68 1.03-.58.05-1.02-.38-1.58-.75-.88-.58-1.38-.94-2.23-1.5-.99-.65-.35-1.01.22-1.59.15-.15 2.71-2.48 2.76-2.69a.2.2 0 00-.05-.18c-.06-.05-.14-.03-.21-.02-.09.02-1.49.95-4.22 2.79-.4.27-.76.41-1.08.4-.36-.01-1.04-.2-1.55-.37-.63-.2-1.12-.31-1.08-.66.02-.18.27-.36.74-.55 2.92-1.27 4.86-2.11 5.83-2.51 2.78-1.16 3.35-1.36 3.73-1.36.08 0 .27.02.39.12.1.08.13.19.14.27-.01.06.01.24 0 .24z"/></svg>`;
    document.body.appendChild(minimized);

    // Toggle Logic
    document.getElementById("oisha-chat-toggle").addEventListener("click", () => {
        panel.style.display = "none";
        minimized.style.display = "flex";
    });

    minimized.addEventListener("click", () => {
        minimized.style.display = "none";
        panel.style.display = "flex";
    });

    // Send Logic
    document.getElementById("oisha-chat-send").addEventListener("click", sendMessage);
    document.getElementById("oisha-chat-input").addEventListener("keypress", (e) => {
        if (e.key === "Enter") sendMessage();
    });
}

// Read phone number from AmoCRM DOM
function extractPhoneNumber() {
    // 1. Primary selectors (AmoCRM standard classes)
    const phoneEls = document.querySelectorAll('.js-control-phone .control-phone__formatted, a[href^="tel:"], input[name="PHONE"], .control-phone input, [data-pe-code="phone"] .control-phone__formatted');
    for (let el of phoneEls) {
        let val = el.value || el.innerText || (el.getAttribute("href") || "").replace("tel:", "");
        val = val.replace(/\D/g, ""); // Keep only digits
        if (val.length >= 9 && val.length <= 15) {
            return val;
        }
    }
    
    // 2. Fallback: Search in headers and titles (like "Звонок на +998...")
    const titleEls = document.querySelectorAll('h1, .card-entity-form__top-title, input.js-control-title, .feed-note__title, .js-card-entity-name, .card-entity-form__name');
    for (let el of titleEls) {
        let text = el.value || el.innerText || "";
        let match = text.match(/\+?\d{9,13}/);
        if (match) {
            let val = match[0].replace(/\D/g, "");
            if (val.length >= 9) return val;
        }
    }
    
    return null;
}

// Fetch history from background script
function fetchHistory(phone) {
    chrome.runtime.sendMessage({ action: "getHistory", phone: phone }, (response) => {
        const msgContainer = document.getElementById("oisha-chat-messages");
        const input = document.getElementById("oisha-chat-input");
        const sendBtn = document.getElementById("oisha-chat-send");
        
        if (response && response.success) {
            currentChatId = response.chatId;
            msgContainer.innerHTML = ""; // clear
            
            if (response.messages.length === 0) {
                msgContainer.innerHTML = `<div style="text-align:center; color:#888; font-size:12px; margin-top:20px;">Xabarlar topilmadi.</div>`;
            } else {
                response.messages.forEach(msg => {
                    appendMessage(msg.text, msg.outbound);
                });
            }
            
            // Enable inputs
            input.disabled = false;
            sendBtn.disabled = false;
        } else {
            msgContainer.innerHTML = `<div style="text-align:center; color:red; font-size:12px; margin-top:20px;">Xatolik: ${response ? response.error : "Backendga ulanib bo'lmadi."}</div>`;
        }
    });
}

function appendMessage(text, isOutbound) {
    const msgContainer = document.getElementById("oisha-chat-messages");
    const div = document.createElement("div");
    div.className = "oisha-msg " + (isOutbound ? "outbound" : "inbound");
    div.innerText = text;
    msgContainer.appendChild(div);
    msgContainer.scrollTop = msgContainer.scrollHeight;
}

function sendMessage() {
    const input = document.getElementById("oisha-chat-input");
    const text = input.value.trim();
    if (!text || !currentChatId) return;

    input.value = "";
    appendMessage(text, true); // optimistically append

    chrome.runtime.sendMessage({ 
        action: "sendMessage", 
        chatId: currentChatId, 
        text: text 
    }, (response) => {
        if (!response || !response.success) {
            alert("Xabar yuborishda xatolik: " + (response ? response.error : "Server xatosi"));
        }
    });
}

// Init
setTimeout(() => {
    createChatUI();
    
    // Poll for phone number (React app might load data late)
    let checks = 0;
    const interval = setInterval(() => {
        const phone = extractPhoneNumber();
        if (phone) {
            clearInterval(interval);
            currentPhone = phone;
            document.getElementById("oisha-chat-messages").innerHTML = `<div style="text-align:center; color:#888; font-size:12px; margin-top:20px;">Tarix yuklanmoqda... (${phone})</div>`;
            fetchHistory(phone);
        } else if (checks > 10) {
            clearInterval(interval);
            document.getElementById("oisha-chat-messages").innerHTML = `<div style="text-align:center; color:red; font-size:12px; margin-top:20px;">Mijoz telefon raqami topilmadi.</div>`;
        }
        checks++;
    }, 1000);
}, 2000);
