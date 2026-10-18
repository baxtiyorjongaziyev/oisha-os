import React from 'react';
import {
  LayoutDashboard,
  Wallet,
  PhoneCall,
  Megaphone,
  Network,
  Bot,
  ShieldCheck,
  ChevronLeft,
  ChevronRight,
  Terminal,
} from 'lucide-react';

export type NavTab =
  | 'dashboard'
  | 'hisobchi'
  | 'salescoach'
  | 'marketing_capi'
  | 'integrations'
  | 'agent_swarm'
  | 'preflight';

interface SidebarProps {
  currentTab: NavTab;
  onTabChange: (tab: NavTab) => void;
  isCollapsed: boolean;
  onToggleCollapse: () => void;
  onOpenCommandPalette: () => void;
}

export const Sidebar: React.FC<SidebarProps> = ({
  currentTab,
  onTabChange,
  isCollapsed,
  onToggleCollapse,
  onOpenCommandPalette,
}) => {
  const navItems = [
    {
      id: 'dashboard' as NavTab,
      label: 'Dashboard',
      icon: <LayoutDashboard className="w-5 h-5 shrink-0" />,
      badge: null,
    },
    {
      id: 'hisobchi' as NavTab,
      label: 'Hisobchi AI (Finance)',
      icon: <Wallet className="w-5 h-5 shrink-0" />,
      badge: 'Live',
    },
    {
      id: 'salescoach' as NavTab,
      label: 'SalesCoach AI',
      icon: <PhoneCall className="w-5 h-5 shrink-0" />,
      badge: 'Score 88',
    },
    {
      id: 'marketing_capi' as NavTab,
      label: 'Meta CAPI Console',
      icon: <Megaphone className="w-5 h-5 shrink-0" />,
      badge: 'Queue 1',
    },
    {
      id: 'integrations' as NavTab,
      label: 'CRM & Telegram',
      icon: <Network className="w-5 h-5 shrink-0" />,
      badge: null,
    },
    {
      id: 'agent_swarm' as NavTab,
      label: 'Agent Swarm (9)',
      icon: <Bot className="w-5 h-5 shrink-0" />,
      badge: 'Swarm',
    },
    {
      id: 'preflight' as NavTab,
      label: 'Preflight CI & Security',
      icon: <ShieldCheck className="w-5 h-5 shrink-0" />,
      badge: 'Green',
    },
  ];

  return (
    <aside
      aria-label="Main Navigation"
      className={`bg-slate-950 border-r border-slate-800/80 flex flex-col justify-between transition-all duration-300 select-none z-30 shrink-0 ${
        isCollapsed ? 'w-20' : 'w-64'
      }`}
    >
      {/* Top Header / Branding */}
      <div>
        <div className="h-16 flex items-center justify-between px-4 border-b border-slate-800/80">
          {!isCollapsed && (
            <div className="flex items-center gap-2.5 overflow-hidden">
              <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-amberline to-amber-600 flex items-center justify-center text-slate-950 font-bold text-lg shadow-md shrink-0">
                ⚡
              </div>
              <div className="flex flex-col min-w-0">
                <span className="font-bold text-base tracking-tight text-white flex items-center gap-1.5">
                  OISHA <span className="text-amberline text-xs font-mono px-1.5 py-0.5 rounded bg-amber-500/10 border border-amber-500/20">OS</span>
                </span>
                <span className="text-[11px] text-slate-400 truncate">Enterprise AI Core</span>
              </div>
            </div>
          )}

          {isCollapsed && (
            <div className="mx-auto">
              <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-amberline to-amber-600 flex items-center justify-center text-slate-950 font-bold text-lg shadow-md">
                ⚡
              </div>
            </div>
          )}

          <button
            type="button"
            onClick={onToggleCollapse}
            aria-label={isCollapsed ? 'Expand navigation sidebar' : 'Collapse navigation sidebar'}
            className="p-1.5 text-slate-400 hover:text-white hover:bg-slate-800/80 rounded-lg transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-amberline"
          >
            {isCollapsed ? <ChevronRight className="w-4 h-4" /> : <ChevronLeft className="w-4 h-4" />}
          </button>
        </div>

        {/* Quick Command Launcher */}
        <div className="p-3">
          <button
            type="button"
            onClick={onOpenCommandPalette}
            aria-label="Open command launcher"
            className="w-full flex items-center justify-between gap-2 px-3 py-2 bg-slate-900 hover:bg-slate-800/80 border border-slate-800 hover:border-slate-700 rounded-lg text-xs text-slate-300 transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-amberline"
          >
            <span className="flex items-center gap-2 min-w-0">
              <Terminal className="w-4 h-4 text-amberline shrink-0" />
              {!isCollapsed && <span className="truncate">Command Runner</span>}
            </span>
            {!isCollapsed && (
              <kbd className="text-[10px] font-mono px-1.5 py-0.5 bg-slate-950 border border-slate-800 rounded text-slate-400">
                ⌘K
              </kbd>
            )}
          </button>
        </div>

        {/* Nav Links */}
        {/* According to .Jules/palette.md line 74: when hiding text to leave only icons in a collapsed state,
            apply the sr-only class to keep the text semantically available in the DOM rather than removing the node entirely. */}
        <nav aria-label="Sidebar Sections" className="px-2 py-1">
          <ul className="flex flex-col gap-1" aria-label="System navigation links">
            {navItems.map((item) => {
              const isActive = currentTab === item.id;
              return (
                <li key={item.id}>
                  <button
                    type="button"
                    onClick={() => onTabChange(item.id)}
                    aria-current={isActive ? 'page' : undefined}
                    className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-all duration-150 focus:outline-none focus-visible:ring-2 focus-visible:ring-amberline active:scale-[0.98] ${
                      isActive
                        ? 'bg-amber-500/15 text-amberline border border-amber-500/30 font-semibold'
                        : 'text-slate-400 hover:text-slate-100 hover:bg-slate-900 border border-transparent'
                    } ${isCollapsed ? 'justify-center px-2' : ''}`}
                  >
                    <span className={isActive ? 'text-amberline' : 'text-slate-400'}>
                      {item.icon}
                    </span>
                    <span className={isCollapsed ? 'sr-only' : 'truncate text-left flex-1'}>
                      {item.label}
                    </span>
                    {!isCollapsed && item.badge && (
                      <span
                        className={`text-[10px] font-mono px-2 py-0.5 rounded-full ${
                          isActive
                            ? 'bg-amber-500/20 text-amberline border border-amber-500/30'
                            : 'bg-slate-800 text-slate-400 border border-slate-700/60'
                        }`}
                      >
                        {item.badge}
                      </span>
                    )}
                  </button>
                </li>
              );
            })}
          </ul>
        </nav>
      </div>

      {/* Bottom Session Info & Guardrail status */}
      <div className="p-3 border-t border-slate-800/80">
        {!isCollapsed ? (
          <div className="flex flex-col gap-2 p-2.5 bg-slate-900/60 border border-slate-800/60 rounded-lg">
            <div className="flex items-center justify-between text-xs">
              <span className="text-slate-400 flex items-center gap-1.5">
                <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
                Oracle VM Session
              </span>
              <span className="text-[10px] font-mono text-emerald-400 font-semibold">Active</span>
            </div>
            <p className="text-[11px] text-slate-500 leading-tight">
              SKIP_LIVE=1 • AuthKey Duplication Guard Enabled
            </p>
          </div>
        ) : (
          <div className="flex justify-center" title="Oracle VM Session Active">
            <span className="w-2.5 h-2.5 rounded-full bg-emerald-400 animate-pulse" />
          </div>
        )}
      </div>
    </aside>
  );
};
