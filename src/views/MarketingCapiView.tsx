import React, { useState } from 'react';
import {
  Megaphone,
  ShieldCheck,
  Send,
  RefreshCw,
  CheckCircle2,
  AlertTriangle,
  Clock,
  Lock,
  Hash,
  Database,
  ExternalLink,
} from 'lucide-react';
import { MetaCapiEvent, CapiEventName, CapiStatus } from '../types';
import { Button } from '../components/common/Button';
import { AccessibleSearchInput } from '../components/common/AccessibleSearchInput';
import { SegmentedControl } from '../components/common/SegmentedControl';

interface MarketingCapiViewProps {
  capiEvents: MetaCapiEvent[];
  onDispatchEvent: (event: MetaCapiEvent) => void;
  onRetryEvent: (id: string) => void;
  initialOpenDispatcher?: boolean;
}

// Simple browser SHA-256 helper for privacy demonstration
async function sha256(message: string): Promise<string> {
  const msgBuffer = new TextEncoder().encode(message.trim().toLowerCase());
  const hashBuffer = await crypto.subtle.digest('SHA-256', msgBuffer);
  const hashArray = Array.from(new Uint8Array(hashBuffer));
  return hashArray.map((b) => b.toString(16).padStart(2, '0')).join('');
}

export const MarketingCapiView: React.FC<MarketingCapiViewProps> = ({
  capiEvents,
  onDispatchEvent,
  onRetryEvent,
}) => {
  const [searchQuery, setSearchQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState<'all' | 'sent' | 'pending' | 'duplicate_confirmed'>('all');

  // Synthetic Dispatcher Form State
  const [eventName, setEventName] = useState<CapiEventName>('Lead');
  const [rawPhone, setRawPhone] = useState('+998 90 123 45 67');
  const [rawEmail, setRawEmail] = useState('lead@example.uz');
  const [purchaseValue, setPurchaseValue] = useState('150');
  const [currency, setCurrency] = useState('USD');
  const [attributionSource, setAttributionSource] = useState('jonbranding_website');
  const [isDispatching, setIsDispatching] = useState(false);
  const [lastDispatchedResult, setLastDispatchedResult] = useState<any | null>(null);

  const handleDispatch = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsDispatching(true);
    setLastDispatchedResult(null);

    const hashedPhone = await sha256(rawPhone.replace(/\D/g, ''));
    const hashedEmail = await sha256(rawEmail);
    const newEventId = `evt_${Date.now()}_${Math.floor(Math.random() * 9000 + 1000)}`;
    const idempotencyKey = `idemp_${eventName.toLowerCase()}_${Date.now()}`;

    setTimeout(() => {
      const newEvent: MetaCapiEvent = {
        id: `capi-${Date.now().toString().slice(-4)}`,
        eventId: newEventId,
        eventName: eventName,
        timestamp: new Date().toISOString().replace('T', ' ').substring(0, 19),
        phoneHash: hashedPhone,
        emailHash: hashedEmail,
        rawPhone: rawPhone.slice(0, 7) + '*** ** ' + rawPhone.slice(-2),
        value: eventName === 'Purchase' ? parseFloat(purchaseValue) || 100 : 0,
        currency: currency,
        status: 'sent',
        retryCount: 0,
        attributionSource: attributionSource,
        eventsReceived: 1,
        idempotencyKey: idempotencyKey,
      };

      onDispatchEvent(newEvent);
      setLastDispatchedResult({
        events_received: 1,
        fbtrace_id: `trace_${Math.random().toString(36).substring(2, 10)}`,
        idempotencyKey: idempotencyKey,
        eventId: newEventId,
      });
      setIsDispatching(false);
    }, 800);
  };

  const filteredEvents = capiEvents.filter((ev) => {
    if (statusFilter !== 'all' && ev.status !== statusFilter) return false;
    if (!searchQuery) return true;
    const q = searchQuery.toLowerCase();
    return (
      ev.eventName.toLowerCase().includes(q) ||
      ev.eventId.toLowerCase().includes(q) ||
      ev.attributionSource.toLowerCase().includes(q) ||
      ev.phoneHash.includes(q)
    );
  });

  return (
    <div className="space-y-6 animate-fade-in">
      {/* Top Banner */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 bg-slate-900 border border-slate-800 rounded-xl p-5 shadow-sm">
        <div>
          <div className="flex items-center gap-2">
            <span className="p-1.5 rounded-lg bg-indigo-500/10 text-indigo-400 border border-indigo-500/20">
              <Megaphone className="w-5 h-5" />
            </span>
            <h2 className="text-xl font-bold text-white tracking-tight">
              Meta Conversions API (CAPI) Platform
            </h2>
          </div>
          <p className="text-xs text-slate-400 mt-1">
            Durable outbox dispatch, SHA-256 PII privacy hashing, and JonBranding producer intake
          </p>
        </div>

        <div className="flex items-center gap-2">
          <span className="text-xs font-mono text-emerald-400 bg-emerald-500/10 border border-emerald-500/20 px-3 py-1.5 rounded-lg flex items-center gap-1.5">
            <ShieldCheck className="w-4 h-4" />
            CAPI Contract: Verified
          </span>
        </div>
      </div>

      {/* Metric Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-4 gap-4">
        <div className="bg-slate-900 border border-slate-800 rounded-xl p-4 shadow-sm">
          <span className="text-xs text-slate-400">Total Intake Events</span>
          <p className="text-2xl font-bold font-mono text-white mt-1">
            {capiEvents.length}
          </p>
          <span className="text-[10px] text-slate-500">Persisted before ack</span>
        </div>

        <div className="bg-slate-900 border border-slate-800 rounded-xl p-4 shadow-sm">
          <span className="text-xs text-slate-400">Sent (events_received=1)</span>
          <p className="text-2xl font-bold font-mono text-emerald-400 mt-1">
            {capiEvents.filter((e) => e.status === 'sent' || e.status === 'duplicate_confirmed').length}
          </p>
          <span className="text-[10px] text-slate-500">Meta Graph Confirmed</span>
        </div>

        <div className="bg-slate-900 border border-slate-800 rounded-xl p-4 shadow-sm">
          <span className="text-xs text-slate-400">Outbox Queue / Leased</span>
          <p className="text-2xl font-bold font-mono text-amberline mt-1">
            {capiEvents.filter((e) => e.status === 'pending' || e.status === 'leased').length}
          </p>
          <span className="text-[10px] text-slate-500">Bounded concurrency</span>
        </div>

        <div className="bg-slate-900 border border-slate-800 rounded-xl p-4 shadow-sm">
          <span className="text-xs text-slate-400">PII Storage Policy</span>
          <p className="text-sm font-bold font-mono text-slate-200 mt-2 flex items-center gap-1.5">
            <Lock className="w-3.5 h-3.5 text-emerald-400" />
            Hashed Only (0 leaks)
          </p>
          <span className="text-[10px] text-slate-500">Never plain in DB</span>
        </div>
      </div>

      {/* Dispatcher Playground & Privacy Hasher */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Synthetic Event Dispatcher Form */}
        <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 shadow-sm space-y-4">
          <div className="flex items-center justify-between border-b border-slate-800 pb-3">
            <div className="flex items-center gap-2">
              <Send className="w-4 h-4 text-amberline" />
              <h3 className="text-sm font-bold text-white uppercase tracking-wider">
                Synthetic CAPI Event Dispatcher
              </h3>
            </div>
            <span className="text-xs font-mono text-slate-400">Graph v19.0</span>
          </div>

          <form onSubmit={handleDispatch} className="space-y-4">
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label htmlFor="capi-event-name" className="block text-xs font-medium text-slate-300 mb-1">
                  Event Name *
                </label>
                <select
                  id="capi-event-name"
                  value={eventName}
                  onChange={(e) => setEventName(e.target.value as CapiEventName)}
                  className="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-lg text-sm text-slate-100 focus:outline-none focus-visible:ring-2 focus-visible:ring-amberline"
                >
                  <option value="Lead">Lead</option>
                  <option value="Purchase">Purchase</option>
                  <option value="AddToCart">AddToCart</option>
                  <option value="Contact">Contact</option>
                  <option value="Schedule">Schedule</option>
                </select>
              </div>

              <div>
                <label htmlFor="capi-source" className="block text-xs font-medium text-slate-300 mb-1">
                  Attribution Source
                </label>
                <select
                  id="capi-source"
                  value={attributionSource}
                  onChange={(e) => setAttributionSource(e.target.value)}
                  className="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-lg text-sm text-slate-100 focus:outline-none focus-visible:ring-2 focus-visible:ring-amberline"
                >
                  <option value="jonbranding_website">JonBranding Website</option>
                  <option value="instagram_lead_ad">Instagram Lead Ad</option>
                  <option value="instagram_dm">Instagram Direct</option>
                </select>
              </div>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <div>
                <label htmlFor="capi-phone" className="block text-xs font-medium text-slate-300 mb-1">
                  Phone (Will be hashed)
                </label>
                <input
                  type="text"
                  id="capi-phone"
                  value={rawPhone}
                  onChange={(e) => setRawPhone(e.target.value)}
                  className="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-lg text-sm font-mono text-slate-100 placeholder-slate-600 focus:outline-none focus-visible:ring-2 focus-visible:ring-amberline"
                />
              </div>

              <div>
                <label htmlFor="capi-email" className="block text-xs font-medium text-slate-300 mb-1">
                  Email (Will be hashed)
                </label>
                <input
                  type="email"
                  id="capi-email"
                  value={rawEmail}
                  onChange={(e) => setRawEmail(e.target.value)}
                  className="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-lg text-sm font-mono text-slate-100 placeholder-slate-600 focus:outline-none focus-visible:ring-2 focus-visible:ring-amberline"
                />
              </div>
            </div>

            {eventName === 'Purchase' && (
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label htmlFor="capi-val" className="block text-xs font-medium text-slate-300 mb-1">
                    Purchase Value *
                  </label>
                  <input
                    type="number"
                    id="capi-val"
                    value={purchaseValue}
                    onChange={(e) => setPurchaseValue(e.target.value)}
                    className="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-lg text-sm font-mono text-slate-100 focus:outline-none focus-visible:ring-2 focus-visible:ring-amberline"
                  />
                </div>
                <div>
                  <label htmlFor="capi-cur" className="block text-xs font-medium text-slate-300 mb-1">
                    Currency
                  </label>
                  <input
                    type="text"
                    id="capi-cur"
                    value={currency}
                    readOnly
                    className="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-lg text-sm font-mono text-slate-400"
                  />
                </div>
              </div>
            )}

            <div className="flex justify-end pt-2">
              <Button
                variant="primary"
                size="md"
                type="submit"
                isLoading={isDispatching}
                icon={<Send className="w-4 h-4" />}
              >
                Dispatch to Meta Graph CAPI
              </Button>
            </div>
          </form>

          {/* Meta Response Receipt */}
          {lastDispatchedResult && (
            <div className="p-3 bg-emerald-500/10 border border-emerald-500/30 rounded-lg text-xs space-y-1 animate-fade-in font-mono text-emerald-300">
              <div className="flex items-center gap-1.5 font-bold text-emerald-400">
                <CheckCircle2 className="w-4 h-4" />
                <span>Meta Graph API 200 OK • events_received=1</span>
              </div>
              <p className="text-slate-300">Event ID: {lastDispatchedResult.eventId}</p>
              <p className="text-slate-400">Trace ID: {lastDispatchedResult.fbtrace_id}</p>
              <p className="text-slate-400">Idempotency: {lastDispatchedResult.idempotencyKey}</p>
            </div>
          )}
        </div>

        {/* CAPI Contract & Privacy Architecture */}
        <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 shadow-sm space-y-4">
          <div className="flex items-center gap-2 border-b border-slate-800 pb-3">
            <ShieldCheck className="w-4 h-4 text-emerald-400" />
            <h3 className="text-sm font-bold text-white uppercase tracking-wider">
              CAPI Architecture &amp; Privacy Contract
            </h3>
          </div>

          <ul className="space-y-3 text-xs text-slate-300" aria-label="CAPI platform rules list">
            <li className="flex items-start gap-3">
              <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0 mt-0.5" aria-hidden="true" />
              <div>
                <strong className="text-slate-100">Intake Persisted Before Ack</strong>
                <p className="text-slate-400 mt-0.5">
                  Raw event is atomically written to SQLite/Postgres outbox before HTTP response is sent back to web producer.
                </p>
              </div>
            </li>

            <li className="flex items-start gap-3">
              <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0 mt-0.5" aria-hidden="true" />
              <div>
                <strong className="text-slate-100">SHA-256 Hashed Matching Data</strong>
                <p className="text-slate-400 mt-0.5">
                  Phone and email are normalized (lowercased, spaces stripped) and hashed before transmission.
                </p>
              </div>
            </li>

            <li className="flex items-start gap-3">
              <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0 mt-0.5" aria-hidden="true" />
              <div>
                <strong className="text-slate-100">events_received=1 Strict Semantics</strong>
                <p className="text-slate-400 mt-0.5">
                  Only HTTP 200 with <code>events_received=1</code> marks an outbox lease completed. Retry queue survives crashes.
                </p>
              </div>
            </li>

            <li className="flex items-start gap-3">
              <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0 mt-0.5" aria-hidden="true" />
              <div>
                <strong className="text-slate-100">Server Bearer Bypass</strong>
                <p className="text-slate-400 mt-0.5">
                  JonBranding website producer communicates via dedicated server bearer token without polluting browser panels.
                </p>
              </div>
            </li>
          </ul>

          <div className="p-3 bg-slate-950 border border-slate-800 rounded-lg text-[11px] font-mono text-slate-400">
            Contract spec: <code>docs/capi-platform.md</code> • <code>leadgen_capi_outbox.py</code>
          </div>
        </div>
      </div>

      {/* Outbox Events Table */}
      <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 shadow-sm space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div className="w-full sm:w-72">
            <AccessibleSearchInput
              id="capi-outbox-search"
              value={searchQuery}
              onChange={setSearchQuery}
              placeholder="Search event ID, type, source..."
              label="Search CAPI Outbox"
            />
          </div>

          <SegmentedControl
            id="capi-status-filter"
            label="Filter by Event Status"
            options={[
              { value: 'all', label: 'All', count: capiEvents.length },
              { value: 'sent', label: 'Sent (200 OK)', count: capiEvents.filter((e) => e.status === 'sent').length },
              { value: 'pending', label: 'Pending Outbox', count: capiEvents.filter((e) => e.status === 'pending').length },
              { value: 'duplicate_confirmed', label: 'Duplicate Check', count: capiEvents.filter((e) => e.status === 'duplicate_confirmed').length },
            ]}
            value={statusFilter}
            onChange={(val) => setStatusFilter(val as any)}
            size="sm"
          />
        </div>

        <div className="overflow-x-auto rounded-lg border border-slate-800">
          <table className="w-full text-left border-collapse" aria-label="Meta CAPI Outbox Ledger">
            <thead className="bg-slate-950/80 border-b border-slate-800 text-xs uppercase text-slate-400 font-semibold">
              <tr>
                <th scope="col" className="px-4 py-3">Event Name &amp; ID</th>
                <th scope="col" className="px-4 py-3">Hashed PII (SHA-256)</th>
                <th scope="col" className="px-4 py-3">Source</th>
                <th scope="col" className="px-4 py-3">Timestamp</th>
                <th scope="col" className="px-4 py-3 text-center">Status</th>
                <th scope="col" className="px-4 py-3 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/60 text-sm">
              {filteredEvents.length === 0 ? (
                <tr>
                  <td colSpan={6} className="px-4 py-8 text-center text-slate-500">
                    No CAPI events found for this query.
                  </td>
                </tr>
              ) : (
                filteredEvents.map((ev) => (
                  <tr key={ev.id} className="hover:bg-slate-800/40 transition-colors">
                    <td className="px-4 py-3 font-medium text-slate-100">
                      <div>
                        <span className="font-semibold text-amberline">{ev.eventName}</span>
                        {ev.value > 0 && (
                          <span className="ml-2 text-xs font-mono text-emerald-400">
                            ${ev.value} {ev.currency}
                          </span>
                        )}
                        <p className="text-[11px] font-mono text-slate-500">{ev.eventId}</p>
                      </div>
                    </td>
                    <td className="px-4 py-3 font-mono text-xs text-slate-400">
                      <div className="flex items-center gap-1.5" title={ev.phoneHash}>
                        <Hash className="w-3.5 h-3.5 text-slate-500 shrink-0" />
                        <span className="truncate max-w-[140px]">{ev.phoneHash}</span>
                      </div>
                      <span className="text-[10px] text-slate-500">{ev.rawPhone}</span>
                    </td>
                    <td className="px-4 py-3 text-xs text-slate-300">
                      <span className="px-2 py-0.5 rounded bg-slate-950 border border-slate-800">
                        {ev.attributionSource}
                      </span>
                    </td>
                    <td className="px-4 py-3 font-mono text-xs text-slate-400">
                      {ev.timestamp}
                    </td>
                    <td className="px-4 py-3 text-center">
                      {ev.status === 'sent' && (
                        <span className="inline-flex items-center gap-1 text-[11px] font-mono font-medium text-emerald-400 bg-emerald-500/10 border border-emerald-500/20 px-2 py-0.5 rounded-full">
                          <CheckCircle2 className="w-3 h-3" />
                          Sent (200)
                        </span>
                      )}
                      {ev.status === 'duplicate_confirmed' && (
                        <span className="inline-flex items-center gap-1 text-[11px] font-mono font-medium text-sky-400 bg-sky-500/10 border border-sky-500/20 px-2 py-0.5 rounded-full">
                          <ShieldCheck className="w-3 h-3" />
                          Deduplicated
                        </span>
                      )}
                      {ev.status === 'pending' && (
                        <span className="inline-flex items-center gap-1 text-[11px] font-mono font-medium text-amberline bg-amber-500/10 border border-amber-500/20 px-2 py-0.5 rounded-full">
                          <Clock className="w-3 h-3" />
                          Pending Outbox
                        </span>
                      )}
                    </td>
                    <td className="px-4 py-3 text-right">
                      {ev.status === 'pending' ? (
                        <Button
                          variant="secondary"
                          size="sm"
                          icon={<RefreshCw className="w-3.5 h-3.5" />}
                          onClick={() => onRetryEvent(ev.id)}
                        >
                          Retry
                        </Button>
                      ) : (
                        <span className="text-xs text-slate-500 font-mono">Acknowledged</span>
                      )}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};
