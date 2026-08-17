/**
 * Base API Client for connecting Next.js Server & Client components to the FastAPI backend.
 * 100% Real ma'lumotlar bilan ishlash uchun sozlangan.
 */

const API_BASE_URL = 
  process.env.INTERNAL_API_URL || 
  process.env.NEXT_PUBLIC_API_URL || 
  'http://127.0.0.1:8080';

const API_SECRET = process.env.OISHA_API_SECRET || process.env.NEXT_SERVER_API_KEY || '';

/**
 * Helper fetch function with standard options and automatic bearer authorization
 */
export async function fetchApi<T>(endpoint: string, options?: RequestInit): Promise<T> {
  const url = `${API_BASE_URL}${endpoint}`;
  
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

  try {
    const res = await fetch(url, defaultOptions);
    if (!res.ok) {
      throw new Error(`API error: ${res.status} - ${res.statusText}`);
    }
    const data = await res.json();
    return data as T;
  } catch (error) {
    console.error(`[fetchApi] Error fetching ${endpoint}:`, error);
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

export async function getCrmDashboardStats(): Promise<CrmDashboardStats | null> {
  try {
    return await fetchApi<CrmDashboardStats>('/api/crm/dashboard');
  } catch {
    return null;
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

export async function getCrmLeads(): Promise<{ leads: CrmLead[]; total: number } | null> {
  try {
    return await fetchApi<{ leads: CrmLead[]; total: number }>('/api/crm/leads');
  } catch {
    return null;
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

export async function getFrogTasks(): Promise<{ tasks: FrogTask[]; total: number } | null> {
  try {
    return await fetchApi<{ tasks: FrogTask[]; total: number }>('/api/crm/tasks');
  } catch {
    return null;
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

export async function getFinanceDashboardStats(): Promise<FinanceDashboardStats | null> {
  try {
    return await fetchApi<FinanceDashboardStats>('/api/finance/dashboard');
  } catch {
    return null;
  }
}

export interface FinanceTransaction {
  id: string | number;
  type: string;
  amount: string;
  description: string;
  date: string;
  category?: string;
  source?: string;
}

export async function getFinanceTransactions(): Promise<{ transactions: FinanceTransaction[] } | null> {
  try {
    return await fetchApi<{ transactions: FinanceTransaction[] }>('/api/finance/transactions');
  } catch {
    return null;
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

export async function getCallQualityRecords(): Promise<{ calls: CallQualityRecord[]; total: number } | null> {
  try {
    return await fetchApi<{ calls: CallQualityRecord[]; total: number }>('/api/oisha/sales-quality');
  } catch {
    return null;
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

export async function getSystemSignals(): Promise<SystemSignalsReport | null> {
  try {
    return await fetchApi<SystemSignalsReport>('/api/system/signals');
  } catch {
    return null;
  }
}

