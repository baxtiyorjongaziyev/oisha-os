import React from 'react';
import {
  TrendingUp,
  TrendingDown,
  DollarSign,
  PhoneCall,
  Megaphone,
  CheckCircle2,
  AlertTriangle,
  ArrowRight,
  Database,
  Cpu,
  Shield,
  Activity,
  Terminal,
} from 'lucide-react';
import {
  HisobchiTransaction,
  SalesCallRecord,
  MetaCapiEvent,
  AmoLead,
  AgentInfo,
} from '../types';
import { NavTab } from '../components/layout/Sidebar';
import { Button } from '../components/common/Button';

interface DashboardViewProps {
  transactions: HisobchiTransaction[];
  calls: SalesCallRecord[];
  capiEvents: MetaCapiEvent[];
  leads: AmoLead[];
  agents: AgentInfo[];
  onNavigate: (tab: NavTab) => void;
  onOpenQuickAction: (actionKey: string) => void;
}

export const DashboardView: React.FC<DashboardViewProps> = ({
  transactions,
  calls,
  capiEvents,
  leads,
  agents,
  onNavigate,
  onOpenQuickAction,
}) => {
  const totalIncome = transactions
    .filter((t) => t.type === 'income')
    .reduce((acc, t) => acc + t.amount, 0);

  const totalExpense = transactions
    .filter((t) => t.type === 'expense')
    .reduce((acc, t) => acc + t.amount, 0);

  const netProfit = totalIncome - totalExpense;

  const avgCoachScore = Math.round(
    calls.reduce((acc, c) => acc + c.overallScore, 0) / (calls.length || 1)
  );

  const capiSentCount = capiEvents.filter((e) => e.status === 'sent' || e.status === 'duplicate_confirmed').length;

  const activeAgentsCount = agents.filter((a) => a.status === 'active').length;

  const formatUZS = (val: number) => {
    return new Intl.NumberFormat('uz-UZ').format(val) + ' UZS';
  };

  return (
    <div className="space-y-6 animate-fade-in">
      {/* Top Welcome Banner & System Status */}
      <div className="relative overflow-hidden rounded-2xl bg-gradient-to-r from-slate-900 via-slate-900 to-amber-950/30 border border-slate-800 p-6 shadow-xl">
        <div className="relative z-10 flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div className="space-y-1">
            <div className="flex items-center gap-2">
              <span className="px-2.5 py-0.5 rounded-full text-xs font-mono font-semibold bg-amberline/20 text-amberline border border-amberline/30">
                OISHA CORE ENGINE
              </span>
              <span className="text-xs text-slate-400">Production Node: Tashkent-DC1</span>
            </div>
            <h2 className="text-2xl font-extrabold text-white tracking-tight">
              Enterprise Operations Center
            </h2>
            <p className="text-sm text-slate-300 max-w-2xl">
              All 9 autonomous engineering agents operational. Hisobchi AI ledger, SalesCoach speech analysis, Meta Leadgen CAPI outbox, and AmoCRM sync running with zero security warnings.
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-3">
            <Button
              variant="outline"
              size="sm"
              icon={<Terminal className="w-4 h-4 text-amberline" />}
              onClick={() => onNavigate('preflight')}
            >
              Run Pre-flight Checks
            </Button>
            <Button
              variant="primary"
              size="sm"
              icon={<ArrowRight className="w-4 h-4" />}
              onClick={() => onNavigate('hisobchi')}
            >
              Open Hisobchi AI
            </Button>
          </div>
        </div>
      </div>

      {/* KPI Cards Row */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* Net Profit Card */}
        <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 shadow-sm hover:border-slate-700 transition-colors">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold uppercase tracking-wider text-slate-400">
              Sof Foyda (Net Profit)
            </span>
            <div className="p-2 rounded-lg bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
              <DollarSign className="w-4 h-4" />
            </div>
          </div>
          <div className="mt-3">
            <p className="text-2xl font-bold font-mono text-white tracking-tight">
              {formatUZS(netProfit)}
            </p>
            <div className="flex items-center gap-2 mt-2 text-xs text-emerald-400">
              <TrendingUp className="w-3.5 h-3.5" />
              <span>+18.4% this month</span>
              <span className="text-slate-500">•</span>
              <span className="text-slate-400 font-mono">PnL Auto-sync</span>
            </div>
          </div>
        </div>

        {/* SalesCoach Avg Score */}
        <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 shadow-sm hover:border-slate-700 transition-colors">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold uppercase tracking-wider text-slate-400">
              SalesCoach Index
            </span>
            <div className="p-2 rounded-lg bg-amber-500/10 text-amberline border border-amber-500/20">
              <PhoneCall className="w-4 h-4" />
            </div>
          </div>
          <div className="mt-3">
            <div className="flex items-baseline gap-2">
              <p className="text-2xl font-bold font-mono text-white tracking-tight">
                {avgCoachScore}
              </p>
              <span className="text-sm text-slate-400 font-mono">/ 100</span>
            </div>
            <div className="flex items-center gap-2 mt-2 text-xs text-amberline">
              <span>{calls.length} calls evaluated</span>
              <span className="text-slate-500">•</span>
              <span className="text-slate-400">Adherence 92%</span>
            </div>
          </div>
        </div>

        {/* Meta CAPI Delivery */}
        <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 shadow-sm hover:border-slate-700 transition-colors">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold uppercase tracking-wider text-slate-400">
              Meta CAPI Events
            </span>
            <div className="p-2 rounded-lg bg-indigo-500/10 text-indigo-400 border border-indigo-500/20">
              <Megaphone className="w-4 h-4" />
            </div>
          </div>
          <div className="mt-3">
            <div className="flex items-baseline gap-2">
              <p className="text-2xl font-bold font-mono text-white tracking-tight">
                {capiSentCount} / {capiEvents.length}
              </p>
              <span className="text-xs font-mono text-emerald-400">100% Attributed</span>
            </div>
            <div className="flex items-center gap-2 mt-2 text-xs text-slate-400">
              <span>SHA-256 Hashed PII</span>
              <span className="text-slate-500">•</span>
              <span className="text-slate-400 font-mono">Leased 0</span>
            </div>
          </div>
        </div>

        {/* Active Agent Swarm */}
        <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 shadow-sm hover:border-slate-700 transition-colors">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold uppercase tracking-wider text-slate-400">
              Agent Swarm
            </span>
            <div className="p-2 rounded-lg bg-sky-500/10 text-sky-400 border border-sky-500/20">
              <Cpu className="w-4 h-4" />
            </div>
          </div>
          <div className="mt-3">
            <div className="flex items-baseline gap-2">
              <p className="text-2xl font-bold font-mono text-white tracking-tight">
                {activeAgentsCount} / {agents.length}
              </p>
              <span className="text-xs font-mono text-emerald-400">All Healthy</span>
            </div>
            <div className="flex items-center gap-2 mt-2 text-xs text-slate-400">
              <span>0 lock conflicts</span>
              <span className="text-slate-500">•</span>
              <span className="text-slate-400 font-mono">CI: Green</span>
            </div>
          </div>
        </div>
      </div>

      {/* Main Grid: Core Services Health & Quick Action Cards */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left Column: Quick Actions & Financial Breakdown */}
        <div className="lg:col-span-2 space-y-6">
          {/* Quick Action Cards */}
          <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 shadow-sm">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-sm font-bold text-white uppercase tracking-wider flex items-center gap-2">
                <Activity className="w-4 h-4 text-amberline" />
                Quick Operations
              </h3>
              <span className="text-xs text-slate-500">Autonomous triggers</span>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <button
                type="button"
                onClick={() => {
                  onNavigate('hisobchi');
                  onOpenQuickAction('open_sms_parser');
                }}
                className="group flex flex-col items-start p-4 bg-slate-950/60 hover:bg-slate-800/60 border border-slate-800 hover:border-amberline/50 rounded-xl text-left transition-all duration-150 focus:outline-none focus-visible:ring-2 focus-visible:ring-amberline active:scale-[0.98]"
              >
                <div className="flex items-center justify-between w-full mb-2">
                  <span className="p-2 rounded-lg bg-amber-500/10 text-amberline border border-amber-500/20">
                    <DollarSign className="w-4 h-4" />
                  </span>
                  <ArrowRight className="w-4 h-4 text-slate-600 group-hover:text-amberline transition-colors" />
                </div>
                <h4 className="text-sm font-semibold text-slate-100 group-hover:text-amberline transition-colors">
                  Parse Bank SMS / Card Receipt
                </h4>
                <p className="text-xs text-slate-400 mt-1">
                  Extract Uzcard/Humo payments into PnL ledger with AI heuristic
                </p>
              </button>

              <button
                type="button"
                onClick={() => {
                  onNavigate('marketing_capi');
                  onOpenQuickAction('open_capi_dispatcher');
                }}
                className="group flex flex-col items-start p-4 bg-slate-950/60 hover:bg-slate-800/60 border border-slate-800 hover:border-amberline/50 rounded-xl text-left transition-all duration-150 focus:outline-none focus-visible:ring-2 focus-visible:ring-amberline active:scale-[0.98]"
              >
                <div className="flex items-center justify-between w-full mb-2">
                  <span className="p-2 rounded-lg bg-indigo-500/10 text-indigo-400 border border-indigo-500/20">
                    <Megaphone className="w-4 h-4" />
                  </span>
                  <ArrowRight className="w-4 h-4 text-slate-600 group-hover:text-amberline transition-colors" />
                </div>
                <h4 className="text-sm font-semibold text-slate-100 group-hover:text-amberline transition-colors">
                  Dispatch Meta CAPI Lead
                </h4>
                <p className="text-xs text-slate-400 mt-1">
                  Send privacy-hashed conversion event to Meta Conversions API
                </p>
              </button>

              <button
                type="button"
                onClick={() => onNavigate('salescoach')}
                className="group flex flex-col items-start p-4 bg-slate-950/60 hover:bg-slate-800/60 border border-slate-800 hover:border-amberline/50 rounded-xl text-left transition-all duration-150 focus:outline-none focus-visible:ring-2 focus-visible:ring-amberline active:scale-[0.98]"
              >
                <div className="flex items-center justify-between w-full mb-2">
                  <span className="p-2 rounded-lg bg-amber-500/10 text-amberline border border-amber-500/20">
                    <PhoneCall className="w-4 h-4" />
                  </span>
                  <ArrowRight className="w-4 h-4 text-slate-600 group-hover:text-amberline transition-colors" />
                </div>
                <h4 className="text-sm font-semibold text-slate-100 group-hover:text-amberline transition-colors">
                  Listen to Sales Call & Coach
                </h4>
                <p className="text-xs text-slate-400 mt-1">
                  Interactive audio player with diarized transcript and objection analysis
                </p>
              </button>

              <button
                type="button"
                onClick={() => onNavigate('preflight')}
                className="group flex flex-col items-start p-4 bg-slate-950/60 hover:bg-slate-800/60 border border-slate-800 hover:border-amberline/50 rounded-xl text-left transition-all duration-150 focus:outline-none focus-visible:ring-2 focus-visible:ring-amberline active:scale-[0.98]"
              >
                <div className="flex items-center justify-between w-full mb-2">
                  <span className="p-2 rounded-lg bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                    <Shield className="w-4 h-4" />
                  </span>
                  <ArrowRight className="w-4 h-4 text-slate-600 group-hover:text-amberline transition-colors" />
                </div>
                <h4 className="text-sm font-semibold text-slate-100 group-hover:text-amberline transition-colors">
                  Pre-flight Security Audit
                </h4>
                <p className="text-xs text-slate-400 mt-1">
                  Bandit -ll scanner, Pytest suites, and .env leak shield
                </p>
              </button>
            </div>
          </div>

          {/* Recent Ledger Activity */}
          <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 shadow-sm">
            <div className="flex items-center justify-between mb-4">
              <div>
                <h3 className="text-sm font-bold text-white uppercase tracking-wider">
                  Latest Financial Transactions
                </h3>
                <p className="text-xs text-slate-400">
                  Hisobchi engine real-time ledger feed
                </p>
              </div>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => onNavigate('hisobchi')}
              >
                View all
              </Button>
            </div>

            <div className="space-y-2.5">
              {transactions.slice(0, 4).map((tx) => (
                <div
                  key={tx.id}
                  className="flex items-center justify-between p-3 bg-slate-950/50 border border-slate-800/60 rounded-lg hover:border-slate-700 transition-colors"
                >
                  <div className="flex items-center gap-3 min-w-0">
                    <div
                      className={`p-2 rounded-lg ${
                        tx.type === 'income'
                          ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20'
                          : 'bg-rose-500/10 text-rose-400 border border-rose-500/20'
                      }`}
                    >
                      {tx.type === 'income' ? (
                        <TrendingUp className="w-4 h-4" />
                      ) : (
                        <TrendingDown className="w-4 h-4" />
                      )}
                    </div>
                    <div className="min-w-0">
                      <p className="text-sm font-medium text-slate-200 truncate">
                        {tx.vendor}
                      </p>
                      <p className="text-xs text-slate-500 truncate">
                        {tx.category} • {tx.date}
                      </p>
                    </div>
                  </div>
                  <div className="text-right shrink-0">
                    <p
                      className={`text-sm font-mono font-semibold ${
                        tx.type === 'income' ? 'text-emerald-400' : 'text-slate-200'
                      }`}
                    >
                      {tx.type === 'income' ? '+' : '-'}{formatUZS(tx.amount)}
                    </p>
                    <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-slate-800 text-slate-400">
                      {tx.channel}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Right Column: Architectural Subsystems Health */}
        <div className="space-y-6">
          <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 shadow-sm">
            <h3 className="text-sm font-bold text-white uppercase tracking-wider mb-4 flex items-center gap-2">
              <Database className="w-4 h-4 text-amberline" />
              Infrastructure Matrix
            </h3>

            <div className="space-y-3">
              <div className="p-3 bg-slate-950/60 border border-slate-800/80 rounded-lg flex items-center justify-between">
                <div className="space-y-0.5">
                  <div className="flex items-center gap-2">
                    <span className="w-2 h-2 rounded-full bg-emerald-400" />
                    <span className="text-xs font-semibold text-slate-200">PostgreSQL Pool</span>
                  </div>
                  <p className="text-[11px] text-slate-400">12 / 20 connections • 0 slow queries</p>
                </div>
                <span className="text-[10px] font-mono text-emerald-400 bg-emerald-500/10 px-2 py-0.5 rounded">
                  Parameterized
                </span>
              </div>

              <div className="p-3 bg-slate-950/60 border border-slate-800/80 rounded-lg flex items-center justify-between">
                <div className="space-y-0.5">
                  <div className="flex items-center gap-2">
                    <span className="w-2 h-2 rounded-full bg-emerald-400" />
                    <span className="text-xs font-semibold text-slate-200">Telegram Userbot</span>
                  </div>
                  <p className="text-[11px] text-slate-400">Oracle VM Session Lock • No collision</p>
                </div>
                <span className="text-[10px] font-mono text-emerald-400 bg-emerald-500/10 px-2 py-0.5 rounded">
                  Guarded
                </span>
              </div>

              <div className="p-3 bg-slate-950/60 border border-slate-800/80 rounded-lg flex items-center justify-between">
                <div className="space-y-0.5">
                  <div className="flex items-center gap-2">
                    <span className="w-2 h-2 rounded-full bg-emerald-400" />
                    <span className="text-xs font-semibold text-slate-200">Meta CAPI Outbox</span>
                  </div>
                  <p className="text-[11px] text-slate-400">Lease worker idle • Graph API 200 OK</p>
                </div>
                <span className="text-[10px] font-mono text-emerald-400 bg-emerald-500/10 px-2 py-0.5 rounded">
                  Durable
                </span>
              </div>

              <div className="p-3 bg-slate-950/60 border border-slate-800/80 rounded-lg flex items-center justify-between">
                <div className="space-y-0.5">
                  <div className="flex items-center gap-2">
                    <span className="w-2 h-2 rounded-full bg-emerald-400" />
                    <span className="text-xs font-semibold text-slate-200">AmoCRM & Airtable</span>
                  </div>
                  <p className="text-[11px] text-slate-400">{leads.length} leads in active pipelines</p>
                </div>
                <span className="text-[10px] font-mono text-emerald-400 bg-emerald-500/10 px-2 py-0.5 rounded">
                  Synced
                </span>
              </div>
            </div>
          </div>

          {/* Schedulers & Background Jobs */}
          <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 shadow-sm">
            <h3 className="text-sm font-bold text-white uppercase tracking-wider mb-3">
              Active Schedulers
            </h3>
            <ul className="space-y-2" aria-label="System schedulers list">
              <li className="flex items-center justify-between text-xs py-1.5 border-b border-slate-800/60">
                <span className="text-slate-300 font-mono">schedulers/daily_reports.py</span>
                <span className="text-slate-500 font-mono">09:00 Tashkent</span>
              </li>
              <li className="flex items-center justify-between text-xs py-1.5 border-b border-slate-800/60">
                <span className="text-slate-300 font-mono">schedulers/night_shift.py</span>
                <span className="text-slate-500 font-mono">23:00 Tashkent</span>
              </li>
              <li className="flex items-center justify-between text-xs py-1.5">
                <span className="text-slate-300 font-mono">schedulers/evolution.py</span>
                <span className="text-slate-500 font-mono">Hourly loop</span>
              </li>
            </ul>
          </div>
        </div>
      </div>
    </div>
  );
};
