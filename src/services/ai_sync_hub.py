class AIFactory:
    """ChatGPT, Claude, Gemini, Perplexity va Manus AI modellarini boshqarish markazi."""
    
    @staticmethod
    def get_service(platform: str):
        """Platformaga qarab tegishli AI xizmatini qaytaradi."""
        platform = platform.lower()
        if platform == "openai":
            return OpenAIService()
        elif platform == "claude":
            return ClaudeService()
        elif platform == "perplexity":
            return PerplexityService()
        elif platform == "manus":
            return ManusService()
        else:
            raise ValueError(f"Unknown platforma: {platform}")

class OpenAIService:
    def chat(self, prompt: str, user_id=None):
        import openai
        # API kalitni os.environ dan oladi
        client = openai.OpenAI()
        logger.info(f"[OPENAI] Chat prompt: {prompt[:50]}...")
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}]
        )
        return response.choices[0].message.content

class ClaudeService:
    def chat(self, prompt: str, user_id=None):
        from anthropic import Anthropic
        client = Anthropic()
        logger.info(f"[CLAUDE] Chat prompt: {prompt[:50]}...")
        message = client.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}]
        )
        return message.content[0].text

class PerplexityService:
    def chat(self, prompt: str, user_id=None):
        import requests
        api_key = os.getenv("PERPLEXITY_API_KEY")
        url = "https://api.perplexity.ai/chat/completions"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        data = {
            "model": "pplx-7b-online",
            "messages": [{"role": "user", "content": prompt}]
        }
        logger.info(f"[PERPLEXITY] Search prompt: {prompt[:50]}...")
        response = requests.post(url, headers=headers, json=data)
        if response.status_code == 200:
            return response.json()['choices'][0]['message']['content']
        return f"Perplexity Error: {response.status_code}"

class ManusService:
    def chat(self, prompt: str, user_id=None):
        # Manus AI hozircha beta bosqichida, API wrapper orqali ishlaydi
        logger.info(f"[MANUS] Agent prompt: {prompt[:50]}...")
        return "Manus AI integratsiyasi tayyorlanmoqda. Bu model avtonom agent sifatida ishlaydi."

class AISyncHub:
    # Existing ingest methods...
    """OpenAI, Claude, Gemini va Manus suhbatlarini birlashtirish moduli."""

    @staticmethod
    def ingest_openai_export(json_file_path, user_id):
        """ChatGPT dan eksport qilingan JSON ma'lumotlarini Oisha xotirasiga o'tkazish."""
        try:
            with open(json_file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            conn = sqlite3.connect("bot_memory.db")
            cursor = conn.cursor()
            
            count = 0
            for conversation in data:
                title = conversation.get('title', 'No Title')
                mapping = conversation.get('mapping', {})
                for node_id in mapping:
                    node = mapping[node_id]
                    message = node.get('message')
                    if message and message.get('content'):
                        content_parts = message['content'].get('parts', [])
                        text = " ".join([str(p) for p in content_parts if isinstance(p, str)])
                        role = message.get('author', {}).get('role', 'unknown')
                        
                        if text.strip():
                            # Oisha xotirasiga 'External Knowledge' sifatida saqlaymiz
                            fact = f"ChatGPT ({title}) - {role}: {text[:500]}..."
                            cursor.execute("INSERT INTO learned_facts (user_id, fact) VALUES (?, ?)", (user_id, fact))
                            count += 1
            
            conn.commit()
            conn.close()
            logger.info(f"[SYNC] Ingested {count} messages from OpenAI export for user {user_id}")
            return f"{count} ta xabar muvaffaqiyatli sinxronizatsiya qilindi."
        except Exception as e:
            logger.error(f"[OPENAI SYNC ERROR] {e}")
            return f"Xatolik yuz berdi: {e}"

    @staticmethod
    def sync_new_thread(platform, thread_id, messages, user_id):
        """Yangi suhbatlarni real vaqtda sinxronizatsiya qilish (API orqali)."""
        # Bu yerda API orqali kelgan xabarlarni bazaga saqlash logikasi
        try:
            conn = sqlite3.connect("bot_memory.db")
            cursor = conn.cursor()
            for msg in messages:
                fact = f"{platform} (Live) - {msg['role']}: {msg['content']}"
                cursor.execute("INSERT INTO learned_facts (user_id, fact) VALUES (?, ?)", (user_id, fact))
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            logger.error(f"[{platform} LIVE SYNC ERROR] {e}")
            return False
