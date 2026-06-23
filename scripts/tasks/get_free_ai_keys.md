# Bepul AI API Kalitlarini Yig'ish — Vazifa

## Maqsad
Quyidagi 10 ta bepul AI provider dan API kalitlarini olish va `.env` faylga qo'shish.

## Providerlar

### 1. Groq ✅ BOR
- Sayt: https://console.groq.com
- Model: Llama 3.3 70B, Mixtral 8x7B
- Bepul: ✅ cheksiz
- Kalit: `GROQ_API_KEY` — HOZIR BOR

### 2. Google Gemini ✅ BOR
- Sayt: https://aistudio.google.com/apikey
- Model: 2.0 Flash, 2.5 Flash
- Bepul: ✅ 1500 req/kun
- Kalit: `GEMINI_API_KEY` — HOZIR BOR

### 3. DeepSeek ✅ BOR
- Sayt: https://platform.deepseek.com
- Model: deepseek-chat
- Bepul: 💰 $0.14/1M (arzon)
- Kalit: `DEEPSEEK_API_KEY` — HOZIR BOR

### 4. Cerebras ⏳ KERAK
- Sayt: https://cloud.cerebras.ai
- Model: Llama 3.3 70B
- Bepul: ✅ 1000 req/kun, juda tez (300+ tok/s)
- Ro'yxatdan o'tish: Google/GitHub bilan
- Kalit: `CEREBRAS_API_KEY`

### 5. SambaNova ⏳ KERAK
- Sayt: https://cloud.sambanova.ai
- Model: Meta-Llama-3.3-70B-Instruct
- Bepul: ✅ 100 req/min
- Ro'yxatdan o'tish: Email bilan
- Kalit: `SAMBANOVA_API_KEY`

### 6. Together AI ⏳ KERAK
- Sayt: https://api.together.xyz
- Model: meta-llama/Llama-3-70b-chat-hf
- Bepul: ✅ $1 bepul kredit (yangi akkaunt)
- Ro'yxatdan o'tish: Google/GitHub bilan
- Kalit: `TOGETHER_API_KEY`

### 7. OpenRouter ⏳ KERAK
- Sayt: https://openrouter.ai
- Model: meta-llama/llama-3.3-70b-instruct:free
- Bepul: ✅ ba'zi modellar bepul
- Ro'yxatdan o'tish: Google/GitHub bilan
- Kalit: `OPENROUTER_API_KEY`

### 8. Hugging Face ⏳ KERAK
- Sayt: https://huggingface.co/settings/tokens
- Model: Barcha open modellar
- Bepul: ✅ bepul inference API
- Ro'yxatdan o'tish: Email bilan
- Kalit: `HUGGINGFACE_API_KEY`

### 9. Cloudflare Workers AI ✅ BOR
- Sayt: https://dash.cloudflare.com → AI → Workers AI
- Model: Llama, Falcon
- Bepul: ✅ 10k req/kun
- Kalit: `CLOUDFLARE_AI_API_TOKEN` — HOZIR BOR

### 10. Mistral ⏳ KERAK
- Sayt: https://console.mistral.ai
- Model: mistral-small, mistral-medium
- Bepul: ✅ bepul tier (yangi akkaunt)
- Ro'yxatdan o'tish: Email bilan
- Kalit: `MISTRAL_API_KEY`

## Vazifa
Har bir provider uchun:
1. Saytga kir
2. Ro'yxatdan o't (Google/GitHub bilan tez)
3. API kalitini o'girib ol
4. Quyidagi formatda qaytar:

```
CEREBRAS_API_KEY=csr_...
SAMBANOVA_API_KEY=...
TOGETHER_API_KEY=...
OPENROUTER_API_KEY=sk-or-...
HUGGINGFACE_API_KEY=hf_...
MISTRAL_API_KEY=...
```

## Prioritet
1. Cerebras (eng tez, bepul)
2. SambaNova (tez, bepul)
3. Together ($1 bepul kredit)
4. OpenRouter (bepul modellar)
5. Hugging Face (sekin lekin bepul)
6. Mistral (bepul tier)
