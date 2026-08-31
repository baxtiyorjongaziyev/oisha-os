"""
General service and collaboration tool declarations schema for Gemini Function Calling.
"""
GENERAL_TOOL_DECLARATIONS = [   {   'description': 'Google Calendar da uchrashuv yoki tadbir yaratish. Mijoz aniq sana va vaqt '
                       "bilan uchrashuvni tasdiqlasa yoki 'ertaga soat 14da' kabi vaqt belgilab "
                       "qo'ysa, BU TOOLNI CHAQIRING.",
        'name': 'create_calendar_event',
        'parameters': {   'properties': {   'description': {   'description': 'Uchrashuv tavsifi '
                                                                              "yoki qo'shimcha "
                                                                              "ma'lumot",
                                                               'type': 'string'},
                                            'end_time': {   'description': 'Tugash vaqti ISO 8601 '
                                                                           'formatida. '
                                                                           "Ko'rsatilmasa, 1 soat "
                                                                           "qo'shiladi.",
                                                            'type': 'string'},
                                            'start_time': {   'description': 'Boshlanish vaqti ISO '
                                                                             '8601 formatida '
                                                                             '(masalan: '
                                                                             "'2026-03-13T14:00:00')",
                                                              'type': 'string'},
                                            'summary': {   'description': 'Uchrashuv mavzusi yoki '
                                                                          'nomi',
                                                           'type': 'string'}},
                          'required': ['summary', 'start_time'],
                          'type': 'object'}},
    {   'description': "Foydalanuvchiga Telegram Stars to'lov invoice yuborish. Mijoz sotib "
                       "olishga tayyor bo'lsa yoki raqamli mahsulot so'rasa chaqiring.",
        'name': 'send_stars_invoice',
        'parameters': {   'properties': {   'product_id': {   'description': 'Mahsulot ID si '
                                                                             '(config.DIGITAL_PRODUCTS '
                                                                             'dan)',
                                                              'enum': [   'logo_template',
                                                                          'branding_guide'],
                                                              'type': 'string'},
                                            'user_id': {   'description': 'Invoice yuboriladigan '
                                                                          'Telegram user ID',
                                                           'type': 'integer'}},
                          'required': ['user_id', 'product_id'],
                          'type': 'object'}},
    {   'description': "Bazadan mijozning to'liq profilini olish. Eski mijoz bilan muloqot "
                       "boshlanishida yoki avvalgi ma'lumotlar kerak bo'lsa chaqiring.",
        'name': 'get_user_profile',
        'parameters': {   'properties': {   'user_id': {   'description': 'Telegram user ID',
                                                           'type': 'integer'}},
                          'required': ['user_id'],
                          'type': 'object'}},
    {   'description': "Agentlikning barcha inson jamoa a'zolarini va ularning rollarini olish. "
                       'Kimga topshiriq berishni bilmasangiz, avval buni chaqiring.',
        'name': 'get_team_members',
        'parameters': {'properties': {}, 'type': 'object'}},
    {   'description': 'Mijozning Telegram profili, bio va umumiy guruhlarini tahlil qilish '
                       "(Sherlock usuli). Yangi mijoz haqida ko'proq ma'lumot kerak bo'lsa yoki "
                       "'kimman?' deb so'rasa buni ishlating.",
        'name': 'sherlock_user_profile',
        'parameters': {   'properties': {   'user_id': {   'description': 'Tahlil qilinadigan '
                                                                          'Telegram user ID',
                                                           'type': 'integer'}},
                          'required': ['user_id'],
                          'type': 'object'}},
    {   'description': "Kompyuter (lokal disk) dagi fayllarni nomi yoki kengaytmasi bo'yicha "
                       'qidirish.',
        'name': 'search_local_files',
        'parameters': {   'properties': {   'extension': {   'description': '.pdf, .docx, .jpg '
                                                                            'kabi kengaytma '
                                                                            '(ixtiyoriy)',
                                                             'type': 'string'},
                                            'query': {   'description': 'Fayl nomi yoki '
                                                                        "qidirilayotgan kalit so'z",
                                                         'type': 'string'}},
                          'required': ['query'],
                          'type': 'object'}},
    {   'description': 'Google Drive dan fayllarni qidirish va ularning havolalarini topish.',
        'name': 'google_drive_search',
        'parameters': {   'properties': {   'query': {   'description': 'Drive dan qidirilayotgan '
                                                                        'fayl nomi',
                                                         'type': 'string'}},
                          'required': ['query'],
                          'type': 'object'}},
    {   'description': 'Tizimda xavfsiz terminal buyruqlarini bajarish (masalan: uptime, df, '
                       'netstat).',
        'name': 'execute_shell_safe',
        'parameters': {   'properties': {   'command': {   'description': 'Bajariladigan buyruq',
                                                           'type': 'string'}},
                          'required': ['command'],
                          'type': 'object'}},
    {   'description': "Airtable dan loyihalar ro'yxatini olish. Loyiha holati, deadline, mas'ul "
                       "xodim haqida so'ralganda BU TOOLNI CHAQIRING.",
        'name': 'get_airtable_projects',
        'parameters': {   'properties': {   'limit': {   'description': 'Nechta loyiha qaytarilsin '
                                                                        '(default: 10)',
                                                         'type': 'integer'},
                                            'stage_filter': {   'description': "Bosqich bo'yicha "
                                                                               'filtrlash '
                                                                               "(masalan: 'Aktiv', "
                                                                               "'Tugallangan')",
                                                                'type': 'string'}},
                          'required': [],
                          'type': 'object'}},
    {   'description': 'Bugungi statistikani olish: yangi lidlar soni, aktiv bitimlar, muddati '
                       "o'tgan loyihalar. Kunlik holat so'ralganda BU TOOLNI CHAQIRING.",
        'name': 'get_today_stats',
        'parameters': {'properties': {}, 'required': [], 'type': 'object'}}]
