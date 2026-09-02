import structlog
from typing import Dict, Any
from src.settings import settings

logger = structlog.get_logger()


class EdgePersonalizer:
    """🪄 Edge AI Personalization — Cloudflare Workers AI.

    Vebsayt tashrif buyuruvchilarni IP, qurilma va oldingi harakatlari bo'yicha
    segmentatsiya qiladi va Next.js middleware orqali vebsayt kontentini
    real-time moslashtiradi.

    Segmentlar:
    - Soha (meditsina, retail, food, service, education)
    - Qurilma (mobile, desktop, tablet)
    - Til (uz, ru, en)
    - Mavsumiy (Ramadan, Yangi yil, Back-to-school)
    """

    def __init__(self):
        self.account_id = settings.CLOUDFLARE_ACCOUNT_ID
        self.api_token = settings.CLOUDFLARE_AI_API_TOKEN.get_secret_value() if settings.CLOUDFLARE_AI_API_TOKEN else None
        self.enabled = bool(self.account_id and self.api_token)

    def build_worker_script(self) -> str:
        """Cloudflare Worker skriptini qaytaradi.

        Bu skript jonbranding.uz ga o'rnatiladi va:
        1. Har bir so'rovda tashrif buyuruvchini tahlil qiladi
        2. Sohasiga qarab hero section ni o'zgartiradi
        3. Cookie orqali segmentni eslab qoladi
        """
        return f"""
// 🪄 Edge AI Personalization — jonbranding.uz
// Cloudflare Workers AI + Next.js Edge Middleware

const AI_GATEWAY = 'https://gateway.ai.cloudflare.com/v1/{self.account_id or "ACCOUNT_ID"}/jonbranding';
const CF_AI_TOKEN = '{self.api_token or "CF_AI_TOKEN"}';

// Sektorlar va ularga mos hero kontent
const SECTOR_HEROES = {{
  'meditsina': {{ headline: 'Meditsina Brendingi', keys: 'Klinikangizni tanigan brend', cta: 'Bepul konsultatsiya' }},
  'ta\'lim': {{ headline: 'Ta\'lim Brendingi', keys: 'Maktabingizni tanitadigan dizayn', cta: 'Portfolioni ko\'rish' }},
  'retail': {{ headline: 'Chakana Savdo Brendi', keys: 'Do\'koningizni yuqori bosqichga', cta: 'Biz bilan bog\'laning' }},
  'food': {{ headline: 'Oziq-ovqat Brendingi', keys: 'Restoraningizni sevdirish', cta: 'Narxlarni ko\'rish' }},
  'service': {{ headline: 'Xizmat Ko\'rsatish Brendi', keys: 'Xizmatingizni premium qilish', cta: 'Portfolioni ko\'rish' }},
}};

// GA4 dan real segmentlarni olish
async function getSegment(request, env) {{
  const ua = request.headers.get('User-Agent') || '';
  const ip = request.headers.get('CF-Connecting-IP');
  const country = request.cf?.country || 'UZ';

  // Cookie orqali segment
  const cookie = request.headers.get('Cookie') || '';
  const segmentMatch = cookie.match(/sector=([^;]+)/);
  if (segmentMatch) return segmentMatch[1];

  // GA4 dan olingan so'nggi segment (query string orqali)
  const url = new URL(request.url);
  const utmContent = url.searchParams.get('utm_content');
  if (utmContent && SECTOR_HEROES[utmContent]) return utmContent;

  // Mobil/Desktop
  const isMobile = ua.includes('Mobile');
  const device = isMobile ? 'mobile' : 'desktop';

  // Til
  const lang = request.headers.get('Accept-Language')?.startsWith('ru') ? 'ru' : 'uz';

  // Cloudflare AI orqali segmentatsiya
  try {{
    const aiResp = await fetch(`${{AI_GATEWAY}}/run/@cf/meta/llama-3.1-8b-instruct`, {{
      method: 'POST',
      headers: {{ 'Authorization': 'Bearer ${{CF_AI_TOKEN}}', 'Content-Type': 'application/json' }},
      body: JSON.stringify({{
        messages: [
          {{ role: 'system', content: 'URL dan sektorni aniqlang. Faqat bitta so\'z: meditsina, retail, food, service, education, yoki unknown.' }},
          {{ role: 'user', content: url.pathname + url.search }}
        ]
      }})
    }});
    const aiData = await aiResp.json();
    const sector = (aiData?.result?.response || '').trim().toLowerCase();
    if (SECTOR_HEROES[sector]) return sector;
  }} catch (e) {{}}

  return 'unknown';
}}

export default {{
  async fetch(request, env, ctx) {{
    const url = new URL(request.url);
    if (url.pathname.startsWith('/_next/') || url.pathname.startsWith('/admin/')) {{
      return fetch(request);
    }}

    const segment = await getSegment(request, env);
    const sector = SECTOR_HEROES[segment] || SECTOR_HEROES['service'];
    const isMobile = (request.headers.get('User-Agent') || '').includes('Mobile');

    // Sektor ma'lumotini cookie ga yozish
    const response = await fetch(request);
    const newResponse = new Response(response.body, response);
    newResponse.headers.append('Set-Cookie', `sector=${{segment}}; Max-Age=86400; Path=/; Secure`);
    newResponse.headers.append('X-Segment', segment);
    newResponse.headers.append('X-Hero-Headline', sector.headline);
    newResponse.headers.append('X-Hero-Keys', sector.keys);
    newResponse.headers.append('X-Device', isMobile ? 'mobile' : 'desktop');

    return newResponse;
  }},
}};
"""

    def get_sector_for_lead(self, lead: Dict[str, Any]) -> str:
        """AmoCRM lead ma'lumotidan sektorni aniqlash."""
        name = (lead.get("name", "") or "").lower()
        biz_type = (lead.get("business_type", "") or "").lower()

        keywords = {
            "meditsina": ["med", "klinik", "shifox", "doktor", "tibbiy", "sog'liq", "hospital", "doctor", "medical"],
            "ta'lim": ["maktab", "universitet", "o'quv", "ta'lim", "education", "school", "kurs"],
            "retail": ["do'kon", "magazin", "savdo", "retail", "shop", "store", "bozor"],
            "food": ["restoran", "kafe", "oshxona", "food", "cafe", "restaurant", "taom", "milliy"],
            "service": ["xizmat", "service", "konsalting", "consult", "transport", "logistika"],
        }

        for sector, words in keywords.items():
            for word in words:
                if word in name or word in biz_type:
                    return sector
        return "service"