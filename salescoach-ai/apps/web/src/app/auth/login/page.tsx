'use client';
import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { api } from '@/lib/api';
import { useAuthStore } from '@/store/auth';

export default function LoginPage() {
  const [form, setForm] = useState({ email: '', password: '' });
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const { setTokens } = useAuthStore();
  const router = useRouter();

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      const { accessToken, refreshToken } = await api.post<{ accessToken: string; refreshToken: string }>(
        '/auth/login', form,
      );
      setTokens(accessToken, refreshToken);
      router.push('/dashboard');
    } catch (err: any) {
      setError(err.message ?? 'Login failed');
    } finally {
      setLoading(false);
    }
  };

  const inputCls = "w-full px-4 py-3 rounded-xl border border-[var(--border)] bg-[var(--bg-card)] text-sm focus:outline-none focus:border-[var(--accent-cyan)] transition-colors placeholder:text-[var(--text-muted)]";

  return (
    <div className="min-h-screen flex items-center justify-center p-4">
      <div className="w-full max-w-sm">
        {/* Logo */}
        <div className="text-center mb-8">
          <h1 className="font-bold text-2xl" style={{
            background: 'linear-gradient(90deg, var(--accent-cyan), #c084fc)',
            WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent',
          }}>
            SALESCOACH AI
          </h1>
          <p className="text-sm mt-1" style={{ color: 'var(--text-muted)' }}>
            Autonomous Negotiations Platform
          </p>
        </div>

        <div className="glass p-8">
          <form onSubmit={submit} className="space-y-4">
            <input
              type="email" placeholder="Email" required
              value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })}
              className={inputCls} style={{ color: 'var(--text-primary)' }}
            />
            <input
              type="password" placeholder="Password" required
              value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })}
              className={inputCls} style={{ color: 'var(--text-primary)' }}
            />

            {error && (
              <div className="px-4 py-3 rounded-xl badge-red text-sm">{error}</div>
            )}

            <button
              type="submit" disabled={loading}
              className="w-full py-3.5 rounded-xl font-semibold text-sm disabled:opacity-50 transition-all hover:opacity-90"
              style={{ background: 'linear-gradient(135deg,var(--accent-violet),var(--accent-cyan))', color: '#fff' }}
            >
              {loading ? <span className="pulse-live inline-block">Signing in...</span> : 'Sign in →'}
            </button>
          </form>

          <div className="mt-5 pt-5 border-t border-[var(--border)] text-center">
            <a
              href={`${process.env.NEXT_PUBLIC_API_URL?.replace('/v1', '') ?? 'http://localhost:4000'}/v1/auth/google`}
              className="text-sm transition-colors hover:text-[var(--accent-cyan)]"
              style={{ color: 'var(--text-secondary)' }}
            >
              🔗 Sign in with Google
            </a>
          </div>
        </div>

        <p className="text-center text-xs mt-6" style={{ color: 'var(--text-muted)' }}>
          Sales intelligence for the CIS market
        </p>
      </div>
    </div>
  );
}
