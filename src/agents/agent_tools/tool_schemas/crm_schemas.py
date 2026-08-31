"""
CRM tool declarations schema for Gemini Function Calling.
"""
CRM_TOOL_DECLARATIONS = [   {   'description': "Mijoz haqidagi ma'lumotni CRM bazaga saqlash. Agar mijoz ism, telefon "
                       "raqam, biznes turi, hudud yoki boshqa kontakt ma'lumotlarini berib qo'ysa, "
                       "BU TOOLNI CHAQIRING. Barcha ma'lumotlar ixtiyoriy — faqat mavjud "
                       "bo'lganlarini yuboring.",
        'name': 'save_lead_info',
        'parameters': {   'properties': {   'brand_name': {   'description': 'Brend yoki kompaniya '
                                                                             'nomi',
                                                              'type': 'string'},
                                            'business_type': {   'description': 'Biznes turi '
                                                                                '(restoran, salon, '
                                                                                "do'kon va h.k.)",
                                                                 'type': 'string'},
                                            'deadline': {   'description': 'Muddat yoki sana '
                                                                           "(masalan: '2 hafta', "
                                                                           "'1 mart')",
                                                            'type': 'string'},
                                            'lead_quality': {   'description': 'Lead sifati: '
                                                                               "'Sifatli', "
                                                                               "'Oddiy', yoki "
                                                                               "'Unknown'",
                                                                'enum': [   'Sifatli',
                                                                            'Oddiy',
                                                                            'Unknown',
                                                                            'Sifatsiz'],
                                                                'type': 'string'},
                                            'name': {   'description': 'Mijoz ismi (Telegram ismi '
                                                                       "yoki o'zi aytgan ism)",
                                                        'type': 'string'},
                                            'phone': {   'description': 'Telefon raqam '
                                                                        '(+998XXXXXXXXX formatida)',
                                                         'type': 'string'},
                                            'region': {   'description': 'Hudud yoki shahar '
                                                                         '(Toshkent, Samarqand va '
                                                                         'h.k.)',
                                                          'type': 'string'},
                                            'service_type': {   'description': 'Kerakli xizmat '
                                                                               '(logo, naming, '
                                                                               'branding '
                                                                               'strategiya va '
                                                                               'h.k.)',
                                                                'type': 'string'},
                                            'user_id': {   'description': 'Telegram foydalanuvchi '
                                                                          'ID si',
                                                           'type': 'integer'}},
                          'required': ['user_id'],
                          'type': 'object'}},
    {   'description': "Mijozni Google Contacts ga saqlash. Telefon raqami va ism mavjud bo'lsa, "
                       'bu toolni chaqiring. save_lead_info dan farqi: bu Google Contacts da '
                       'saqlaydi (sinxronizatsiya uchun).',
        'name': 'save_google_contact',
        'parameters': {   'properties': {   'name': {'description': 'Mijoz ismi', 'type': 'string'},
                                            'note': {   'description': "Qo'shimcha izoh (masalan: "
                                                                       'kerakli xizmat)',
                                                        'type': 'string'},
                                            'phone': {   'description': 'Telefon raqam',
                                                         'type': 'string'}},
                          'required': ['name', 'phone'],
                          'type': 'object'}},
    {   'description': "Mijoz ma'lumotlarini CRM Telegram guruhiga yuborish. Mijoz to'liq "
                       "ma'lumotlarini bergandan so'ng (ism, telefon, xizmat turi) buni chaqiring. "
                       "Sifatli lead bo'lganda majburiy.",
        'name': 'forward_to_crm_group',
        'parameters': {   'properties': {   'quality': {   'description': 'Lead sifati',
                                                           'enum': [   'Sifatli',
                                                                       'Oddiy',
                                                                       'Unknown',
                                                                       'Sifatsiz'],
                                                           'type': 'string'},
                                            'summary': {   'description': "Mijoz so'rovining "
                                                                          'qisqacha bayoni',
                                                           'type': 'string'},
                                            'user_id': {   'description': 'Telegram user ID',
                                                           'type': 'integer'}},
                          'required': ['user_id', 'quality'],
                          'type': 'object'}},
    {   'description': "Inson jamoa a'zosiga (masalan: PM, Dizayner, CEO) yangi vazifa/topshiriq "
                       "biriktirish. Mijozdan lead tushganda yoki uchrashuv so'ralganda ALBATTA "
                       'topshiriq yarating.',
        'name': 'assign_task_to_human',
        'parameters': {   'properties': {   'assigned_to': {   'description': 'Vazifa '
                                                                              'biriktiriladigan '
                                                                              'xodimning Telegram '
                                                                              'ID si',
                                                               'type': 'integer'},
                                            'deadline': {   'description': 'Muddat (masalan: '
                                                                           "'Bugun', 'Ertaga soat "
                                                                           "18:00')",
                                                            'type': 'string'},
                                            'description': {   'description': 'Vazifa haqida '
                                                                              "to'liq tafsilotlar",
                                                               'type': 'string'},
                                            'title': {   'description': 'Vazifa nomi (qisqa va '
                                                                        'aniq)',
                                                         'type': 'string'}},
                          'required': ['assigned_to', 'title', 'description'],
                          'type': 'object'}},
    {   'description': 'Mijozning AmoCRM dagi joriy holatini tekshirish. Agar mijoz loyiha qaysi '
                       "etapda ekanligini so'rasa yoki 'status' haqida gapirsa chaqiring.",
        'name': 'get_crm_status_tool',
        'parameters': {   'properties': {   'user_id': {   'description': 'Telegram user ID',
                                                           'type': 'integer'}},
                          'required': ['user_id'],
                          'type': 'object'}},
    {   'description': "AmoCRM dagi bitim (lead) statusini o'zgartirish. Muloqot yangi bosqichga "
                       "o'tganda (masalan: uchrashuv belgilandi, narx so'raldi, mijoz qiziqish "
                       'bildirdi) buni ALBATTA chaqiring.',
        'name': 'update_lead_status',
        'parameters': {   'properties': {   'status_name': {   'description': 'Yangi status nomi',
                                                               'enum': [   'Initial Contact',
                                                                           'Negotiation',
                                                                           'Qualified',
                                                                           'Interested',
                                                                           'Meeting Scheduled',
                                                                           'Conversation Over',
                                                                           'Closed Lost'],
                                                               'type': 'string'},
                                            'user_id': {   'description': 'Telegram user ID',
                                                           'type': 'integer'}},
                          'required': ['user_id', 'status_name'],
                          'type': 'object'}},
    {   'description': 'AmoCRM ichida lead uchun keyingi follow-up vazifasini yaratish. Mijoz '
                       "keyinroq javob berishini aytsa, narx e'tirozi qolsa yoki closer follow-up "
                       "kerak bo'lsa ishlatiladi.",
        'name': 'create_followup_task',
        'parameters': {   'properties': {   'details': {   'description': "Vazifa bo'yicha aniq "
                                                                          'next step yoki izoh',
                                                           'type': 'string'},
                                            'due_at': {   'description': 'ISO 8601 muddat vaqti',
                                                          'type': 'string'},
                                            'due_in_hours': {   'description': 'Agar due_at '
                                                                               "bo'lmasa, hozirdan "
                                                                               'necha soatdan '
                                                                               'keyin bajariladi',
                                                                'type': 'integer'},
                                            'lead_id': {   'description': 'AmoCRM lead ID. '
                                                                          "To'g'ridan-to'g'ri lead "
                                                                          "ma'lum bo'lsa "
                                                                          'ishlatiladi.',
                                                           'type': 'integer'},
                                            'title': {   'description': 'Follow-up vazifa nomi',
                                                         'type': 'string'},
                                            'user_id': {   'description': 'Telegram user ID. '
                                                                          'lead_id berilmasa shu '
                                                                          'orqali lead topiladi.',
                                                           'type': 'integer'}},
                          'required': ['title'],
                          'type': 'object'}},
    {   'description': "AmoCRM lead kartasiga negotiation yoki follow-up bo'yicha izoh yozish. "
                       "E'tiroz, meeting natijasi yoki keyingi qadamni CRM tarixiga qoldirish "
                       'uchun ishlatiladi.',
        'name': 'add_lead_note',
        'parameters': {   'properties': {   'lead_id': {   'description': 'AmoCRM lead ID',
                                                           'type': 'integer'},
                                            'note': {   'description': 'CRMga yoziladigan izoh '
                                                                       'matni',
                                                        'type': 'string'},
                                            'user_id': {   'description': 'Telegram user ID. '
                                                                          'lead_id berilmasa shu '
                                                                          'orqali lead topiladi.',
                                                           'type': 'integer'}},
                          'required': ['note'],
                          'type': 'object'}},
    {   'description': "Mijoz ma'lumotlarini (xizmat turi, manba, qiziqish darajasi) AmoCRM "
                       'maydonlariga va teglarga avtomatik saqlash. Mijoz niyatini '
                       'aniqlaganingizda chaqiring.',
        'name': 'qualify_lead',
        'parameters': {   'properties': {   'budget_range': {   'enum': [   '< 500$',
                                                                            '500$ - 1500$',
                                                                            '1500$ - 3000$',
                                                                            '> 3000$'],
                                                                'type': 'string'},
                                            'need': {   'description': 'Mijozning asosiy ehtiyoji '
                                                                       'yoki muammosi',
                                                        'type': 'string'},
                                            'service': {   'enum': [   'Naming',
                                                                       'Logo',
                                                                       'Brandbook',
                                                                       'Web',
                                                                       'SMM'],
                                                           'type': 'string'},
                                            'source': {   'enum': [   'Telegram',
                                                                      'Instagram',
                                                                      'Facebook',
                                                                      'Sayt'],
                                                          'type': 'string'},
                                            'tag': {   'description': "Qo'shimcha teg (masalan: "
                                                                      "'High-Intent')",
                                                       'type': 'string'},
                                            'temperature': {   'enum': ['Sovuq', 'Issiq'],
                                                               'type': 'string'},
                                            'user_id': {   'description': 'Telegram user ID',
                                                           'type': 'integer'}},
                          'required': ['user_id'],
                          'type': 'object'}},
    {   'description': "AmoCRM da lidlarni qidirish. Jamoa guruhida 'Abdulladan to'lov keldimi', "
                       "'Nike loyihasi qayerda', 'bugun nechta yangi lid bor' kabi savollarda BU "
                       'TOOLNI CHAQIRING.',
        'name': 'search_crm_leads',
        'parameters': {   'properties': {   'limit': {   'description': 'Nechta natija qaytarilsin '
                                                                        '(default: 5)',
                                                         'type': 'integer'},
                                            'query': {   'description': 'Qidiruv matni: mijoz '
                                                                        'ismi, kompaniya yoki '
                                                                        'telefon',
                                                         'type': 'string'}},
                          'required': [],
                          'type': 'object'}}]
