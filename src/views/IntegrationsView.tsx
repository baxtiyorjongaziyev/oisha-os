import React, { useState } from 'react';
import {
  Network,
  RefreshCw,
  Send,
  Database,
  ShieldCheck,
  CheckCircle2,
  AlertOctagon,
  Bot,
  ExternalLink,
  MessageSquare,
  Sparkles,
} from 'lucide-react';
import { AmoLead } from '../types';
import { Button } from '../components/common/Button';
import { ToggleSwitch } from '../components/common/ToggleSwitch';
import { AccessibleSearchInput } from '../components/common/AccessibleSearchInput';

interface IntegrationsViewProps {
  leads: AmoLead[];
  onSyncAll: () => void;
}

export const IntegrationsView: React.FC<IntegrationsViewProps> = ({
  leads,
  onSyncAll,
}) => {
  const [isSyncing, setIsSyncing] = useState(false);
  const [autoReplyEnabled, setAutoReplyEnabled] = useState(true);
  const [quietHoursEnabled, setQuietHoursEnabled] = useState(true);
  const [telegramTopicMessage, setTelegramTopicMessage] = useState('');
  const [isSendingTopicMsg, setIsSendingTopicMsg] = useState(false);
  const [topicSentFeedback, setTopicSentFeedback] = useState<string | null>(null);
  const [searchLeadQuery, setSearchLeadQuery] = useState('');

  const handleTriggerSync = () => {
    setIsSyncing(true);
    setTimeout(() => {
      onSyncAll();
      setIsSyncing(false);
    }, 1000);
  };

  const handleSendTelegramTopicMsg = (e: React.FormEvent) => {
    e.preventDefault();
    if (!telegramTopicMessage.trim()) return;

    setIsSendingTopicMsg(true);
    setTopicSentFeedback(null);
    setTimeout(() => {
      setTopicSentFeedback(`Message successfully dispatched to Telegram Finance Group (-1001889214710) Topic #2!`);
      setTelegramTopicMessage('');
      setIsSendingTopicMsg(false);
    }, 700);
  };

  const filteredLeads = leads.filter(
    (l) =>
      l.name.toLowerCase().includes(searchLeadQuery.toLowerCase()) ||
      l.contactName.toLowerCase().includes(searchLeadQuery.toLowerCase()) ||
      l.pipeline.toLowerCase().includes(searchLeadQuery.toLowerCase()) ||
      l.phone.includes(searchLeadQuery)
  );

  return (
    <div className="space-y-6 animate-fade-in">
      {/* Top Banner */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 bg-slate-900 border border-slate-800 rounded-xl p-5 shadow-sm">
        <div>
          <div className="flex items-center gap-2">
            <span className="p-1.5 rounded-lg bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
              <Network className="w-5 h-5" />
            </span>
            <h2 className="text-xl font-bold text-white tracking-tight">
              CRM &amp; Telegram Integration Hub
            </h2>
          </div>
          <p className="text-xs text-slate-400 mt-1">
            AmoCRM pipelines, Airtable two-way synchronization, and Oracle VM Telegram Bot manager
          </p>
        </div>

        <Button
          variant="primary"
          size="sm"
          isLoading={isSyncing}
          icon={<RefreshCw className="w-4 h-4" />}
          onClick={handleTriggerSync}
        >
          Force Sync All Channels
        </Button>
      </div>

      {/* Grid: Left AmoCRM & Airtable; Right Telegram Bot & Guardrails */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left 2 Cols: AmoCRM & Airtable Synchronizer */}
        <div className="lg:col-span-2 space-y-6">
          <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 shadow-sm space-y-4">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-slate-800 pb-3">
              <div>
                <h3 className="text-sm font-bold text-white uppercase tracking-wider">
                  AmoCRM Active Leads &amp; Pipelines
                </h3>
                <p className="text-xs text-slate-400">
                  Real-time deal status mapped directly into Airtable &amp; Hisobchi
                </p>
              </div>

              <div className="w-full sm:w-60">
                <AccessibleSearchInput
                  id="amo-leads-search"
                  value={searchLeadQuery}
                  onChange={setSearchLeadQuery}
                  placeholder="Search lead or contact..."
                  label="Search AmoCRM Leads"
                />
              </div>
            </div>

            <div className="overflow-x-auto rounded-lg border border-slate-800">
              <table className="w-full text-left border-collapse" aria-label="AmoCRM Leads Table">
                <thead className="bg-slate-950/80 border-b border-slate-800 text-xs uppercase text-slate-400 font-semibold">
                  <tr>
                    <th scope="col" className="px-4 py-3">Lead &amp; Contact</th>
                    <th scope="col" className="px-4 py-3">Pipeline</th>
                    <th scope="col" className="px-4 py-3 text-right">Deal Value</th>
                    <th scope="col" className="px-4 py-3 text-center">Status</th>
                    <th scope="col" className="px-4 py-3 text-center">Airtable</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800/60 text-sm">
                  {filteredLeads.map((lead) => (
                    <tr key={lead.id} className="hover:bg-slate-800/40 transition-colors">
                      <td className="px-4 py-3 font-medium text-slate-100">
                        <p>{lead.name}</p>
                        <span className="text-xs text-slate-400">
                          {lead.contactName} • {lead.phone}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-xs text-slate-300">
                        <span className="px-2 py-0.5 rounded bg-slate-950 border border-slate-800">
                          {lead.pipeline}
                        </span>
                      </td>
                      <td className="px-4 py-3 font-mono font-semibold text-right text-amberline">
                        {new Intl.NumberFormat('uz-UZ').format(lead.price)} UZS
                      </td>
                      <td className="px-4 py-3 text-center">
                        <span
                          className={`text-xs px-2.5 py-0.5 rounded-full font-medium ${
                            lead.status === 'Closed Won'
                              ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20'
                              : lead.status === 'Invoice Sent'
                              ? 'bg-amber-500/10 text-amberline border border-amber-500/20'
                              : 'bg-slate-800 text-slate-300 border border-slate-700'
                          }`}
                        >
                          {lead.status}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-center">
                        {lead.syncedToAirtable ? (
                          <span className="inline-flex items-center gap-1 text-[11px] font-mono text-emerald-400 bg-emerald-500/10 px-2 py-0.5 rounded">
                            <CheckCircle2 className="w-3 h-3" /> Synced
                          </span>
                        ) : (
                          <span className="inline-flex items-center gap-1 text-[11px] font-mono text-amberline bg-amber-500/10 px-2 py-0.5 rounded">
                            Queued
                          </span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>

        {/* Right Col: Telegram Bot & Session Guardrail */}
        <div className="space-y-6">
          {/* Telegram Session Guard Callout */}
          <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 shadow-sm space-y-4">
            <div className="flex items-center gap-2 border-b border-slate-800 pb-3">
              <Bot className="w-4 h-4 text-sky-400" />
              <h3 className="text-sm font-bold text-white uppercase tracking-wider">
                Telegram Bot &amp; Userbot
              </h3>
            </div>

            {/* Oracle VM Session Lock Notice */}
            <div className="p-3.5 bg-sky-950/30 border border-sky-800/50 rounded-xl space-y-2">
              <div className="flex items-center gap-2 text-sky-400 text-xs font-bold uppercase tracking-wider">
                <ShieldCheck className="w-4 h-4 shrink-0" />
                <span>Oracle VM Session Lock Enforced</span>
              </div>
              <p className="text-xs text-slate-300 leading-relaxed">
                As coded in <code>.claude/hooks/guard.py</code>, local userbot runs and reading <code>*.session</code> files are blocked to prevent <code>AuthKeyDuplicatedError</code> on the active production Oracle server.
              </p>
            </div>

            {/* Accessible Switches */}
            <div className="space-y-2 pt-1 border-t border-slate-800">
              <ToggleSwitch
                id="auto-reply-switch"
                label="AUTO_REPLY_MODE"
                description="Automatically answer customer questions using SalesCoach knowledge base"
                checked={autoReplyEnabled}
                onChange={setAutoReplyEnabled}
              />

              <ToggleSwitch
                id="quiet-hours-switch"
                label="Quiet Hours (23:00 - 08:00)"
                description="Pause outbound telemarketing dispatches during nighttime in Tashkent"
                checked={quietHoursEnabled}
                onChange={setQuietHoursEnabled}
              />
            </div>
          </div>

          {/* Telegram Topic Dispatcher */}
          <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 shadow-sm space-y-4">
            <div className="flex items-center gap-2">
              <Send className="w-4 h-4 text-amberline" />
              <h3 className="text-sm font-bold text-white uppercase tracking-wider">
                Finance Topic Dispatcher
              </h3>
            </div>

            <form onSubmit={handleSendTelegramTopicMsg} className="space-y-3">
              <div>
                <label htmlFor="telegram-topic-msg" className="block text-xs font-medium text-slate-300 mb-1">
                  Broadcast Alert to HISOBCHI_FINANCE_GROUP_ID
                </label>
                <textarea
                  id="telegram-topic-msg"
                  rows={3}
                  value={telegramTopicMessage}
                  onChange={(e) => setTelegramTopicMessage(e.target.value)}
                  placeholder="Type an announcement or financial alert to broadcast to the team..."
                  className="w-full p-2.5 bg-slate-950 border border-slate-800 rounded-lg text-xs font-mono text-slate-200 placeholder-slate-600 focus:outline-none focus-visible:ring-2 focus-visible:ring-amberline resize-none"
                />
              </div>

              {topicSentFeedback && (
                <p className="text-xs text-emerald-400 bg-emerald-500/10 p-2.5 rounded-lg border border-emerald-500/20">
                  {topicSentFeedback}
                </p>
              )}

              <div className="flex justify-end">
                <Button
                  variant="primary"
                  size="sm"
                  type="submit"
                  isLoading={isSendingTopicMsg}
                  icon={<Send className="w-3.5 h-3.5" />}
                >
                  Send to Topic #2
                </Button>
              </div>
            </form>
          </div>
        </div>
      </div>
    </div>
  );
};
