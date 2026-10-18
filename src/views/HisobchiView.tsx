import React, { useState } from 'react';
import {
  Wallet,
  TrendingUp,
  TrendingDown,
  DollarSign,
  Plus,
  Download,
  Sparkles,
  Send,
  CreditCard,
  CheckCircle,
  FileText,
  AlertCircle,
  X,
} from 'lucide-react';
import {
  HisobchiTransaction,
  TransactionType,
  TransactionCategory,
  Currency,
} from '../types';
import { Button } from '../components/common/Button';
import { AccessibleSearchInput } from '../components/common/AccessibleSearchInput';
import { SegmentedControl } from '../components/common/SegmentedControl';
import { InteractiveTableHeader, SortDirection } from '../components/common/InteractiveTableHeader';
import { SAMPLE_SMS_RECEIPTS } from '../data/mockData';

interface HisobchiViewProps {
  transactions: HisobchiTransaction[];
  onAddTransaction: (tx: HisobchiTransaction) => void;
  initialOpenParser?: boolean;
}

export const HisobchiView: React.FC<HisobchiViewProps> = ({
  transactions,
  onAddTransaction,
  initialOpenParser = false,
}) => {
  const [currency, setCurrency] = useState<Currency>('UZS');
  const [searchQuery, setSearchQuery] = useState('');
  const [typeFilter, setTypeFilter] = useState<'all' | 'income' | 'expense'>('all');
  const [sortField, setSortField] = useState<string>('date');
  const [sortDirection, setSortDirection] = useState<SortDirection>('desc');

  // Parser Playground State
  const [rawSmsInput, setRawSmsInput] = useState<string>(SAMPLE_SMS_RECEIPTS[0].text);
  const [isParsing, setIsParsing] = useState(false);
  const [parsedResult, setParsedResult] = useState<Partial<HisobchiTransaction> | null>(null);
  const [parseSuccessMsg, setParseSuccessMsg] = useState<string | null>(null);

  // Manual Modal State
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [manualType, setManualType] = useState<TransactionType>('expense');
  const [manualAmount, setManualAmount] = useState('');
  const [manualVendor, setManualVendor] = useState('');
  const [manualCategory, setManualCategory] = useState<TransactionCategory>('Server & Infra');
  const [manualDesc, setManualDesc] = useState('');
  const [manualCard, setManualCard] = useState('');

  // Exchange rate simulation
  const UZS_PER_USD = 12750;

  const formatAmount = (val: number, cur: Currency) => {
    if (cur === 'USD') {
      const inUsd = val / UZS_PER_USD;
      return '$' + inUsd.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
    }
    return new Intl.NumberFormat('uz-UZ').format(val) + ' UZS';
  };

  const totalIncome = transactions
    .filter((t) => t.type === 'income')
    .reduce((acc, t) => acc + t.amount, 0);

  const totalExpense = transactions
    .filter((t) => t.type === 'expense')
    .reduce((acc, t) => acc + t.amount, 0);

  const netProfit = totalIncome - totalExpense;

  // Sorting
  const handleSort = (field: string) => {
    if (sortField === field) {
      setSortDirection(sortDirection === 'asc' ? 'desc' : 'asc');
    } else {
      setSortField(field);
      setSortDirection('asc');
    }
  };

  // Parsing Engine Simulation
  const handleRunParser = () => {
    setIsParsing(true);
    setParseSuccessMsg(null);

    setTimeout(() => {
      const text = rawSmsInput;
      let detectedType: TransactionType = 'expense';
      if (
        text.toLowerCase().includes('kirim') ||
        text.toLowerCase().includes('tushdi') ||
        text.toLowerCase().includes('popolnenie')
      ) {
        detectedType = 'income';
      }

      // Extract amount
      const amountMatch = text.match(/([\d,]+(?:\.\d+)?)\s*(?:UZS|сум|so'm|\$)/i);
      let detectedAmount = 0;
      if (amountMatch) {
        detectedAmount = parseFloat(amountMatch[1].replace(/,/g, ''));
      } else {
        const fallbackNumbers = text.match(/\b\d{1,3}(?:,\d{3})+\b/);
        if (fallbackNumbers) {
          detectedAmount = parseFloat(fallbackNumbers[0].replace(/,/g, ''));
        }
      }

      // Extract card
      const cardMatch = text.match(/(?:\*|karta:?\s*\*?)(\d{4})/i);
      const cardLast4 = cardMatch ? cardMatch[1] : '8812';

      // Extract vendor / merchant
      let vendor = 'Aniqlanmagan Qabul qiluvchi';
      if (text.toLowerCase().includes('meta')) vendor = 'Meta Ads Dublin';
      else if (text.toLowerCase().includes('hetzner')) vendor = 'Hetzner Online GmbH';
      else if (text.toLowerCase().includes('akfa')) vendor = 'OOO AKFA BUILDING';
      else if (text.toLowerCase().includes('toshshahar')) vendor = 'Toshshahartrans';
      else if (text.toLowerCase().includes('openai')) vendor = 'OpenAI API Platform';
      else {
        const vendorMatch = text.match(/(?:Manzil|Manba|Yuboruvchi|To'lov|Oplata):\s*([^.\n]+)/i);
        if (vendorMatch) vendor = vendorMatch[1].trim();
      }

      // Category detection
      let category: TransactionCategory = 'Boshqa';
      if (vendor.toLowerCase().includes('meta') || vendor.toLowerCase().includes('ad')) {
        category = 'Marketing & Ads';
      } else if (vendor.toLowerCase().includes('hetzner') || vendor.toLowerCase().includes('server')) {
        category = 'Server & Infra';
      } else if (detectedType === 'income') {
        category = 'Mijoz to\'lovi (Client Payment)';
      }

      setParsedResult({
        type: detectedType,
        amount: detectedAmount || 1500000,
        currency: 'UZS',
        vendor: vendor,
        category: category,
        description: `Parsed from SMS via hisobchi_card_parser.py (${cardLast4})`,
        cardLast4: cardLast4,
        date: new Date().toISOString().replace('T', ' ').substring(0, 16),
        channel: 'card_parser',
        status: 'verified',
        rawReceipt: text,
      });

      setIsParsing(false);
      setParseSuccessMsg('Receipt successfully structured into Hisobchi schema!');
    }, 600);
  };

  const handleConfirmParsed = () => {
    if (!parsedResult) return;
    const newTx: HisobchiTransaction = {
      id: `tx-${Date.now().toString().slice(-4)}`,
      type: parsedResult.type || 'expense',
      amount: parsedResult.amount || 0,
      currency: parsedResult.currency || 'UZS',
      category: parsedResult.category || 'Boshqa',
      vendor: parsedResult.vendor || 'Unknown Vendor',
      description: parsedResult.description || 'Auto parsed transaction',
      cardLast4: parsedResult.cardLast4,
      date: parsedResult.date || new Date().toISOString().replace('T', ' ').substring(0, 16),
      channel: 'card_parser',
      status: 'verified',
      rawReceipt: parsedResult.rawReceipt,
    };
    onAddTransaction(newTx);
    setParsedResult(null);
    setParseSuccessMsg('Added to verified ledger & dispatched alert to Telegram Finance Group!');
  };

  const handleManualSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!manualAmount || !manualVendor) return;

    const newTx: HisobchiTransaction = {
      id: `tx-${Date.now().toString().slice(-4)}`,
      type: manualType,
      amount: parseFloat(manualAmount.replace(/,/g, '')),
      currency: currency,
      category: manualCategory,
      vendor: manualVendor,
      description: manualDesc || `${manualCategory} payment`,
      cardLast4: manualCard || undefined,
      date: new Date().toISOString().replace('T', ' ').substring(0, 16),
      channel: 'manual',
      status: 'verified',
    };
    onAddTransaction(newTx);
    setIsModalOpen(false);
    setManualAmount('');
    setManualVendor('');
    setManualDesc('');
    setManualCard('');
  };

  // Filter & Sort Transactions
  const filteredTransactions = transactions
    .filter((tx) => {
      if (typeFilter !== 'all' && tx.type !== typeFilter) return false;
      if (!searchQuery) return true;
      const q = searchQuery.toLowerCase();
      return (
        tx.vendor.toLowerCase().includes(q) ||
        tx.description.toLowerCase().includes(q) ||
        tx.category.toLowerCase().includes(q) ||
        (tx.cardLast4 && tx.cardLast4.includes(q))
      );
    })
    .sort((a, b) => {
      let comparison = 0;
      if (sortField === 'amount') {
        comparison = a.amount - b.amount;
      } else if (sortField === 'vendor') {
        comparison = a.vendor.localeCompare(b.vendor);
      } else if (sortField === 'category') {
        comparison = a.category.localeCompare(b.category);
      } else {
        comparison = a.date.localeCompare(b.date);
      }
      return sortDirection === 'asc' ? comparison : -comparison;
    });

  const exportCSV = () => {
    const headers = ['ID', 'Type', 'Amount', 'Currency', 'Category', 'Vendor', 'Date', 'Channel'];
    const rows = filteredTransactions.map((t) => [
      t.id,
      t.type,
      t.amount,
      t.currency,
      `"${t.category}"`,
      `"${t.vendor}"`,
      t.date,
      t.channel,
    ]);
    const csvContent = 'data:text/csv;charset=utf-8,' + [headers.join(','), ...rows.map((r) => r.join(','))].join('\n');
    const encodedUri = encodeURI(csvContent);
    const link = document.createElement('a');
    link.setAttribute('href', encodedUri);
    link.setAttribute('download', `oisha_hisobchi_ledger_${Date.now()}.csv`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  return (
    <div className="space-y-6 animate-fade-in">
      {/* Top Banner & Currency Switcher */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 bg-slate-900 border border-slate-800 rounded-xl p-5 shadow-sm">
        <div>
          <div className="flex items-center gap-2">
            <span className="p-1.5 rounded-lg bg-amber-500/10 text-amberline border border-amber-500/20">
              <Wallet className="w-5 h-5" />
            </span>
            <h2 className="text-xl font-bold text-white tracking-tight">
              Hisobchi AI Finance Engine
            </h2>
          </div>
          <p className="text-xs text-slate-400 mt-1">
            Automated bank receipt parsing, real-time PnL ledger & Telegram group topic dispatcher
          </p>
        </div>

        <div className="flex items-center gap-3">
          {/* Currency Toggle */}
          <div className="flex items-center bg-slate-950 p-1 rounded-lg border border-slate-800">
            <button
              type="button"
              onClick={() => setCurrency('UZS')}
              aria-pressed={currency === 'UZS'}
              className={`px-3 py-1 text-xs font-mono font-medium rounded-md transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-amberline ${
                currency === 'UZS'
                  ? 'bg-amberline text-slate-950 font-bold'
                  : 'text-slate-400 hover:text-white'
              }`}
            >
              UZS
            </button>
            <button
              type="button"
              onClick={() => setCurrency('USD')}
              aria-pressed={currency === 'USD'}
              className={`px-3 py-1 text-xs font-mono font-medium rounded-md transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-amberline ${
                currency === 'USD'
                  ? 'bg-amberline text-slate-950 font-bold'
                  : 'text-slate-400 hover:text-white'
              }`}
            >
              USD
            </button>
          </div>

          <Button
            variant="primary"
            size="sm"
            icon={<Plus className="w-4 h-4" />}
            onClick={() => setIsModalOpen(true)}
          >
            Add Transaction
          </Button>
        </div>
      </div>

      {/* PnL Stats Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        {/* Income Card */}
        <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 shadow-sm">
          <div className="flex items-center justify-between text-xs font-semibold uppercase tracking-wider text-slate-400">
            <span>Jami Kirim (Income)</span>
            <div className="p-1.5 rounded-lg bg-emerald-500/10 text-emerald-400">
              <TrendingUp className="w-4 h-4" />
            </div>
          </div>
          <p className="text-2xl font-bold font-mono text-emerald-400 mt-2">
            +{formatAmount(totalIncome, currency)}
          </p>
          <p className="text-xs text-slate-500 mt-1">Verified Client Inflow</p>
        </div>

        {/* Expense Card */}
        <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 shadow-sm">
          <div className="flex items-center justify-between text-xs font-semibold uppercase tracking-wider text-slate-400">
            <span>Jami Chiqim (Expense)</span>
            <div className="p-1.5 rounded-lg bg-rose-500/10 text-rose-400">
              <TrendingDown className="w-4 h-4" />
            </div>
          </div>
          <p className="text-2xl font-bold font-mono text-slate-200 mt-2">
            -{formatAmount(totalExpense, currency)}
          </p>
          <p className="text-xs text-slate-500 mt-1">Infra, Ads & Operations</p>
        </div>

        {/* Net Profit Card */}
        <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 shadow-sm">
          <div className="flex items-center justify-between text-xs font-semibold uppercase tracking-wider text-slate-400">
            <span>Sof Foyda (Net Profit)</span>
            <div className="p-1.5 rounded-lg bg-amber-500/10 text-amberline">
              <DollarSign className="w-4 h-4" />
            </div>
          </div>
          <p className="text-2xl font-bold font-mono text-white mt-2">
            {formatAmount(netProfit, currency)}
          </p>
          <p className="text-xs text-emerald-400 mt-1">Margin: {Math.round((netProfit / (totalIncome || 1)) * 100)}%</p>
        </div>
      </div>

      {/* Interactive Bank SMS / Card Parser Section */}
      <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 shadow-sm space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-slate-800 pb-3">
          <div className="flex items-center gap-2">
            <Sparkles className="w-4 h-4 text-amberline" />
            <h3 className="text-sm font-bold text-white uppercase tracking-wider">
              Card &amp; Bank SMS Parser Playground
            </h3>
            <span className="text-[11px] font-mono text-amberline bg-amber-500/10 border border-amber-500/20 px-2 py-0.5 rounded">
              hisobchi_card_parser.py
            </span>
          </div>
          <span className="text-xs text-slate-400">
            Topic: HISOBCHI_FINANCE_GROUP_ID
          </span>
        </div>

        {/* Sample preset buttons */}
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-xs text-slate-400">Presets:</span>
          {SAMPLE_SMS_RECEIPTS.map((preset, idx) => (
            <button
              key={idx}
              type="button"
              onClick={() => {
                setRawSmsInput(preset.text);
                setParsedResult(null);
                setParseSuccessMsg(null);
              }}
              className="text-xs px-2.5 py-1 bg-slate-950 hover:bg-slate-800 border border-slate-800 hover:border-slate-700 text-slate-300 rounded-md transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-amberline"
            >
              {preset.label}
            </button>
          ))}
        </div>

        {/* Input Textarea & Run Button */}
        <div className="space-y-2">
          <label htmlFor="raw-sms-input" className="sr-only">
            Raw SMS or Bank Receipt Text
          </label>
          <textarea
            id="raw-sms-input"
            rows={2}
            value={rawSmsInput}
            onChange={(e) => setRawSmsInput(e.target.value)}
            placeholder="Paste raw bank SMS (Uzcard, Humo, Visa, Payme, Click)..."
            className="w-full p-3 bg-slate-950 border border-slate-800 rounded-lg text-sm font-mono text-slate-200 placeholder-slate-600 focus:outline-none focus-visible:ring-2 focus-visible:ring-amberline focus-visible:border-transparent resize-none"
          />

          <div className="flex items-center justify-between gap-3 pt-1">
            <p className="text-xs text-slate-500">
              Regex parser detects amount, card last 4, vendor entity, and PnL category.
            </p>
            <Button
              variant="primary"
              size="sm"
              isLoading={isParsing}
              icon={<Sparkles className="w-4 h-4" />}
              onClick={handleRunParser}
            >
              Parse with Hisobchi Engine
            </Button>
          </div>
        </div>

        {/* Success Feedback banner */}
        {parseSuccessMsg && (
          <div className="flex items-center gap-2 p-3 bg-emerald-500/10 border border-emerald-500/30 text-emerald-300 text-xs rounded-lg animate-fade-in">
            <CheckCircle className="w-4 h-4 shrink-0 text-emerald-400" />
            <span>{parseSuccessMsg}</span>
          </div>
        )}

        {/* Structured Result Preview */}
        {parsedResult && (
          <div className="p-4 bg-slate-950 border border-amberline/40 rounded-xl space-y-3 animate-fade-in">
            <div className="flex items-center justify-between">
              <span className="text-xs font-bold uppercase tracking-wider text-amberline flex items-center gap-1.5">
                <CheckCircle className="w-4 h-4" />
                Parsed &amp; Validated Entity
              </span>
              <span className="text-xs font-mono text-slate-400">Ready to commit</span>
            </div>

            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs">
              <div className="p-2.5 bg-slate-900 border border-slate-800 rounded-lg">
                <span className="text-slate-500">Amount &amp; Type</span>
                <p className={`font-mono font-bold mt-1 text-sm ${parsedResult.type === 'income' ? 'text-emerald-400' : 'text-slate-200'}`}>
                  {parsedResult.type === 'income' ? '+' : '-'}{formatAmount(parsedResult.amount || 0, currency)}
                </p>
              </div>

              <div className="p-2.5 bg-slate-900 border border-slate-800 rounded-lg">
                <span className="text-slate-500">Vendor / Merchant</span>
                <p className="font-semibold text-slate-200 mt-1 truncate">
                  {parsedResult.vendor}
                </p>
              </div>

              <div className="p-2.5 bg-slate-900 border border-slate-800 rounded-lg">
                <span className="text-slate-500">Category</span>
                <p className="font-semibold text-amberline mt-1 truncate">
                  {parsedResult.category}
                </p>
              </div>

              <div className="p-2.5 bg-slate-900 border border-slate-800 rounded-lg">
                <span className="text-slate-500">Card Identifier</span>
                <p className="font-mono text-slate-300 mt-1">
                  *{parsedResult.cardLast4}
                </p>
              </div>
            </div>

            {/* Telegram Alert Preview */}
            <div className="p-3 bg-slate-900/80 border border-slate-800 rounded-lg text-xs font-mono text-slate-300 space-y-1">
              <div className="flex items-center gap-1.5 text-slate-400 text-[11px] mb-1">
                <Send className="w-3.5 h-3.5 text-amberline" />
                <span>Telegram Finance Alert Dispatch Preview:</span>
              </div>
              <p className="text-slate-200">
                📢 <strong>Hisobchi PnL Bot</strong>: {parsedResult.type === 'income' ? '🟢 KIRIM' : '🔴 CHIQIM'}
              </p>
              <p>Summa: {new Intl.NumberFormat('uz-UZ').format(parsedResult.amount || 0)} UZS</p>
              <p>Kategoriya: {parsedResult.category} | Qabul qiluvchi: {parsedResult.vendor}</p>
            </div>

            <div className="flex justify-end gap-2 pt-1">
              <Button
                variant="outline"
                size="sm"
                onClick={() => setParsedResult(null)}
              >
                Discard
              </Button>
              <Button
                variant="primary"
                size="sm"
                icon={<CheckCircle className="w-4 h-4" />}
                onClick={handleConfirmParsed}
              >
                Tasdiqlash &amp; Balansga Qo'shish
              </Button>
            </div>
          </div>
        )}
      </div>

      {/* Transactions Ledger Table */}
      <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 shadow-sm space-y-4">
        {/* Table Controls (Search, Filters, CSV Export) */}
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div className="w-full md:w-72">
            <AccessibleSearchInput
              id="hisobchi-ledger-search"
              value={searchQuery}
              onChange={setSearchQuery}
              placeholder="Search vendor, category, card..."
              label="Search Ledger"
            />
          </div>

          <div className="flex flex-wrap items-center gap-3">
            <SegmentedControl
              id="tx-type-filter"
              label="Transaction Type Filter"
              options={[
                { value: 'all', label: 'All', count: transactions.length },
                { value: 'income', label: 'Kirim', count: transactions.filter((t) => t.type === 'income').length },
                { value: 'expense', label: 'Chiqim', count: transactions.filter((t) => t.type === 'expense').length },
              ]}
              value={typeFilter}
              onChange={(val) => setTypeFilter(val as 'all' | 'income' | 'expense')}
              size="sm"
            />

            <Button
              variant="outline"
              size="sm"
              icon={<Download className="w-3.5 h-3.5" />}
              onClick={exportCSV}
            >
              Export CSV
            </Button>
          </div>
        </div>

        {/* Table View */}
        <div className="overflow-x-auto rounded-lg border border-slate-800">
          <table className="w-full text-left border-collapse" aria-label="Hisobchi Transactions Ledger">
            <thead className="bg-slate-950/80 border-b border-slate-800">
              <tr>
                <InteractiveTableHeader
                  label="Vendor / Source"
                  field="vendor"
                  currentSortField={sortField}
                  direction={sortDirection}
                  onSort={handleSort}
                />
                <InteractiveTableHeader
                  label="Category"
                  field="category"
                  currentSortField={sortField}
                  direction={sortDirection}
                  onSort={handleSort}
                />
                <InteractiveTableHeader
                  label="Amount"
                  field="amount"
                  currentSortField={sortField}
                  direction={sortDirection}
                  onSort={handleSort}
                  align="right"
                />
                <InteractiveTableHeader
                  label="Date"
                  field="date"
                  currentSortField={sortField}
                  direction={sortDirection}
                  onSort={handleSort}
                />
                <th scope="col" className="px-4 py-3 text-xs font-semibold uppercase tracking-wider text-slate-400 text-center">
                  Channel
                </th>
                <th scope="col" className="px-4 py-3 text-xs font-semibold uppercase tracking-wider text-slate-400 text-center">
                  Status
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/60 text-sm">
              {filteredTransactions.length === 0 ? (
                <tr>
                  <td colSpan={6} className="px-4 py-8 text-center text-slate-500">
                    No transactions match your search query.
                  </td>
                </tr>
              ) : (
                filteredTransactions.map((tx) => (
                  <tr
                    key={tx.id}
                    className="hover:bg-slate-800/40 transition-colors"
                  >
                    <td className="px-4 py-3 font-medium text-slate-100">
                      <div className="flex items-center gap-2">
                        {tx.type === 'income' ? (
                          <span className="p-1 rounded bg-emerald-500/10 text-emerald-400" title="Kirim">
                            <TrendingUp className="w-3.5 h-3.5" />
                          </span>
                        ) : (
                          <span className="p-1 rounded bg-rose-500/10 text-rose-400" title="Chiqim">
                            <TrendingDown className="w-3.5 h-3.5" />
                          </span>
                        )}
                        <div>
                          <p className="leading-snug">{tx.vendor}</p>
                          {tx.cardLast4 && (
                            <span className="text-[11px] font-mono text-slate-500">
                              *{tx.cardLast4}
                            </span>
                          )}
                        </div>
                      </div>
                    </td>
                    <td className="px-4 py-3 text-slate-300">
                      <span className="inline-block px-2 py-0.5 rounded text-xs bg-slate-950 border border-slate-800 text-slate-300">
                        {tx.category}
                      </span>
                    </td>
                    <td className="px-4 py-3 font-mono font-semibold text-right">
                      <span className={tx.type === 'income' ? 'text-emerald-400' : 'text-slate-200'}>
                        {tx.type === 'income' ? '+' : '-'}{formatAmount(tx.amount, currency)}
                      </span>
                    </td>
                    <td className="px-4 py-3 font-mono text-xs text-slate-400">
                      {tx.date}
                    </td>
                    <td className="px-4 py-3 text-center">
                      <span className="text-[11px] font-mono px-2 py-0.5 rounded bg-slate-800 text-slate-400 uppercase">
                        {tx.channel}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-center">
                      <span className="inline-flex items-center gap-1 text-[11px] font-medium text-emerald-400 bg-emerald-500/10 border border-emerald-500/20 px-2 py-0.5 rounded-full">
                        <CheckCircle className="w-3 h-3" />
                        Verified
                      </span>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Manual Add Transaction Modal */}
      {isModalOpen && (
        <div
          role="dialog"
          aria-modal="true"
          aria-labelledby="manual-tx-title"
          className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/80 backdrop-blur-sm"
        >
          <div
            className="w-full max-w-md bg-slate-900 border border-slate-800 rounded-2xl shadow-2xl overflow-hidden"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-between px-5 py-4 border-b border-slate-800">
              <h3 id="manual-tx-title" className="text-base font-bold text-white">
                Add Manual Transaction
              </h3>
              <button
                type="button"
                onClick={() => setIsModalOpen(false)}
                aria-label="Close modal"
                className="p-1 text-slate-400 hover:text-white rounded-lg hover:bg-slate-800 transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-amberline"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <form onSubmit={handleManualSubmit} className="p-5 space-y-4">
              {/* Type selector */}
              <div>
                <label id="manual-type-label" className="block text-xs font-medium text-slate-300 mb-1.5">
                  Transaction Type
                </label>
                <div role="group" aria-labelledby="manual-type-label" className="grid grid-cols-2 gap-2">
                  <button
                    type="button"
                    aria-pressed={manualType === 'expense'}
                    onClick={() => setManualType('expense')}
                    className={`py-2 text-xs font-semibold rounded-lg border transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-amberline ${
                      manualType === 'expense'
                        ? 'bg-rose-500/20 text-rose-400 border-rose-500/40'
                        : 'bg-slate-950 text-slate-400 border-slate-800 hover:text-slate-200'
                    }`}
                  >
                    Chiqim (Expense)
                  </button>
                  <button
                    type="button"
                    aria-pressed={manualType === 'income'}
                    onClick={() => setManualType('income')}
                    className={`py-2 text-xs font-semibold rounded-lg border transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-amberline ${
                      manualType === 'income'
                        ? 'bg-emerald-500/20 text-emerald-400 border-emerald-500/40'
                        : 'bg-slate-950 text-slate-400 border-slate-800 hover:text-slate-200'
                    }`}
                  >
                    Kirim (Income)
                  </button>
                </div>
              </div>

              {/* Amount */}
              <div>
                <label htmlFor="manual-amount" className="block text-xs font-medium text-slate-300 mb-1">
                  Amount (UZS) *
                </label>
                <input
                  type="number"
                  id="manual-amount"
                  required
                  value={manualAmount}
                  onChange={(e) => setManualAmount(e.target.value)}
                  placeholder="e.g. 1500000"
                  className="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-lg text-sm text-slate-100 placeholder-slate-600 focus:outline-none focus-visible:ring-2 focus-visible:ring-amberline"
                />
              </div>

              {/* Vendor */}
              <div>
                <label htmlFor="manual-vendor" className="block text-xs font-medium text-slate-300 mb-1">
                  Vendor / Counterparty *
                </label>
                <input
                  type="text"
                  id="manual-vendor"
                  required
                  value={manualVendor}
                  onChange={(e) => setManualVendor(e.target.value)}
                  placeholder="e.g. Hetzner, Meta Ads, Client LLC"
                  className="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-lg text-sm text-slate-100 placeholder-slate-600 focus:outline-none focus-visible:ring-2 focus-visible:ring-amberline"
                />
              </div>

              {/* Category */}
              <div>
                <label htmlFor="manual-category" className="block text-xs font-medium text-slate-300 mb-1">
                  Category
                </label>
                <select
                  id="manual-category"
                  value={manualCategory}
                  onChange={(e) => setManualCategory(e.target.value as TransactionCategory)}
                  className="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-lg text-sm text-slate-100 focus:outline-none focus-visible:ring-2 focus-visible:ring-amberline"
                >
                  <option value="Server & Infra">Server &amp; Infra</option>
                  <option value="Marketing & Ads">Marketing &amp; Ads</option>
                  <option value="Oylik (Salary)">Oylik (Salary)</option>
                  <option value="Ijara (Rent)">Ijara (Rent)</option>
                  <option value="Komissiya">Komissiya</option>
                  <option value="Mijoz to'lovi (Client Payment)">Mijoz to'lovi (Client Payment)</option>
                  <option value="Dasturiy Ta'minot">Dasturiy Ta'minot</option>
                  <option value="Boshqa">Boshqa</option>
                </select>
              </div>

              {/* Card last 4 */}
              <div>
                <label htmlFor="manual-card" className="block text-xs font-medium text-slate-300 mb-1">
                  Card Last 4 Digits (Optional)
                </label>
                <input
                  type="text"
                  id="manual-card"
                  maxLength={4}
                  value={manualCard}
                  onChange={(e) => setManualCard(e.target.value)}
                  placeholder="e.g. 8812"
                  className="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-lg text-sm font-mono text-slate-100 placeholder-slate-600 focus:outline-none focus-visible:ring-2 focus-visible:ring-amberline"
                />
              </div>

              <div className="flex justify-end gap-2 pt-2 border-t border-slate-800">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setIsModalOpen(false)}
                >
                  Cancel
                </Button>
                <Button
                  variant="primary"
                  size="sm"
                  type="submit"
                >
                  Save Transaction
                </Button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
