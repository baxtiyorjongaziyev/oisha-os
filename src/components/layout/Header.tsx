import React from 'react';
import { Shield, Bell, Terminal, CheckCircle2 } from 'lucide-react';
import { NavTab } from './Sidebar';

interface HeaderProps {
  currentTab: NavTab;
  onOpenCommandPalette: () => void;
  unreadCount?: number;
}

export const Header: React.FC<HeaderProps> = ({
  currentTab,
  onOpenCommandPalette,
  unreadCount = 2,
}) => {
  const titles: Record<NavTab, { title: string; subtitle: string }> = {
    dashboard: {
      title: 'Operations Dashboard',
      subtitle: 'Real-time telemetry, financial KPIs & active service status',
    },
    hisobchi: {
      title: 'Hisobchi AI • Financial Engine',
      subtitle: 'Uzcard/Humo card parser, SMS intake, PnL breakdown & ledger',
    },
    salescoach: {
      title: 'SalesCoach AI • Call Intelligence',
      subtitle: 'Audio analysis, speaker diarization, objection handling & coaching',
    },
    marketing_capi: {
      title: 'Marketing OS • Meta CAPI Console',
      subtitle: 'Privacy-hashed Lead & Purchase intake, retry queue & delivery ledger',
    },
    integrations: {
      title: 'CRM & Telegram Hub',
      subtitle: 'AmoCRM two-way sync, Airtable pipelines & Telegram bot manager',
    },
    agent_swarm: {
      title: 'Multi-Agent Swarm (9 Agents)',
      subtitle: 'Autonomous subagent coordination, locks, and task execution',
    },
    preflight: {
      title: 'Pre-flight CI & Security Guard',
      subtitle: 'Ruff F821, Bandit -ll security scan, Pytest & .env leak guard',
    },
  };

  const currentInfo = titles[currentTab] || {
    title: 'Oisha OS',
    subtitle: 'Enterprise AI & Automation Platform',
  };

  return (
    <header className="h-16 bg-slate-950/80 backdrop-blur-md border-b border-slate-800/80 px-6 flex items-center justify-between sticky top-0 z-20">
      {/* Title & subtitle */}
      <div className="flex flex-col min-w-0">
        <h1 className="text-base font-bold text-white tracking-tight flex items-center gap-2">
          <span>{currentInfo.title}</span>
          <span className="hidden sm:inline-flex items-center gap-1 text-[11px] font-mono font-medium text-emerald-400 bg-emerald-500/10 border border-emerald-500/20 px-2 py-0.5 rounded-full">
            <CheckCircle2 className="w-3 h-3" />
            Operational
          </span>
        </h1>
        <p className="text-xs text-slate-400 truncate hidden md:block">
          {currentInfo.subtitle}
        </p>
      </div>

      {/* Right controls */}
      <div className="flex items-center gap-3">
        {/* Environment Tags */}
        <div className="hidden lg:flex items-center gap-2">
          <span className="text-[11px] font-mono px-2 py-0.5 rounded bg-slate-900 border border-slate-800 text-slate-400">
            ENV: <strong className="text-slate-200">Production</strong>
          </span>
          <span className="text-[11px] font-mono px-2 py-0.5 rounded bg-amber-500/10 border border-amber-500/20 text-amberline">
            SKIP_LIVE=1
          </span>
        </div>

        {/* Command Runner Button */}
        <button
          type="button"
          onClick={onOpenCommandPalette}
          aria-label="Open command palette"
          className="flex items-center gap-1.5 px-3 py-1.5 bg-slate-900 hover:bg-slate-800 border border-slate-800 rounded-lg text-xs font-medium text-slate-200 transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-amberline"
        >
          <Terminal className="w-3.5 h-3.5 text-amberline" />
          <span className="hidden sm:inline">Commands</span>
          <kbd className="hidden sm:inline text-[10px] font-mono text-slate-400 bg-slate-950 px-1 rounded">
            ⌘K
          </kbd>
        </button>

        {/* Security Guard badge */}
        <div
          title="Guardrail active: Direct pushes to main and userbot duplicate sessions blocked"
          className="flex items-center gap-1.5 px-2.5 py-1.5 bg-slate-900 border border-slate-800 rounded-lg text-xs text-slate-300"
        >
          <Shield className="w-3.5 h-3.5 text-emerald-400" />
          <span className="hidden xl:inline text-[11px] font-mono">Guard: ON</span>
        </div>

        {/* Notifications Icon */}
        <div className="relative">
          <button
            type="button"
            aria-label={`View notifications, ${unreadCount} unread`}
            className="p-2 text-slate-400 hover:text-slate-100 hover:bg-slate-900 rounded-lg transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-amberline relative"
          >
            <Bell className="w-4 h-4" />
            {unreadCount > 0 && (
              <span className="absolute top-1.5 right-1.5 w-2 h-2 rounded-full bg-amberline" />
            )}
          </button>
        </div>
      </div>
    </header>
  );
};
