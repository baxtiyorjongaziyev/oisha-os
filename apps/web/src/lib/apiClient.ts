/**
 * Base API Client for connecting Next.js Server & Client components to the FastAPI backend.
 */

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8000';

/**
 * Helper fetch function with standard options
 */
export async function fetchApi<T>(endpoint: string, options?: RequestInit): Promise<T> {
  const url = `${API_BASE_URL}${endpoint}`;
  
  // Set default cache behavior to prevent stale data for dynamic dashboard pages
  const defaultOptions: RequestInit = {
    cache: 'no-store', // Always fetch fresh data for dashboard
    headers: {
      'Content-Type': 'application/json',
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
    // Throw error so pages can handle them using error boundaries or default states
    throw error;
  }
}

/**
 * Domain specific fetchers
 */

export interface CrmDashboardStats {
  timestamp: string;
  amocrm: { status: string; error?: string; subdomain?: string };
  leads: { total: number; hot: number; warm: number; cold: number };
  deals: { total: number; value: number; won: number; lost: number };
  tasks: { pending: number; overdue: number; completed_today: number };
  contacts: { total: number; new_today: number };
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
}

export async function getCrmLeads(): Promise<{ leads: CrmLead[]; total: number } | null> {
  try {
    return await fetchApi<{ leads: CrmLead[]; total: number }>('/api/crm/leads');
  } catch {
    return null;
  }
}

export interface FinanceDashboardStats {
  balance: number;
  monthly_income: number;
  monthly_expense: number;
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
}

export async function getFinanceTransactions(): Promise<{ transactions: FinanceTransaction[] } | null> {
  try {
    return await fetchApi<{ transactions: FinanceTransaction[] }>('/api/finance/transactions');
  } catch {
    return null;
  }
}
