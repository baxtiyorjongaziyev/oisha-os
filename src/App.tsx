import React, { useState } from 'react';
import { Sidebar, NavTab } from './components/layout/Sidebar';
import { Header } from './components/layout/Header';
import { CommandPaletteModal } from './components/layout/CommandPaletteModal';

import { DashboardView } from './views/DashboardView';
import { HisobchiView } from './views/HisobchiView';
import { SalesCoachView } from './views/SalesCoachView';
import { MarketingCapiView } from './views/MarketingCapiView';
import { IntegrationsView } from './views/IntegrationsView';
import { AgentSwarmView } from './views/AgentSwarmView';
import { PreflightView } from './views/PreflightView';

import {
  INITIAL_TRANSACTIONS,
  INITIAL_CALL_RECORDS,
  INITIAL_CAPI_EVENTS,
  INITIAL_AMO_LEADS,
  AGENT_SWARM,
  INITIAL_PREFLIGHT_CHECKS,
} from './data/mockData';
import {
  HisobchiTransaction,
  SalesCallRecord,
  MetaCapiEvent,
  AmoLead,
  AgentInfo,
} from './types';

export function App() {
  const [currentTab, setCurrentTab] = useState<NavTab>('dashboard');
  const [isSidebarCollapsed, setIsSidebarCollapsed] = useState(false);
  const [isCommandPaletteOpen, setIsCommandPaletteOpen] = useState(false);

  // Application Data State
  const [transactions, setTransactions] = useState<HisobchiTransaction[]>(INITIAL_TRANSACTIONS);
  const [calls, setCalls] = useState<SalesCallRecord[]>(INITIAL_CALL_RECORDS);
  const [capiEvents, setCapiEvents] = useState<MetaCapiEvent[]>(INITIAL_CAPI_EVENTS);
  const [leads, setLeads] = useState<AmoLead[]>(INITIAL_AMO_LEADS);
  const [agents, setAgents] = useState<AgentInfo[]>(AGENT_SWARM);

  // Quick Action Handler from Dashboard / Command Palette
  const handleQuickAction = (actionKey: string) => {
    if (actionKey === 'open_palette') {
      setIsCommandPaletteOpen(true);
    } else if (actionKey === 'open_sms_parser') {
      setCurrentTab('hisobchi');
    } else if (actionKey === 'open_capi_dispatcher') {
      setCurrentTab('marketing_capi');
    } else if (actionKey === 'run_all_preflight') {
      setCurrentTab('preflight');
    }
  };

  // State mutations
  const handleAddTransaction = (newTx: HisobchiTransaction) => {
    setTransactions((prev) => [newTx, ...prev]);
  };

  const handleAddCall = (newCall: SalesCallRecord) => {
    setCalls((prev) => [newCall, ...prev]);
  };

  const handleDispatchCapiEvent = (newEvent: MetaCapiEvent) => {
    setCapiEvents((prev) => [newEvent, ...prev]);
  };

  const handleRetryCapiEvent = (id: string) => {
    setCapiEvents((prev) =>
      prev.map((e) =>
        e.id === id
          ? {
              ...e,
              status: 'sent',
              eventsReceived: 1,
              retryCount: e.retryCount + 1,
              timestamp: new Date().toISOString().replace('T', ' ').substring(0, 19),
            }
          : e
      )
    );
  };

  const handleSyncAllIntegrations = () => {
    setLeads((prev) =>
      prev.map((lead) => ({
        ...lead,
        syncedToAirtable: true,
        updatedAt: new Date().toISOString().replace('T', ' ').substring(0, 16),
      }))
    );
  };

  const handleTriggerAgentTask = (agentId: string) => {
    setAgents((prev) =>
      prev.map((a) =>
        a.id === agentId
          ? {
              ...a,
              status: 'active',
              recentTasks: [
                `Executed verification: ${new Date().toLocaleTimeString()}`,
                ...a.recentTasks.slice(0, 2),
              ],
            }
          : a
      )
    );
  };

  return (
    <div className="flex h-screen w-screen overflow-hidden bg-slate-950 text-slate-100 font-sans">
      {/* Sidebar Navigation */}
      <Sidebar
        currentTab={currentTab}
        onTabChange={setCurrentTab}
        isCollapsed={isSidebarCollapsed}
        onToggleCollapse={() => setIsSidebarCollapsed(!isSidebarCollapsed)}
        onOpenCommandPalette={() => setIsCommandPaletteOpen(true)}
      />

      {/* Main Content Area */}
      <div className="flex-1 flex flex-col min-w-0 h-full overflow-hidden">
        {/* Top Header */}
        <Header
          currentTab={currentTab}
          onOpenCommandPalette={() => setIsCommandPaletteOpen(true)}
        />

        {/* Dynamic Views Viewport */}
        <main className="flex-1 overflow-y-auto p-4 sm:p-6 lg:p-8">
          <div className="max-w-7xl mx-auto pb-12">
            {currentTab === 'dashboard' && (
              <DashboardView
                transactions={transactions}
                calls={calls}
                capiEvents={capiEvents}
                leads={leads}
                agents={agents}
                onNavigate={setCurrentTab}
                onOpenQuickAction={handleQuickAction}
              />
            )}

            {currentTab === 'hisobchi' && (
              <HisobchiView
                transactions={transactions}
                onAddTransaction={handleAddTransaction}
              />
            )}

            {currentTab === 'salescoach' && (
              <SalesCoachView
                calls={calls}
                onAddCallRecord={handleAddCall}
              />
            )}

            {currentTab === 'marketing_capi' && (
              <MarketingCapiView
                capiEvents={capiEvents}
                onDispatchEvent={handleDispatchCapiEvent}
                onRetryEvent={handleRetryCapiEvent}
              />
            )}

            {currentTab === 'integrations' && (
              <IntegrationsView
                leads={leads}
                onSyncAll={handleSyncAllIntegrations}
              />
            )}

            {currentTab === 'agent_swarm' && (
              <AgentSwarmView
                agents={agents}
                onTriggerAgentTask={handleTriggerAgentTask}
              />
            )}

            {currentTab === 'preflight' && (
              <PreflightView
                checks={INITIAL_PREFLIGHT_CHECKS}
                onRunChecks={() => {}}
              />
            )}
          </div>
        </main>
      </div>

      {/* Command Palette Modal */}
      <CommandPaletteModal
        isOpen={isCommandPaletteOpen}
        onClose={() => setIsCommandPaletteOpen(false)}
        onNavigate={setCurrentTab}
        onTriggerQuickAction={handleQuickAction}
      />
    </div>
  );
}

export default App;
