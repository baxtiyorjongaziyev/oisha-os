'use client';
import { useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { useAuthStore } from '@/store/auth';

// Google OAuth redirects here with tokens in URL fragment
// e.g. /auth/callback#access=...&refresh=...
export default function AuthCallbackPage() {
  const { setTokens } = useAuthStore();
  const router = useRouter();

  useEffect(() => {
    const hash = new URLSearchParams(window.location.hash.slice(1));
    const access = hash.get('access');
    const refresh = hash.get('refresh');
    if (access && refresh) {
      setTokens(access, refresh);
      router.replace('/dashboard');
    } else {
      router.replace('/auth/login?error=oauth_failed');
    }
  }, []);

  return <div className="p-8 text-center">Signing you in...</div>;
}
