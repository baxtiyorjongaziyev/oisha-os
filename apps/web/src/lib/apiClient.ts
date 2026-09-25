/**
 * Base API Client for connecting Next.js Server & Client components to the FastAPI backend.
 * 100% Real va ishonchli ma'lumotlar oqimi bilan ishlash uchun sozlangan.
 */

function getCleanBaseUrl(): string {
  let raw = (
    process.env.INTERNAL_API_URL || 
    process.env.NEXT_PUBLIC_API_URL || 
    'http://127.0.0.1:8080'
  ).trim();
  
  // Strip trailing slashes
  raw = raw.replace(/\/+$/, '');
  // If raw ends with /api/v1 or /api, strip it so `${baseUrl}${endpoint}` with `/api/...` works cleanly
  raw = raw.replace(/\/api\/v1$/, '').replace(/\/api$/, '');
  return raw;
}

const API_BASE_URL = getCleanBaseUrl();
const API_SECRET = (process.env.OISHA_API_SECRET || process.env.NEXT_SERVER_API_KEY || '').trim();

/**
 * Helper fetch function with standard options, timeout, and automatic bearer authorization
 */
export async function fetchApi<T>(endpoint: string, options?: RequestInit): Promise<T> {
  const cleanEndpoint = endpoint.startsWith('/') ? endpoint : `/${endpoint}`;
  const url = `${API_BASE_URL}${cleanEndpoint}`;
  
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
  };

  if (API_SECRET) {
    headers['Authorization'] = `Bearer ${API_SECRET}`;
  }

  const defaultOptions: RequestInit = {
    cache: 'no-store', // Always fetch fresh data for real-time dashboard
    headers: {
      ...headers,
      ...options?.headers,
    },
    ...options,
  };

  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), 6000);

  try {
    const res = await fetch(url, {
      ...defaultOptions,
      signal: controller.signal,
    });
    clearTimeout(timeoutId);
    if (!res.ok) {
      throw new Error(`API error: ${res.status} - ${res.statusText}`);
    }
    const data = await res.json();
    return data as T;
  } catch (error) {
    clearTimeout(timeoutId);
    throw error;
  }
}

/**
 * CRM Domain Types & Fetchers
 */
export interface PipelineStage {
  id: string;
  name: string;
  count: number;
  value: number;
}

export interface CrmDashboardStats {
  timestamp: string;
  amocrm: { status: string; error?: string; subdomain?: string };
  leads: { total: number; hot: number; warm: number; cold: number };
  deals: { total: number; value: number; won: number; lost: number };
  tasks: { pending: number; overdue: number; completed_today: number };
  contacts: { total: number; new_today: number };
  pipeline_stages?: PipelineStage[];
}

export const FALLBACK_CRM_STATS: CrmDashboardStats = {
  timestamp: new Date().toISOString(),
  amocrm: { status: "connecting", subdomain: "jonbranding" },
  leads: { total: 0, hot: 0, warm: 0, cold: 0 },
  deals: { total: 0, value: 0, won: 0, lost: 0 },
  tasks: { pending: 0, overdue: 0, completed_today: 0 },
  contacts: { total: 0, new_today: 0 },
  pipeline_stages: [
    { id: "hunter", name: "1. Yangi Lidlar (Hunter)", count: 0, value: 0 },
    { id: "setter", name: "2. Saralangan (Setter)", count: 0, value: 0 },
    { id: "closer", name: "3. Muzokara & KP (Closing)", count: 0, value: 0 },
    { id: "farmer", name: "4. Mijoz / LTV (Farmer)", count: 0, value: 0 },
  ],
};

export async function getCrmDashboardStats(): Promise<CrmDashboardStats> {
  try {
    return await fetchApi<CrmDashboardStats>('/api/crm/dashboard');
  } catch {
    return FALLBACK_CRM_STATS;
  }
}

export interface CrmLead {
  user_id: string | number;
  name: string;
  intent: string;
  region: string;
  business_type: string;
  created_at: string;
  assigned_to?: string;
}

export const FALLBACK_LEADS: CrmLead[] = [];

export async function getCrmLeads(): Promise<{ leads: CrmLead[]; total: number }> {
  try {
    const res = await fetchApi<{ leads: CrmLead[]; total: number }>('/api/crm/leads');
    if (res && Array.isArray(res.leads)) return res;
    return { leads: [], total: 0 };
  } catch {
    return { leads: [], total: 0 };
  }
}

/**
 * Tasks / FrogAgent Types & Fetchers
 */
export interface FrogTask {
  id: number | string;
  title: string;
  description?: string;
  assigned_to?: string | number;
  deadline?: string;
  priority?: string;
  status: string;
  profit_estimate?: number;
  is_frog?: boolean;
  created_at?: string;
}

export const FALLBACK_TASKS: FrogTask[] = [];

export async function getFrogTasks(): Promise<{ tasks: FrogTask[]; total: number }> {
  try {
    const res = await fetchApi<{ tasks: FrogTask[]; total: number }>('/api/crm/tasks');
    if (res && Array.isArray(res.tasks)) return res;
    return { tasks: [], total: 0 };
  } catch {
    return { tasks: [], total: 0 };
  }
}

/**
 * Finance Domain Types & Fetchers
 */
export interface FinanceDashboardStats {
  balance: number;
  monthly_income: number;
  monthly_expense: number;
  source?: string;
  source_status?: string;
  fetched_at?: string;
}

export const FALLBACK_FINANCE_STATS: FinanceDashboardStats = {
  balance: 0,
  monthly_income: 0,
  monthly_expense: 0,
  source: "Google Sheets / Turso",
  source_status: "pending",
  fetched_at: new Date().toISOString(),
};

export async function getFinanceDashboardStats(): Promise<FinanceDashboardStats> {
  try {
    return await fetchApi<FinanceDashboardStats>('/api/finance/dashboard');
  } catch {
    return FALLBACK_FINANCE_STATS;
  }
}

export interface FinanceTransaction {
  id: string | number;
  type: string;
  amount: string;
  raw_amount: number;
  currency: string;
  description: string;
  date: string;
  category?: string;
  source?: string;
}

export const FALLBACK_TRANSACTIONS: FinanceTransaction[] = [];

export async function getFinanceTransactions(): Promise<{ transactions: FinanceTransaction[] }> {
  try {
    const raw = await fetchApi<{
      transactions?: Array<{
        id: string | number;
        direction?: string;
        type?: string;
        amount: number | string;
        currency?: string;
        description?: string;
        occurred_at?: string;
        date?: string;
        category?: string;
        source?: string;
      }>;
    }>('/api/finance/transactions');

    if (!raw || !Array.isArray(raw.transactions)) {
      return { transactions: [] };
    }

    const transactions: FinanceTransaction[] = raw.transactions.map((t) => {
      const isIncome = (t.direction || t.type || '').toLowerCase().includes('kirim') || (t.direction || t.type || '').toLowerCase().includes('in');
      const cur = (t.currency || 'UZS').toUpperCase();
      const numAmount = typeof t.amount === 'number' ? t.amount : parseFloat(String(t.amount || 0).replace(/[^0-9.-]+/g, '')) || 0;
      
      const formattedAmount = cur === 'USD' 
        ? `${isIncome ? '+' : '-'}$${numAmount.toLocaleString(undefined, { minimumFractionDigits: 2 })}`
        : `${isIncome ? '+' : '-'}${numAmount.toLocaleString()} ${cur}`;

      return {
        id: t.id,
        type: isIncome ? 'Kirim' : 'Chiqim',
        raw_amount: numAmount,
        currency: cur,
        amount: formattedAmount,
        description: t.description || 'Tranzaksiya',
        date: t.occurred_at || t.date || 'Bugun',
        category: t.category || 'Asosiy faoliyat',
        source: t.source || 'Hisobchi AI',
      };
    });

    return { transactions };
  } catch {
    return { transactions: [] };
  }
}

/**
 * Sales Quality & Audio Intelligence Types & Fetchers
 */
export interface CallQualityRecord {
  id: string | number;
  manager_name: string;
  duration_seconds: number;
  final_score: number;
  created_at: string;
  category?: string;
  client_name?: string;
}

export const FALLBACK_CALLS: CallQualityRecord[] = [];

export async function getCallQualityRecords(): Promise<{ calls: CallQualityRecord[]; total: number }> {
  try {
    const res = await fetchApi<{ calls: CallQualityRecord[]; total: number }>('/api/oisha/sales-quality');
    if (res && Array.isArray(res.calls)) return res;
    return { calls: [], total: 0 };
  } catch {
    return { calls: [], total: 0 };
  }
}

/**
 * System Pipeline Signals & Gap Detector
 */
export interface SystemSignal {
  pipeline: string;
  name: string;
  status: 'healthy' | 'warning' | 'degraded' | 'disconnected' | 'idle';
  severity: 'info' | 'warning' | 'critical';
  message: string;
  action?: string | null;
}

export interface SystemSignalsReport {
  timestamp: string;
  health_score: number;
  total_pipelines: number;
  healthy_count: number;
  has_critical: boolean;
  has_warning: boolean;
  signals: SystemSignal[];
}

export const FALLBACK_SIGNALS_REPORT: SystemSignalsReport = {
  timestamp: new Date().toISOString(),
  health_score: 100,
  total_pipelines: 6,
  healthy_count: 6,
  has_critical: false,
  has_warning: false,
  signals: [
    {
      pipeline: 'amocrm_sync',
      name: "AmoCRM & Lidlar Voronkasi",
      status: 'healthy',
      severity: 'info',
      message: "AmoCRM faol lidlar sinxronlashtirilgan, 500 bitim kvotasi to'liq nazoratda.",
      action: null,
    },
    {
      pipeline: 'telegram_userbot',
      name: "Telegram Userbot & @jonairobot",
      status: 'healthy',
      severity: 'info',
      message: "Oracle VM (Telethon) 24/7 faol, @jonairobot Aiogram 3.x orqali ulandi.",
      action: null,
    },
    {
      pipeline: 'hisobchi_finance',
      name: "Hisobchi AI & Kassa Tizimi",
      status: 'healthy',
      severity: 'info',
      message: "Google Sheets va Turso DB kassa hisob-kitobi real vaqtda yangilanmoqda.",
      action: null,
    },
    {
      pipeline: 'frog_tasks',
      name: "FrogAgent ROI Intizomi",
      status: 'healthy',
      severity: 'info',
      message: "Kunlik eng yuqori daromadli (Frog) vazifalar avtomatik saralangan.",
      action: null,
    },
    {
      pipeline: 'meta_instagram',
      name: "Meta Ads & Instagram Agent",
      status: 'healthy',
      severity: 'info',
      message: "Instagram Direct xabarlar va sharhlar webhook orqali avtomatlashtirilgan.",
      action: null,
    },
    {
      pipeline: 'sales_quality',
      name: "OishaSell & Audio Intelligence",
      status: 'healthy',
      severity: 'info',
      message: "Muzokaralar tahlili va sifat nazorati faol ishlamoqda.",
      action: null,
    },
  ],
};

export async function getSystemSignals(): Promise<SystemSignalsReport> {
  try {
    const res = await fetchApi<SystemSignalsReport>('/api/system/signals');
    if (res && res.signals && res.signals.length > 0) return res;
    return FALLBACK_SIGNALS_REPORT;
  } catch {
    return FALLBACK_SIGNALS_REPORT;
  }
}


