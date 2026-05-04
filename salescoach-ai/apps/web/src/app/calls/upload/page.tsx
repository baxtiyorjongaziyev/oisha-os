'use client';
import { useState, useRef } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { api } from '@/lib/api';

export default function UploadPage() {
  const [file, setFile] = useState<File | null>(null);
  const [form, setForm] = useState({ customerName: '', customerPhone: '', direction: 'OUTBOUND' });
  const [uploading, setUploading] = useState(false);
  const [progress, setProgress] = useState(0);
  const [error, setError] = useState('');
  const router = useRouter();
  const inputRef = useRef<HTMLInputElement>(null);
  const dropRef = useRef<HTMLDivElement>(null);

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    const f = e.dataTransfer.files[0];
    if (f && f.type.startsWith('audio/')) setFile(f);
  };

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!file) return;
    setUploading(true);
    setError('');
    setProgress(10);
    try {
      const ext = file.name.split('.').pop() ?? 'mp3';
      const { callId, uploadUrl } = await api.post<{ callId: string; uploadUrl: string; audioKey: string }>(
        '/calls', { ...form, ext, contentType: file.type || 'audio/mpeg' },
      );
      setProgress(30);

      const uploadRes = await fetch(uploadUrl, {
        method: 'PUT',
        body: file,
        headers: { 'Content-Type': file.type || 'audio/mpeg' },
      });
      if (!uploadRes.ok) throw new Error('Upload to storage failed');
      setProgress(80);

      await api.post(`/calls/${callId}/confirm`, {});
      setProgress(100);

      setTimeout(() => router.push(`/calls/${callId}`), 300);
    } catch (err: any) {
      setError(err.message ?? 'Upload failed');
      setProgress(0);
    } finally {
      setUploading(false);
    }
  };

  const inputCls = "w-full px-4 py-3 rounded-xl border border-[var(--border)] bg-[var(--bg-card)] text-sm focus:outline-none focus:border-[var(--accent-cyan)] transition-colors placeholder:text-[var(--text-muted)]";

  return (
    <div className="flex h-screen overflow-hidden">
      {/* Sidebar */}
      <aside className="w-60 border-r border-[var(--border)] flex flex-col p-4 gap-1 shrink-0">
        <div className="px-3 py-4 mb-4">
          <h1 className="font-bold text-lg" style={{
            background: 'linear-gradient(90deg, var(--accent-cyan), #c084fc)',
            WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent',
          }}>
            SALESCOACH AI
          </h1>
          <p className="text-xs mt-0.5" style={{ color: 'var(--text-muted)' }}>Autonomous Negotiations</p>
        </div>
        <Link href="/dashboard"><div className="nav-item">📊 Dashboard</div></Link>
        <Link href="/calls/upload"><div className="nav-item active">⬆️ Upload Call</div></Link>
        <Link href="/negotiate"><div className="nav-item">🤝 Negotiate</div></Link>
        <div className="nav-item">📈 Analytics</div>
        <div className="nav-item">⚙️ Settings</div>
        <div className="flex-1" />
        <div className="px-3 py-2 text-xs" style={{ color: 'var(--text-muted)' }}>
          <div className="flex items-center gap-2">
            <span className="w-2 h-2 rounded-full pulse-live" style={{ background: 'var(--accent-green)' }} />
            System Online
          </div>
        </div>
      </aside>

      {/* Main */}
      <main className="flex-1 flex items-center justify-center p-8 overflow-y-auto">
        <div className="w-full max-w-lg">
          <div className="mb-8">
            <h2 className="text-2xl font-bold">Upload Call Recording</h2>
            <p className="text-sm mt-1" style={{ color: 'var(--text-secondary)' }}>
              AI will transcribe, score, and extract negotiation insights
            </p>
          </div>

          <form onSubmit={submit} className="space-y-4">
            {/* Drop zone */}
            <div
              ref={dropRef}
              onClick={() => inputRef.current?.click()}
              onDragOver={(e) => e.preventDefault()}
              onDrop={handleDrop}
              className="border-2 border-dashed rounded-2xl p-12 text-center cursor-pointer transition-all"
              style={{
                borderColor: file ? 'var(--accent-cyan)' : 'var(--border)',
                background: file ? 'rgba(0,242,255,.04)' : 'var(--bg-card)',
              }}
            >
              <input
                ref={inputRef} type="file"
                accept="audio/mp3,audio/wav,audio/ogg,audio/m4a,audio/mpeg,audio/*"
                className="hidden"
                onChange={(e) => setFile(e.target.files?.[0] ?? null)}
              />
              {file ? (
                <div>
                  <div className="text-3xl mb-2">🎵</div>
                  <p className="font-semibold text-sm" style={{ color: 'var(--accent-cyan)' }}>{file.name}</p>
                  <p className="text-xs mt-1" style={{ color: 'var(--text-muted)' }}>
                    {(file.size / 1024 / 1024).toFixed(1)} MB · Click to change
                  </p>
                </div>
              ) : (
                <div>
                  <div className="text-4xl mb-3" style={{ opacity: .5 }}>⬆️</div>
                  <p className="font-medium text-sm" style={{ color: 'var(--text-secondary)' }}>
                    Drop audio file or click to browse
                  </p>
                  <p className="text-xs mt-1.5" style={{ color: 'var(--text-muted)' }}>
                    MP3, WAV, OGG, M4A — up to 500 MB
                  </p>
                </div>
              )}
            </div>

            {/* Meta fields */}
            <input
              placeholder="Customer name (optional)"
              value={form.customerName}
              onChange={(e) => setForm({ ...form, customerName: e.target.value })}
              className={inputCls}
              style={{ color: 'var(--text-primary)' }}
            />
            <input
              placeholder="Customer phone (optional)"
              value={form.customerPhone}
              onChange={(e) => setForm({ ...form, customerPhone: e.target.value })}
              className={inputCls}
              style={{ color: 'var(--text-primary)' }}
            />
            <select
              value={form.direction}
              onChange={(e) => setForm({ ...form, direction: e.target.value })}
              className={inputCls}
              style={{ color: 'var(--text-primary)' }}
            >
              <option value="OUTBOUND">📞 Outbound Call</option>
              <option value="INBOUND">📲 Inbound Call</option>
            </select>

            {/* Progress bar */}
            {uploading && progress > 0 && (
              <div className="progress-bar">
                <div className="progress-fill" style={{ width: `${progress}%` }} />
              </div>
            )}

            {error && (
              <div className="px-4 py-3 rounded-xl badge-red text-sm">
                ⚠ {error}
              </div>
            )}

            <button
              type="submit"
              disabled={!file || uploading}
              className="w-full py-3.5 rounded-xl font-semibold text-sm disabled:opacity-40 transition-all hover:opacity-90"
              style={{ background: 'linear-gradient(135deg,var(--accent-violet),var(--accent-cyan))', color: '#fff' }}
            >
              {uploading ? (
                <span className="flex items-center justify-center gap-2">
                  <span className="pulse-live inline-block">⚙️</span>
                  {progress < 80 ? 'Uploading...' : 'Processing...'}
                </span>
              ) : (
                '⬆️ Upload & Analyze'
              )}
            </button>
          </form>

          {/* Info cards */}
          <div className="mt-8 grid grid-cols-3 gap-3">
            {[
              { icon: '🎙️', label: 'Auto Transcribe', desc: 'Whisper AI' },
              { icon: '🧠', label: 'AI Scoring', desc: '6-stage analysis' },
              { icon: '📊', label: 'Insights', desc: 'Risk + signals' },
            ].map(({ icon, label, desc }) => (
              <div key={label} className="glass p-3 text-center">
                <div className="text-xl mb-1">{icon}</div>
                <p className="text-xs font-medium" style={{ color: 'var(--text-primary)' }}>{label}</p>
                <p className="text-[10px] mt-0.5" style={{ color: 'var(--text-muted)' }}>{desc}</p>
              </div>
            ))}
          </div>
        </div>
      </main>
    </div>
  );
}
