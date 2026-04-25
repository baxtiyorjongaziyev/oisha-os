'use client';
import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { api } from '@/lib/api';
import { useAuthStore } from '@/store/auth';

export default function LoginPage() {
  const [form, setForm] = useState({ email: '', password: '' });
  const [error, setError] = useState('');
  const { setTokens } = useAuthStore();
  const router = useRouter();

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    try {
      const { accessToken, refreshToken } = await api.post<{ accessToken: string; refreshToken: string }>(
        '/auth/login', form,
      );
      setTokens(accessToken, refreshToken);
      router.push('/dashboard');
    } catch (err: any) {
      setError(err.message ?? 'Login failed');
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50">
      <div className="bg-white rounded-2xl shadow-lg p-8 w-96">
        <h1 className="text-2xl font-bold mb-6">SalesCoach AI</h1>
        <form onSubmit={submit} className="space-y-4">
          <input
            type="email" placeholder="Email" required
            value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })}
            className="w-full border rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
          <input
            type="password" placeholder="Password" required
            value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })}
            className="w-full border rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
          {error && <p className="text-red-500 text-sm">{error}</p>}
          <button type="submit" className="w-full bg-blue-600 text-white rounded-lg py-2 hover:bg-blue-700">
            Sign in
          </button>
        </form>
        <div className="mt-4 text-center">
          <a href="/v1/auth/google" className="text-sm text-blue-600 hover:underline">
            Sign in with Google
          </a>
        </div>
      </div>
    </div>
  );
}
