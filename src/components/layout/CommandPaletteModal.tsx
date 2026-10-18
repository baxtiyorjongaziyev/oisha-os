import React, { useState, useEffect, useRef } from 'react';
import { Terminal, Search, X, Check, ArrowRight } from 'lucide-react';
import { NavTab } from './Sidebar';

interface CommandPaletteModalProps {
  isOpen: boolean;
  onClose: () => void;
  onNavigate: (tab: NavTab) => void;
  onTriggerQuickAction: (actionKey: string) => void;
}

interface CommandItem {
  id: string;
  command: string;
  description: string;
  category: 'Navigation' | 'Hisobchi AI' | 'Marketing CAPI' | 'System & Preflight';
  action: () => void;
}

export const CommandPaletteModal: React.FC<CommandPaletteModalProps> = ({
  isOpen,
  onClose,
  onNavigate,
  onTriggerQuickAction,
}) => {
  const [query, setQuery] = useState('');
  const [selectedIndex, setSelectedIndex] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);

  const commands: CommandItem[] = [
    {
      id: 'cmd-parse-sms',
      command: '/hisobchi parse',
      description: 'Open Card & SMS receipt parser playground',
      category: 'Hisobchi AI',
      action: () => {
        onNavigate('hisobchi');
        onTriggerQuickAction('open_sms_parser');
      },
    },
    {
      id: 'cmd-pnl',
      command: '/hisobchi pnl',
      description: 'View current Net Profit & PnL breakdown',
      category: 'Hisobchi AI',
      action: () => onNavigate('hisobchi'),
    },
    {
      id: 'cmd-capi-send',
      command: '/capi dispatch',
      description: 'Dispatch synthetic Meta Conversions API event',
      category: 'Marketing CAPI',
      action: () => {
        onNavigate('marketing_capi');
        onTriggerQuickAction('open_capi_dispatcher');
      },
    },
    {
      id: 'cmd-sales-coach',
      command: '/salescoach eval',
      description: 'Analyze call recordings and review audio coaching scorecard',
      category: 'Navigation',
      action: () => onNavigate('salescoach'),
    },
    {
      id: 'cmd-preflight',
      command: '/preflight run',
      description: 'Run Bandit, Ruff F821, and Pytest security checks',
      category: 'System & Preflight',
      action: () => {
        onNavigate('preflight');
        onTriggerQuickAction('run_all_preflight');
      },
    },
    {
      id: 'cmd-crm-sync',
      command: '/sync amocrm',
      description: 'Force sync leads between AmoCRM and Airtable',
      category: 'Navigation',
      action: () => onNavigate('integrations'),
    },
    {
      id: 'cmd-agent-swarm',
      command: '/swarm inspect',
      description: 'Inspect status and locks across all 9 engineering subagents',
      category: 'System & Preflight',
      action: () => onNavigate('agent_swarm'),
    },
  ];

  const filtered = commands.filter(
    (c) =>
      c.command.toLowerCase().includes(query.toLowerCase()) ||
      c.description.toLowerCase().includes(query.toLowerCase()) ||
      c.category.toLowerCase().includes(query.toLowerCase())
  );

  useEffect(() => {
    if (isOpen) {
      setTimeout(() => inputRef.current?.focus(), 50);
      setSelectedIndex(0);
      setQuery('');
    }
  }, [isOpen]);

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault();
        if (isOpen) onClose();
        else onTriggerQuickAction('open_palette');
      }
      if (!isOpen) return;

      if (e.key === 'Escape') {
        e.preventDefault();
        onClose();
      } else if (e.key === 'ArrowDown') {
        e.preventDefault();
        setSelectedIndex((prev) => (prev + 1) % (filtered.length || 1));
      } else if (e.key === 'ArrowUp') {
        e.preventDefault();
        setSelectedIndex((prev) => (prev - 1 + (filtered.length || 1)) % (filtered.length || 1));
      } else if (e.key === 'Enter') {
        e.preventDefault();
        if (filtered[selectedIndex]) {
          filtered[selectedIndex].action();
          onClose();
        }
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, selectedIndex, filtered, onClose, onTriggerQuickAction]);

  if (!isOpen) return null;

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label="Command Runner"
      className="fixed inset-0 z-50 flex items-start justify-center pt-20 px-4 bg-slate-950/80 backdrop-blur-sm animate-fade-in"
    >
      <div
        className="w-full max-w-xl bg-slate-900 border border-slate-800 rounded-2xl shadow-2xl overflow-hidden flex flex-col"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Search Bar */}
        <div className="flex items-center gap-3 px-4 py-3.5 border-b border-slate-800">
          <Terminal className="w-5 h-5 text-amberline shrink-0" />
          <input
            ref={inputRef}
            type="text"
            value={query}
            onChange={(e) => {
              setQuery(e.target.value);
              setSelectedIndex(0);
            }}
            placeholder="Type a command or search feature (e.g. /hisobchi, /capi)..."
            aria-label="Command input"
            className="w-full bg-transparent text-sm text-slate-100 placeholder-slate-500 focus:outline-none"
          />
          <button
            type="button"
            onClick={onClose}
            aria-label="Close command runner"
            className="p-1 text-slate-400 hover:text-slate-100 rounded-lg hover:bg-slate-800 transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-amberline"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Command list */}
        <div className="max-h-80 overflow-y-auto p-2">
          {filtered.length === 0 ? (
            <div className="py-8 text-center text-slate-500 text-sm">
              No matching commands found. Try <code className="text-amberline">/hisobchi</code> or <code className="text-amberline">/capi</code>.
            </div>
          ) : (
            <ul className="flex flex-col gap-1" aria-label="Available commands">
              {filtered.map((cmd, idx) => {
                const isSelected = idx === selectedIndex;
                return (
                  <li key={cmd.id}>
                    <button
                      type="button"
                      onClick={() => {
                        cmd.action();
                        onClose();
                      }}
                      onMouseEnter={() => setSelectedIndex(idx)}
                      className={`w-full flex items-center justify-between gap-3 px-3 py-2.5 rounded-lg text-sm transition-colors text-left focus:outline-none ${
                        isSelected
                          ? 'bg-amberline/15 text-slate-100 border border-amberline/30'
                          : 'text-slate-300 hover:bg-slate-800/60 border border-transparent'
                      }`}
                    >
                      <div className="flex items-center gap-3 min-w-0">
                        <span className="font-mono text-xs font-semibold px-2 py-0.5 rounded bg-slate-950 border border-slate-800 text-amberline">
                          {cmd.command}
                        </span>
                        <span className="truncate text-xs text-slate-300">
                          {cmd.description}
                        </span>
                      </div>
                      <div className="flex items-center gap-2 shrink-0">
                        <span className="text-[10px] font-mono text-slate-500 uppercase">
                          {cmd.category}
                        </span>
                        {isSelected && <ArrowRight className="w-3.5 h-3.5 text-amberline" />}
                      </div>
                    </button>
                  </li>
                );
              })}
            </ul>
          )}
        </div>

        {/* Modal footer hints */}
        <div className="px-4 py-2.5 bg-slate-950 border-t border-slate-800/80 flex items-center justify-between text-[11px] text-slate-500">
          <div className="flex items-center gap-3">
            <span>
              <kbd className="font-mono bg-slate-900 px-1 py-0.5 rounded text-slate-400">↑↓</kbd> Navigate
            </span>
            <span>
              <kbd className="font-mono bg-slate-900 px-1 py-0.5 rounded text-slate-400">↵</kbd> Execute
            </span>
            <span>
              <kbd className="font-mono bg-slate-900 px-1 py-0.5 rounded text-slate-400">ESC</kbd> Close
            </span>
          </div>
          <span className="font-mono text-amberline/80">Oisha OS v2.4</span>
        </div>
      </div>
    </div>
  );
};
