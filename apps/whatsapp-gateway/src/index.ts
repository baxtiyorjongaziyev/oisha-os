import makeWASocket, {
  DisconnectReason,
  fetchLatestBaileysVersion,
  makeCacheableSignalKeyStore,
  makeInMemoryStore,
  useMultiFileAuthState,
  WAMessageContent,
  proto,
} from "@whiskeysockets/baileys";
import { Boom } from "@hapi/boom";
import express, { Request, Response } from "express";
import axios from "axios";
import qrcode from "qrcode-terminal";
import pino from "pino";
import * as fs from "fs";
import * as path from "path";
import { fileURLToPath } from "url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));

const logger = pino({ level: "silent" });

// Config (env orqali)
const OISHA_WEBHOOK_URL = process.env.OISHA_WEBHOOK_URL || "http://localhost:8000/webhook/whatsapp";
const OISHA_SECRET = process.env.OISHA_WHATSAPP_SECRET || "secret";
const PORT = parseInt(process.env.WA_GATEWAY_PORT || "3001");
const AUTH_DIR = process.env.WA_AUTH_DIR || path.join(__dirname, "..", "wa_auth_state");

// In-memory store (message history uchun)
const store = makeInMemoryStore({ logger });

let sock: ReturnType<typeof makeWASocket> | null = null;
let isConnected = false;

async function connectToWhatsApp() {
  const { state, saveCreds } = await useMultiFileAuthState(AUTH_DIR);
  const { version } = await fetchLatestBaileysVersion();

  sock = makeWASocket({
    version,
    logger,
    auth: {
      creds: state.creds,
      keys: makeCacheableSignalKeyStore(state.keys, logger),
    },
    printQRInTerminal: false,
    syncFullHistory: false,
  });

  store.bind(sock.ev);

  // QR Code - terminalga chiqarish
  sock.ev.on("connection.update", async (update) => {
    const { connection, lastDisconnect, qr } = update;

    if (qr) {
      console.log("\n📱 WhatsApp ga ulaning! QR kodni skanlang:\n");
      qrcode.generate(qr, { small: true });
      console.log("\n");
    }

    if (connection === "close") {
      const shouldReconnect =
        (lastDisconnect?.error as Boom)?.output?.statusCode !== DisconnectReason.loggedOut;

      console.log(`❌ Ulanish uzildi. Qayta ulanish: ${shouldReconnect}`);
      isConnected = false;

      if (shouldReconnect) {
        setTimeout(connectToWhatsApp, 5000);
      } else {
        console.log("🚪 WhatsApp dan chiqildi. wa_auth_state papkasini o'chirib qaytadan QR skanlang.");
      }
    } else if (connection === "open") {
      console.log("✅ WhatsApp ga muvaffaqiyatli ulandi!");
      isConnected = true;
    }
  });

  sock.ev.on("creds.update", saveCreds);

  // Kiruvchi xabarlarni Oisha-OS ga yuborish
  sock.ev.on("messages.upsert", async ({ messages, type }) => {
    if (type !== "notify") return;

    for (const msg of messages) {
      if (msg.key.fromMe) continue; // O'zimizdan yuborilgan xabarlarni o'tkazib yuborish
      if (!msg.message) continue;

      const jid = msg.key.remoteJid || "";
      const isGroup = jid.endsWith("@g.us");
      if (isGroup) continue; // Guruh xabarlarini hozircha o'tkazib yuborish

      const phone = jid.replace("@s.whatsapp.net", "").replace("+", "");
      const text =
        msg.message?.conversation ||
        msg.message?.extendedTextMessage?.text ||
        msg.message?.imageMessage?.caption ||
        "[media]";

      const pushName = msg.pushName || "Noma'lum";

      console.log(`📨 Yangi xabar | ${pushName} (${phone}): ${text?.slice(0, 80)}`);

      // Oisha-OS ga yuborish
      try {
        await axios.post(
          OISHA_WEBHOOK_URL,
          {
            source: "whatsapp",
            phone,
            name: pushName,
            text,
            message_id: msg.key.id,
            timestamp: msg.messageTimestamp,
            jid,
          },
          {
            headers: {
              "X-Oisha-Secret": OISHA_SECRET,
              "Content-Type": "application/json",
            },
            timeout: 10000,
          }
        );
      } catch (err: any) {
        console.error(`❌ Oisha webhook xatoligi: ${err.message}`);
      }
    }
  });
}

// Express API — Oisha-OS WA orqali xabar yuboradi
const app = express();
app.use(express.json());

// Auth tekshirish middleware
app.use((req: Request, res: Response, next) => {
  const secret = req.headers["x-oisha-secret"];
  if (secret !== OISHA_SECRET) {
    res.status(401).json({ error: "Ruxsat yo'q" });
    return;
  }
  next();
});

// Xabar yuborish endpoint
app.post("/send", async (req: Request, res: Response) => {
  if (!isConnected || !sock) {
    res.status(503).json({ error: "WhatsApp ga ulanmagan" });
    return;
  }

  const { phone, text, image_url } = req.body;
  if (!phone || !text) {
    res.status(400).json({ error: "phone va text kerak" });
    return;
  }

  try {
    const jid = `${phone.replace(/\D/g, "")}@s.whatsapp.net`;

    if (image_url) {
      await sock.sendMessage(jid, {
        image: { url: image_url },
        caption: text,
      });
    } else {
      await sock.sendMessage(jid, { text });
    }

    res.json({ ok: true, jid });
  } catch (err: any) {
    console.error(`❌ Xabar yuborishda xatolik: ${err.message}`);
    res.status(500).json({ error: err.message });
  }
});

// Holat tekshirish
app.get("/status", (_req: Request, res: Response) => {
  res.json({
    connected: isConnected,
    phone: sock?.user?.id || null,
  });
});

app.listen(PORT, () => {
  console.log(`\n🚀 Oisha WhatsApp Gateway ishga tushdi — Port: ${PORT}`);
  console.log(`📡 Webhook URL (Oisha -> WA): POST http://localhost:${PORT}/send`);
  console.log(`📊 Status: GET http://localhost:${PORT}/status\n`);
  connectToWhatsApp();
});
