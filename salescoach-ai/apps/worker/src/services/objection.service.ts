import Anthropic from '@anthropic-ai/sdk';

export type ObjectionType =
  | 'price_high'
  | 'need_to_think'
  | 'competitor_comparison'
  | 'no_budget'
  | 'timing_bad'
  | 'no_authority'
  | 'not_interested'
  | 'quality_doubt'
  | 'unknown';

export interface DetectedObjection {
  type: ObjectionType;
  quote: string;           // Exact text from transcript
  start: number;           // Timestamp in seconds
  severity: 'low' | 'medium' | 'high';
  suggestedResponse: string;
  followUpQuestion: string;
}

export interface ObjectionReport {
  callId: string;
  totalObjections: number;
  handledSuccessfully: number;
  unhandled: DetectedObjection[];
  objectionsByType: Record<ObjectionType, number>;
  overallObjectionScore: number; // 0-100, higher = better handling
  scriptSuggestions: string[];
}

const OBJECTION_PATTERNS: Record<ObjectionType, RegExp[]> = {
  price_high: [
    /qimmat/i, /narx(i)?\s*(baland|ko'p|oshiq|yuqori)/i, /arzon(roq)?/i,
    /chegirma/i, /bu qadar/i, /budget(im)?\s*(yo'q|kam|cheklangan)/i,
  ],
  need_to_think: [
    /o'ylab ko'ray/i, /o'ylayman/i, /keyinroq/i, /hozir(cha)?\s*(emas|yo'q)/i,
    /vaqt bering/i, /qaror\s*(qilmadim|bermadim)/i,
  ],
  competitor_comparison: [
    /boshqa\s*(kompaniya|agentlik|joy)/i, /ular\s*(arzon|yaxshi|yaxshiroq)/i,
    /raqobatchi/i, /taqqoslab/i, /boshqa(lar)?dan so'rayman/i,
  ],
  no_budget: [
    /pul\s*(yo'q|kam|etmaydi)/i, /byudjet\s*(yo'q|cheklangan)/i,
    /moliya(viy)?\s*(qiyinchilik|muammo)/i, /hozir\s*(to'lay\s*olmay|imkonim yo'q)/i,
  ],
  timing_bad: [
    /hozir\s*(vaqt(im)?\s*yo'q|band)/i, /keyingi\s*(oy|hafta|yil)/i,
    /fasl(dan so'ng)?/i, /loyiha\s*(tugganda|boshlanda)/i,
  ],
  no_authority: [
    /direktor(im)?ga\s*(so'ray|aytay)/i, /rahbariy(at)?dan\s*ruxsat/i,
    /o'zim\s*(qaror\s*bera\s*olmayman|bilmayman)/i,
    /hamkor(im)? bilan\s*(maslahatlash|gaplash)/i,
  ],
  not_interested: [
    /qiziqmay(man)?/i, /kerak\s*(emas|emas\s*hozir)/i,
    /to'xtatamiz/i, /bekor\s*qilamiz/i,
  ],
  quality_doubt: [
    /sifat(i)?\s*(yaxshi\s*emas|past|shubhali)/i, /ishona\s*(olmay|qiyin)/i,
    /misol\s*(ko'rsating|bering)/i, /portfolio/i,
    /avvalgi\s*(ish(lar)?|mijozlar)/i,
  ],
  unknown: [],
};

const RESPONSE_SCRIPTS: Record<ObjectionType, { response: string; followUp: string }> = {
  price_high: {
    response:
      'Narx masalasini tushunaman. Lekin bizning xizmat ROI hisobi bo\'yicha odatda 3 oy ichida o\'zini qoplaydi. Qaysi qism narxini yuqori deb hisdingiz?',
    followUp: 'Byudjetingiz qanday oraliqda? Moslashtirish imkonimiz bor.',
  },
  need_to_think: {
    response:
      'Albatta, muhim qaror. Qaysi nuqta aniq bo\'lmadi? Hoziroq javob bera olaman — bu qaror qabul qilishni osonlashtiradi.',
    followUp: 'Qachon gaplashsak qulay bo\'ladi?',
  },
  competitor_comparison: {
    response:
      'Taqqoslab ko\'rish to\'g\'ri qaror. Bizning farqimiz — loyiha jarayonida to\'liq shaffoflik va 30 kunlik bepul tuzatish. Ularning shartlari qanday?',
    followUp: 'Qaysi agentlik bilan taqqoslyapsiz?',
  },
  no_budget: {
    response:
      'Moliyaviy reja topish mumkin. Bosqichma-bosqich to\'lov yoki kichikroq boshlang\'ich paketi taklif qila olamiz.',
    followUp: 'Hozir qancha byudjet ajrata olasiz?',
  },
  timing_bad: {
    response:
      'Vaqt tanlash muhim. Hozir boshlamasak ham, keyinroq murojaat qilsangiz slot bo\'lmasligi mumkin. Qachon boshlash qulay?',
    followUp: 'Taxminan qaysi oyda boshlashni rejalashtiryapsiz?',
  },
  no_authority: {
    response:
      'Tushunaman. Direktor uchun qisqa prezentatsiya yoki hisob-kitob tayyorlab bera olaman. Bu qaror qabul qilishni osonlashtiradi.',
    followUp: 'Direktoringiz bilan uchrashuvni tashkil qila olamizmi?',
  },
  not_interested: {
    response:
      'Mayli, majburlamayman. Faqat bitta savol: qaysi soha xizmati siz uchun hozir eng muhim?',
    followUp: 'Agar kelajakda kerak bo\'lsa, raqamimni qoldirayinmi?',
  },
  quality_doubt: {
    response:
      'Sifat bo\'yicha xavotir tushunarli. Bizning portfoliomizdan shunga o\'xshash 3 ta loyiha ko\'rsatib bera olaman. Sohangizga mos misollar bormi?',
    followUp: 'Qaysi turdagi ishlar ko\'rmoqchisiz?',
  },
  unknown: {
    response: 'Bu haqda ko\'proq gaplashsak bo\'ladimi? Nima xavotirlantiryapti?',
    followUp: 'Qanday savolingiz bor?',
  },
};

/**
 * ObjectionHandlerAgent — detects sales objections in transcript and
 * provides scored handling analysis + scripted response suggestions.
 */
export class ObjectionService {
  private client: Anthropic;

  constructor() {
    this.client = new Anthropic({ apiKey: process.env['ANTHROPIC_API_KEY'] });
  }

  async analyze(
    callId: string,
    transcript: string,
    segments: Array<{ speaker: string; text: string; start: number }>,
    language: 'uz' | 'ru' | 'en' = 'uz',
  ): Promise<ObjectionReport> {
    // Fast path: pattern matching on customer segments
    const customerSegments = segments.filter((s) => s.speaker === 'customer');
    const patternObjections = this._detectByPattern(customerSegments);

    // Deep path: LLM analysis for nuanced objections
    const llmObjections = await this._detectByLLM(transcript, language);

    // Merge, deduplicate by timestamp proximity
    const allObjections = this._merge(patternObjections, llmObjections);

    return this._buildReport(callId, allObjections, segments);
  }

  private _detectByPattern(
    segments: Array<{ text: string; start: number }>,
  ): DetectedObjection[] {
    const detected: DetectedObjection[] = [];

    for (const seg of segments) {
      for (const [type, patterns] of Object.entries(OBJECTION_PATTERNS) as [ObjectionType, RegExp[]][]) {
        if (type === 'unknown') continue;
        const matched = patterns.some((p) => p.test(seg.text));
        if (matched) {
          const script = RESPONSE_SCRIPTS[type];
          detected.push({
            type,
            quote: seg.text,
            start: seg.start,
            severity: this._severity(type),
            suggestedResponse: script.response,
            followUpQuestion: script.followUp,
          });
          break;
        }
      }
    }

    return detected;
  }

  private async _detectByLLM(
    transcript: string,
    language: string,
  ): Promise<DetectedObjection[]> {
    if (!process.env['ANTHROPIC_API_KEY']) return [];

    const prompt = `Analyze this sales call transcript in ${language} language.
Identify every sales objection raised by the CUSTOMER.

For each objection return a JSON array item:
{
  "type": one of [price_high, need_to_think, competitor_comparison, no_budget, timing_bad, no_authority, not_interested, quality_doubt, unknown],
  "quote": exact customer quote (max 100 chars),
  "start": approximate timestamp in seconds (estimate from context),
  "severity": "low"|"medium"|"high",
  "suggestedResponse": best sales response in ${language},
  "followUpQuestion": best follow-up question in ${language}
}

Transcript:
${transcript.slice(0, 4000)}

Return ONLY valid JSON array. Empty array if no objections.`;

    try {
      const resp = await this.client.messages.create({
        model: 'claude-sonnet-4-6',
        max_tokens: 1024,
        messages: [{ role: 'user', content: prompt }],
      });
      const block = resp.content[0];
      const text = block?.type === 'text' ? block.text : '[]';
      return JSON.parse(text.match(/\[[\s\S]*\]/)?.[0] ?? '[]');
    } catch {
      return [];
    }
  }

  private _merge(
    pattern: DetectedObjection[],
    llm: DetectedObjection[],
  ): DetectedObjection[] {
    const merged = [...pattern];
    for (const llmObj of llm) {
      const duplicate = merged.some(
        (p) => Math.abs(p.start - llmObj.start) < 5 && p.type === llmObj.type,
      );
      if (!duplicate) merged.push(llmObj);
    }
    return merged.sort((a, b) => a.start - b.start);
  }

  private _buildReport(
    callId: string,
    objections: DetectedObjection[],
    allSegments: Array<{ speaker: string; text: string; start: number }>,
  ): ObjectionReport {
    const managerSegments = allSegments.filter((s) => s.speaker === 'manager');
    let handledCount = 0;

    // Simple heuristic: objection is "handled" if manager speaks > 30s after it
    const unhandled: DetectedObjection[] = [];
    for (const obj of objections) {
      const nextManagerSeg = managerSegments.find((m) => m.start > obj.start);
      if (nextManagerSeg) {
        handledCount++;
      } else {
        unhandled.push(obj);
      }
    }

    const byType: Record<ObjectionType, number> = {
      price_high: 0, need_to_think: 0, competitor_comparison: 0,
      no_budget: 0, timing_bad: 0, no_authority: 0, not_interested: 0,
      quality_doubt: 0, unknown: 0,
    };
    for (const obj of objections) byType[obj.type]++;

    const handleRatio = objections.length > 0
      ? handledCount / objections.length
      : 1;
    const overallScore = Math.round(handleRatio * 100);

    const scriptSuggestions = [...new Set(
      unhandled.map((o) => RESPONSE_SCRIPTS[o.type].response)
    )];

    return {
      callId,
      totalObjections: objections.length,
      handledSuccessfully: handledCount,
      unhandled,
      objectionsByType: byType,
      overallObjectionScore: overallScore,
      scriptSuggestions,
    };
  }

  private _severity(type: ObjectionType): 'low' | 'medium' | 'high' {
    const high: ObjectionType[] = ['not_interested', 'no_budget', 'no_authority'];
    const medium: ObjectionType[] = ['price_high', 'competitor_comparison', 'quality_doubt'];
    if (high.includes(type)) return 'high';
    if (medium.includes(type)) return 'medium';
    return 'low';
  }
}
