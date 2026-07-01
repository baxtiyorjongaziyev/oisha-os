'use client';
import { useState } from 'react';
import { api } from '@/lib/api';

export default function CRMPage() {
  const [selectedAction, setSelectedAction] = useState<string | null>(null);
  const [processing, setProcessing] = useState(false);

  const actions = [
    {
      id: 'export_tez_natija_sheets',
      label: '📊 Export Tez Natija to Google Sheets',
      description: 'Export all Tez Natija group members to Google Sheets',
      color: 'linear-gradient(135deg, #06b6d4, #0ea5e9)',
    },
    {
      id: 'export_tez_natija_amocrm',
      label: '💼 Export Tez Natija to AmoCRM',
      description: 'Create leads in AmoCRM from Tez Natija members',
      color: 'linear-gradient(135deg, #f59e0b, #d97706)',
    },
  ];

  const handleAction = async (actionId: string) => {
    setProcessing(true);
    try {
      await api.post(`/admin/actions/${actionId}`, {});
      alert(`✅ Action completed: ${actionId}`);
      setSelectedAction(null);
    } catch (err) {
      alert(`❌ Failed: ${err instanceof Error ? err.message : 'Unknown error'}`);
    } finally {
      setProcessing(false);
    }
  };

  return (
    <div>
      {/* Header */}
      <div className="mb-8">
        <h2 className="text-3xl font-bold mb-2">CRM Management</h2>
        <p style={{ color: 'var(--text-secondary)', fontSize: '.875rem' }}>
          Lead syncing, exports, and AmoCRM operations
        </p>
      </div>

      {/* Actions Grid */}
      <div className="grid grid-cols-2 gap-6">
        {actions.map((action) => (
          <div
            key={action.id}
            className="glass p-6 cursor-pointer transition-all hover:scale-105"
            onClick={() => setSelectedAction(action.id)}
            style={{
              borderLeft: `4px solid ${action.color.split(',')[0]}`,
            }}
          >
            <h3 className="text-lg font-semibold mb-2">{action.label}</h3>
            <p style={{ color: 'var(--text-secondary)', fontSize: '.875rem', marginBottom: '1rem' }}>
              {action.description}
            </p>
            <button
              onClick={(e) => {
                e.stopPropagation();
                handleAction(action.id);
              }}
              disabled={processing}
              className="px-4 py-2 rounded-lg font-medium text-sm transition-all hover:opacity-90 disabled:opacity-50 text-white"
              style={{ background: action.color }}
            >
              {processing ? 'Processing...' : 'Execute'}
            </button>
          </div>
        ))}
      </div>

      {/* Info Section */}
      <div className="mt-8 glass p-6">
        <h3 className="font-semibold mb-4">ℹ️ Available CRM Operations</h3>
        <ul className="space-y-2 text-sm" style={{ color: 'var(--text-secondary)' }}>
          <li>✓ Sync Tez Natija members from Telegram groups</li>
          <li>✓ Export to Google Sheets with full member details</li>
          <li>✓ Create AmoCRM leads (Hunter pipeline)</li>
          <li>✓ Auto-tag with "Tez Natija" status</li>
          <li>✓ Duplicate detection (avoid re-importing)</li>
        </ul>
      </div>
    </div>
  );
}
