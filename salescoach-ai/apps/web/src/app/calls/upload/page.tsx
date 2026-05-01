'use client';
import { useState, useRef } from 'react';
import { useRouter } from 'next/navigation';
import { api } from '@/lib/api';

export default function UploadPage() {
  const [file, setFile] = useState<File | null>(null);
  const [form, setForm] = useState({ customerName: '', customerPhone: '', direction: 'OUTBOUND' });
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState('');
  const router = useRouter();
  const inputRef = useRef<HTMLInputElement>(null);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!file) return;
    setUploading(true);
    setError('');
    try {
      const ext = file.name.split('.').pop() ?? 'mp3';
      const { callId, uploadUrl } = await api.post<{ callId: string; uploadUrl: string; audioKey: string }>(
        '/calls', { ...form, ext, contentType: file.type || 'audio/mpeg' },
      );

      // Upload directly to S3
      const uploadRes = await fetch(uploadUrl, {
        method: 'PUT',
        body: file,
        headers: { 'Content-Type': file.type || 'audio/mpeg' },
      });
      if (!uploadRes.ok) throw new Error('S3 upload failed');

      // Confirm and enqueue transcription
      await api.post(`/calls/${callId}/confirm`, {});

      router.push(`/calls/${callId}`);
    } catch (err: any) {
      setError(err.message ?? 'Upload failed');
    } finally {
      setUploading(false);
    }
  };

  return (
    <div className="max-w-xl mx-auto p-8">
      <h1 className="text-2xl font-bold mb-6">Upload Call Recording</h1>
      <form onSubmit={submit} className="space-y-4">
        <div
          onClick={() => inputRef.current?.click()}
          className="border-2 border-dashed border-gray-300 rounded-xl p-12 text-center cursor-pointer hover:border-blue-400 transition-colors"
        >
          <input
            ref={inputRef} type="file" accept="audio/*" className="hidden"
            onChange={(e) => setFile(e.target.files?.[0] ?? null)}
          />
          {file ? (
            <p className="font-medium text-gray-800">{file.name}</p>
          ) : (
            <p className="text-gray-500">Click to select audio file (MP3, WAV, OGG, M4A)</p>
          )}
        </div>

        <input
          placeholder="Customer name (optional)"
          value={form.customerName}
          onChange={(e) => setForm({ ...form, customerName: e.target.value })}
          className="w-full border rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500"
        />
        <input
          placeholder="Customer phone (optional)"
          value={form.customerPhone}
          onChange={(e) => setForm({ ...form, customerPhone: e.target.value })}
          className="w-full border rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500"
        />
        <select
          value={form.direction}
          onChange={(e) => setForm({ ...form, direction: e.target.value })}
          className="w-full border rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500"
        >
          <option value="OUTBOUND">Outbound</option>
          <option value="INBOUND">Inbound</option>
        </select>

        {error && <p className="text-red-500 text-sm">{error}</p>}
        <button
          type="submit" disabled={!file || uploading}
          className="w-full bg-blue-600 text-white rounded-lg py-3 hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed font-medium"
        >
          {uploading ? 'Uploading...' : 'Upload & Analyze'}
        </button>
      </form>
    </div>
  );
}
