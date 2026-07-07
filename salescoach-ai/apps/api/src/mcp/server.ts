#!/usr/bin/env node
/**
 * SalesCoach AI — MCP Server
 * Claude Code va boshqa AI agentlar uchun salescoach-ai ni tool sifatida expose qiladi.
 *
 * Ishga tushirish:
 *   npx tsx apps/api/src/mcp/server.ts
 *
 * Env:
 *   SALESCOACH_API_URL   (default: http://localhost:4000)
 *   SALESCOACH_SERVICE_TOKEN  (Bearer token yoki bo'sh)
 */

import { Server } from '@modelcontextprotocol/sdk/server/index.js';
import { StdioServerTransport } from '@modelcontextprotocol/sdk/server/stdio.js';
import {
  CallToolRequestSchema,
  ListToolsRequestSchema,
} from '@modelcontextprotocol/sdk/types.js';

const API_URL = (process.env.SALESCOACH_API_URL ?? 'http://localhost:4000').replace(/\/$/, '');
const TOKEN = process.env.SALESCOACH_SERVICE_TOKEN ?? '';

// ── HTTP Helper ────────────────────────────────────────────────
async function apiFetch(path: string, opts: RequestInit = {}) {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(TOKEN ? { Authorization: `Bearer ${TOKEN}` } : {}),
  };
  const res = await fetch(`${API_URL}/v1${path}`, { ...opts, headers });
  if (!res.ok) {
    const body = await res.text().catch(() => '');
    throw new Error(`API ${res.status}: ${body.slice(0, 200)}`);
  }
  return res.json();
}

// ── Tool definitions ───────────────────────────────────────────
const TOOLS = [
  {
    name: 'get_negotiation_suggestion',
    description:
      'Mijoz xabari uchun AI-powered javob taklifi, tactical analysis va surgicalMission olish. ' +
      'Muzokaralar jarayonida real-time yordam beradi.',
    inputSchema: {
      type: 'object',
      properties: {
        message: { type: 'string', description: "Mijozning so'nggi xabari" },
        history: {
          type: 'array',
          description: "Oldingi suhbat tarixi [{role, content}]",
          items: {
            type: 'object',
            properties: {
              role: { type: 'string', enum: ['manager', 'customer'] },
              content: { type: 'string' },
            },
          },
        },
        crmStatus: { type: 'string', description: "CRM dagi mijoz holati (ixtiyoriy)" },
        serviceType: {
          type: 'string',
          enum: ['branding', 'web', 'marketing', 'consulting'],
          description: "Xizmat turi",
        },
        customerName: { type: 'string', description: "Mijoz ismi (ixtiyoriy)" },
      },
      required: ['message'],
    },
  },
  {
    name: 'get_realtime_tip',
    description:
      "Jonli qo'ng'iroq paytida tezkor (Haiku model) coaching tip olish. " +
      "1 ta qisqa, harakat qilish mumkin bo'lgan maslahat qaytaradi.",
    inputSchema: {
      type: 'object',
      properties: {
        message: { type: 'string', description: "Mijoz yoki menejer so'nggi gap/iborasi" },
        crmStatus: { type: 'string' },
      },
      required: ['message'],
    },
  },
  {
    name: 'get_pipeline_insights',
    description:
      "So'nggi N kun uchun pipeline statistikasi: jami qo'ng'iroqlar, o'rtacha ball, eng ko'p risk flaglar.",
    inputSchema: {
      type: 'object',
      properties: {
        days: { type: 'number', description: "Necha kunlik statistika (default: 7)", default: 7 },
      },
    },
  },
  {
    name: 'list_calls',
    description: "So'nggi qo'ng'iroqlar ro'yxati: mijoz ismi, yo'nalish, status, AI ball.",
    inputSchema: {
      type: 'object',
      properties: {
        limit: { type: 'number', description: "Nechta qaytarish (default: 10)", default: 10 },
      },
    },
  },
  {
    name: 'get_call_detail',
    description:
      "Bitta qo'ng'iroq ma'lumotlari. Faqat ishlov berilgan (status=DONE) qo'ng'iroqlarda transcript va scorecard bor. " +
      "Agar status=UPLOADED/TRANSCRIBING/SCORING bo'lsa, hali tayyor emas. processingNote maydoniga qarang.",
    inputSchema: {
      type: 'object',
      properties: {
        callId: { type: 'string', description: "Qo'ng'iroq UUID si" },
      },
      required: ['callId'],
    },
  },
  {
    name: 'handle_objection',
    description:
      "Muayyan e'tiroz turi uchun moslashtirilgan javob strategiyasi olish (narx, vaqt, raqobat va boshqalar).",
    inputSchema: {
      type: 'object',
      properties: {
        objectionType: {
          type: 'string',
          enum: ['price', 'trust', 'timing', 'competition', 'legal', 'budget', 'authority'],
          description: "E'tiroz turi",
        },
        context: { type: 'string', description: "Suhbat konteksti" },
        language: { type: 'string', enum: ['uz', 'ru', 'en'], default: 'uz' },
      },
      required: ['objectionType', 'context'],
    },
  },
];

// ── Server setup ───────────────────────────────────────────────
const server = new Server(
  { name: 'salescoach-ai', version: '1.0.0' },
  { capabilities: { tools: {} } },
);

server.setRequestHandler(ListToolsRequestSchema, async () => ({ tools: TOOLS }));

server.setRequestHandler(CallToolRequestSchema, async (req) => {
  const { name, arguments: args } = req.params;
  try {
    let result: unknown;
    switch (name) {
      case 'get_negotiation_suggestion':
        result = await apiFetch('/negotiations/suggest', {
          method: 'POST',
          body: JSON.stringify(args),
        });
        break;
      case 'get_realtime_tip':
        result = await apiFetch('/negotiations/realtime', {
          method: 'POST',
          body: JSON.stringify(args),
        });
        break;
      case 'get_pipeline_insights': {
        const days = (args as any)?.days ?? 7;
        result = await apiFetch(`/negotiations/pipeline-insights?days=${days}`);
        break;
      }
      case 'list_calls': {
        result = await apiFetch('/calls');
        const limit = (args as any)?.limit ?? 10;
        if (Array.isArray(result)) result = result.slice(0, limit);
        break;
      }
      case 'get_call_detail': {
        const { callId } = args as { callId: string };
        result = await apiFetch(`/calls/${callId}`);
        break;
      }
      case 'handle_objection': {
        const { objectionType, context, language } = args as any;
        result = await apiFetch(`/negotiations/objection/${objectionType}`, {
          method: 'POST',
          body: JSON.stringify({ context, language }),
        });
        break;
      }
      default:
        throw new Error(`Unknown tool: ${name}`);
    }
    return { content: [{ type: 'text', text: JSON.stringify(result, null, 2) }] };
  } catch (err: any) {
    return { content: [{ type: 'text', text: `Error: ${err.message}` }], isError: true };
  }
});

// ── Start ──────────────────────────────────────────────────────
async function main() {
  // Health check: verify API is reachable
  try {
    const healthRes = await fetch(`${API_URL}/v1/health`, { signal: AbortSignal.timeout(5000) });
    if (!healthRes.ok) {
      process.stderr.write(`[salescoach-ai MCP] WARNING: API at ${API_URL} returned HTTP ${healthRes.status}\n`);
    } else {
      process.stderr.write(`[salescoach-ai MCP] API at ${API_URL} is reachable\n`);
    }
  } catch (err: any) {
    process.stderr.write(`[salescoach-ai MCP] WARNING: API at ${API_URL} not reachable — ${err.message}\n`);
    process.stderr.write('[salescoach-ai MCP] Tools will fail until API is started\n');
  }

  const transport = new StdioServerTransport();
  await server.connect(transport);
  process.stderr.write('[salescoach-ai MCP] Server started\n');
}

main().catch((err) => {
  process.stderr.write(`[salescoach-ai MCP] Fatal: ${err.message}\n`);
  process.exit(1);
});
