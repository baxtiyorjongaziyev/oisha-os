"""
Classification prompt template and builder for CRM lead auditor.
"""
import json
from typing import Any, Dict


def build_classification_prompt(context: Dict[str, Any]) -> str:
    return (
        "Siz Oisha-OS Surgical Agent tizimining aloqalarni tahlil qilish va saralash xizmatining bir bo'lagisiz. "
        "Sizga amoCRM dagi bitim nomi, bitimning to'liq har bir maydoni (field), bitimdagi izohlar va eslatmalar tarixi (notes_history), kontakt ma'lumotlari, qo'ng'iroq yozuvlari tahlili/tarixi, "
        "Telegram shaxsiy va guruh yozishmalari tarixi, amoCRM bitimidagi vazifalar (zadachalar) tarixi hamda ularga berilgan javoblar/izohlar, "
        "va Telegram chatlaridagi javobsiz qolib ketgan suhbatlar holati taqdim etiladi.\n\n"
        "Sizning vazifangiz taqdim etilgan barcha ma'lumotlarni, jumladan sdelkaning har bir fieldini, vazifalar va ularning bajarilish javoblarini, ayniqsa notes_history dagi izohlarni chuqur tahlil qilib, quyidagi natijalarni ishlab chiqish:\n\n"
        "1. **Tasniflash (category)**: Kontaktni quyidagi 5 ta toifadan faqat bittasiga tasniflash:\n"
        "   - Mijoz: Brending, SMM, sayt yaratish, dizayn kabi xizmatlarimizni so'ragan, sotib olgan, narxi yoki tijorat taklifi bilan qiziqqan har qanday shaxs.\n"
        "   - Shaxsiy: Shaxsiy oila a'zolari, do'stlar yoki biznesga mutlaqo aloqasi bo'lmagan shaxsiy masaladagi suhbatdoshlar.\n"
        "   - Kandidat: Ish so'rab kelganlar, rezyume (CV) tashlaganlar, vakansiya yoki amaliyot haqida so'raganlar.\n"
        "   - Hamkor/Jamoa: Jamoamiz a'zolari (xodimlar), hamkorlar yoki birgalikda ish olib borayotgan tashqi hamkorlar.\n"
        "   - Boshqa: Spam qo'ng'iroqlar, xato tushganlar, yoki suhbat tarixi bo'sh bo'lgan va aniq toifaga kirmaydigan kontaktlar. SHUNINGDEK, agar notes_history da mijoz bo'lmaganligi, puli qaytarilganligi yoki bitim bekor qilinganligi (masalan, 'mijozimiz emas', 'ishlab bo'lmaydi', 'pulini qaytarganmiz', 'junk', 'reject') aniq yozilgan bo'lsa, uni Boshqa toifasiga kiriting.\n\n"
        "2. **Tasniflash sababi (explanation)**: Qisqa va londa o'zbek tilida (lotin alifbosida) tasniflash sababi.\n\n"
        "3. **Mukammal Tahlil Xulosasi (detailed_summary)**: Har bir mijozning ma'lumotlarini (Telefon qo'ng'iroqlari, Telegram shaxsiy va guruh yozishmalari, sdelka maydonlari, vazifalar tarixi va ularning bajarilish izohlari) to'liq tahlil qilib, o'zbek tilida (lotin alifbosida) professional biznes-konsalting ohangida yozilgan mukammal xulosa. \n"
        "Xulosaning oxiriga har doim va faqat haqiqiy faol mijozlar uchun quyidagi maslahatni qo'shing:\n"
        "   '💡 Menejerga maslahat: Vazifa bajarilgach, uni amoCRMda \"Bajarildi\" deb belgilang va bajarilish izohini yozing. Oisha boti bajarilgan vazifalar tarixi va izohlarini to'liq tahlil qiladi va qayta takroriy vazifa yaratilishining oldini oladi.'\n\n"
        "4. **Keyingi Qadam Vazifasi (next_step_task)**: Mas'ul menejer uchun keyingi qadam bo'yicha aniq vazifa matni. \n"
        "   - **MUHIM QOIDA (Takroriy vazifalarni oldini olish va bekorchi bitimlar)**:\n"
        "     - Agar bitimdagi izohlar yoki eslatmalar (notes_history) ichida 'mijozimiz emas', 'ishlamaymiz', 'pulini qaytarganmiz', 'ishlab bo'lmaydi', 'junk' yoki shunga o'xshash mijoz bo'lmaganligi yoki bitim tugatilganligi haqidagi ma'lumotlar mavjud bo'lsa, keyingi qadam vazifasini mutlaqo yozmang (bo'sh satr '' qoldiring).\n"
        "     - Agar keyingi qadam vazifasi taqdim etilgan vazifalar tarixida (tasks_history) allaqachon bajarilgan bo'lsa yoki hozirda faol bo'lsa, xuddi shu vazifani qaytadan yaratishni tavsiya qilmang. Buning o'rniga yangi mantiqiy vazifa yozing.\n"
        "     - Agar bitim toifasi 'Boshqa' (Other) deb saralansa va faol biznes vazifasi talab etilmasa, keyingi qadam vazifasini bo'sh satr ('') qoldiring.\n"
        "     - Telegram javobsiz xabarlar: Agar 'telegram_unanswered_info' maydoni mijozning xabari javobsiz qolganini ko'rsatsa, birinchi navbatda Telegramda mijozga javob yozish vazifasini qo'ying.\n"
        "     - Agar mutlaqo yangi vazifa qo'yish shart bo'lmasa yoki barcha ishlar yakunlangan bo'lsa, 'next_step_task' maydonini bo'sh satr ('') qoldiring.\n\n"
        "5. **Telegram Draft Reply (telegram_draft_reply)**: Mijozning shaxsiy Telegramdagi oxirgi javobsiz xabariga taklif qilinayotgan javob matni (o'zbek tilida, lotin alifbosida, samimiy va professional ohangda). Agar shaxsiy Telegram chatida mijozning xabari javobsiz qolgan bo'lsa, ushbu maydonga tahminiy javob matnini yozing. Userbot buni shaxsiy chatda avtomatik ravishda qoralama (draft) qilib qo'yadi. Agar javobsiz xabar bo'lmasa, bo'sh satr ('') qaytaring.\n\n"
        "Javobni quyidagi JSON formatida qaytaring, boshqa hech qanday qo'shimcha tushuntirish va markdown belgilari (masalan, ```json) yozmang:\n"
        "{\n"
        '  "category": "Mijoz|Shaxsiy|Kandidat|Hamkor/Jamoa|Boshqa",\n'
        '  "explanation": "Tasniflash sababi...",\n'
        '  "detailed_summary": "Tahlil xulosasi...",\n'
        '  "next_step_task": "Menejer uchun vazifa...",\n'
        '  "telegram_draft_reply": "Taklif etiladigan javob matni..."\n'
        "}\n\n"
        f"Kontekst JSON:\n{json.dumps(context, ensure_ascii=False, default=str)}"
    )
