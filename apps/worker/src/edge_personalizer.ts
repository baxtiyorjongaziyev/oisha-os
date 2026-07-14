// 🪄 Edge AI Personalization Worker — jonbranding.uz
// Cloudflare Workers AI + Next.js Edge Middleware
// Deploy: npx wrangler deploy apps/worker/src/edge_personalizer.ts

export interface Env {
  CLOUDFLARE_ACCOUNT_ID: string;
  CLOUDFLARE_AI_API_TOKEN: string;
  AI_GATEWAY?: string;
}

const SECTOR_HEROES: Record<string, { headline: string; keys: string; cta: string }> = {
  'meditsina': { headline: 'Meditsina Brendingi', keys: 'Klinikangizni tanigan brend', cta: 'Bepul konsultatsiya' },
  'ta\'lim': { headline: 'Ta\'lim Brendingi', keys: 'Maktabingizni tanitadigan dizayn', cta: 'Portfolioni ko\'rish' },
  'retail': { headline: 'Chakana Savdo Brendi', keys: 'Do\'koningizni yuqori bosqichga', cta: 'Biz bilan bog\'laning' },
  'food': { headline: 'Oziq-ovqat Brendingi', keys: 'Restoraningizni sevdirish', cta: 'Narxlarni ko\'rish' },
  'service': { headline: 'Xizmat Ko\'rsatish Brendi', keys: 'Xizmatingizni premium qilish', cta: 'Portfolioni ko\'rish' },
  'education': { headline: 'Ta\'lim Brendingi', keys: 'Maktabingizni tanitadigan dizayn', cta: 'Portfolioni ko\'rish' },
};

async function getSector(request: Request, env: Env): Promise<string> {
  const cookie = request.headers.get('Cookie') || '';
  const match = cookie.match(/sector=([^;]+)/);
  if (match) return match[1];

  const url = new URL(request.url);
  const utmContent = url.searchParams.get('utm_content');
  if (utmContent && SECTOR_HEROES[utmContent]) return utmContent;

  try {
    const aiResp = await fetch(
      `https://api.cloudflare.com/client/v4/accounts/${env.CLOUDFLARE_ACCOUNT_ID || ''}/ai/run/@cf/meta/llama-3.1-8b-instruct`,
      {
        method: 'POST',
        headers: { Authorization: `Bearer ${env.CLOUDFLARE_AI_API_TOKEN}`, 'Content-Type': 'application/json' },
        body: JSON.stringify({
          messages: [
            { role: 'system', content: 'URL dan mijoz sektorini aniqlang. Faqat bitta so\'z: meditsina, retail, food, service, education, yoki unknown.' },
            { role: 'user', content: url.pathname + url.search },
          ],
        }),
      },
    );
    const data: any = await aiResp.json();
    const sector = (data?.result?.response || '').trim().toLowerCase();
    if (SECTOR_HEROES[sector]) return sector;
  } catch {}

  return 'unknown';
}

export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    const url = new URL(request.url);

    // Skip static files and admin
    if (url.pathname.startsWith('/_next/') || url.pathname.startsWith('/admin/') || url.pathname.match(/\.(js|css|png|jpg|svg|ico|woff2?)$/)) {
      return fetch(request);
    }

    const segment = await getSector(request, env);
    const sector = SECTOR_HEROES[segment] || SECTOR_HEROES['service'];
    const isMobile = (request.headers.get('User-Agent') || '').includes('Mobile');

    const response = await fetch(request);
    const newResponse = new Response(response.body, response);
    newResponse.headers.append('Set-Cookie', `sector=${segment}; Max-Age=86400; Path=/; Secure`);
    newResponse.headers.append('X-Segment', segment);
    newResponse.headers.append('X-Hero-Headline', sector.headline);
    newResponse.headers.append('X-Hero-Keys', sector.keys);
    newResponse.headers.append('X-Device', isMobile ? 'mobile' : 'desktop');

    return newResponse;
  },
};
