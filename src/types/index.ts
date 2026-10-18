export type Currency = 'UZS' | 'USD' | 'EUR';

export type TransactionType = 'income' | 'expense';

export type TransactionCategory =
  | 'Oylik (Salary)'
  | 'Server & Infra'
  | 'Marketing & Ads'
  | 'Ijara (Rent)'
  | 'Komissiya'
  | 'Mijoz to\'lovi (Client Payment)'
  | 'Dasturiy Ta\'minot'
  | 'Boshqa';

export interface HisobchiTransaction {
  id: string;
  type: TransactionType;
  amount: number;
  currency: Currency;
  category: TransactionCategory;
  vendor: string;
  description: string;
  cardLast4?: string;
  date: string;
  channel: 'sms' | 'manual' | 'bot' | 'card_parser';
  status: 'verified' | 'pending' | 'flagged';
  rawReceipt?: string;
}

export interface CallTranscriptLine {
  id: string;
  speaker: 'operator' | 'client';
  text: string;
  timestamp: string; // e.g. "00:15"
  seconds: number;
  sentiment?: 'positive' | 'neutral' | 'negative' | 'objection';
}

export interface SalesCallRecord {
  id: string;
  leadName: string;
  phone: string;
  operatorName: string;
  durationSeconds: number;
  callDate: string;
  audioDurationFormatted: string;
  overallScore: number; // 0 - 100
  scriptAdherence: number; // 0 - 100
  empathyScore: number; // 0 - 100
  objectionHandlingScore: number; // 0 - 100
  dealOutcome: 'Won' | 'Follow-up' | 'Lost' | 'In Progress';
  dealValue: number;
  transcript: CallTranscriptLine[];
  coachingSummary: string;
  positivePoints: string[];
  areasForImprovement: string[];
}

export type CapiEventName = 'Lead' | 'Purchase' | 'AddToCart' | 'Contact' | 'Schedule';

export type CapiStatus = 'pending' | 'leased' | 'sent' | 'failed' | 'duplicate_confirmed';

export interface MetaCapiEvent {
  id: string;
  eventId: string;
  eventName: CapiEventName;
  timestamp: string;
  phoneHash: string; // SHA-256 preview
  emailHash: string; // SHA-256 preview
  rawPhone: string;
  value: number;
  currency: string;
  status: CapiStatus;
  retryCount: number;
  attributionSource: string; // e.g. "jonbranding_website" | "lead_ad" | "instagram_dm"
  eventsReceived: number; // 1 = Meta acknowledged
  errorMessage?: string;
  idempotencyKey: string;
}

export interface AmoLead {
  id: string;
  name: string;
  contactName: string;
  phone: string;
  price: number;
  pipeline: string;
  status: 'New' | 'In Conversation' | 'Invoice Sent' | 'Closed Won' | 'Closed Lost';
  updatedAt: string;
  syncedToAirtable: boolean;
}

export interface AgentInfo {
  id: string;
  name: string;
  role: string;
  mission: string;
  ownedFiles: string[];
  status: 'active' | 'idle' | 'running' | 'completed';
  lockStatus: 'available' | 'locked';
  verifyCmd: string;
  summary: string;
  recentTasks: string[];
}

export interface PreflightCheckItem {
  id: string;
  name: string;
  command: string;
  category: 'Python' | 'Security' | 'TypeScript' | 'Diff';
  status: 'pending' | 'running' | 'passed' | 'failed';
  details?: string;
  timeTakenMs?: number;
}
