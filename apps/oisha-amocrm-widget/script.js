define(['jquery'], function ($) {
    var CustomWidget = function () {
        var self = this;
        var API_BASE = "https://oisha.jonbranding.uz/api/telegram/extension";
        var currentPhone = null;
        var currentChatId = null;

        this.callbacks = {
            render: function () {
                var $container = self.render_template({
                    caption: {
                        class_name: 'js-ac-caption',
                        html: ''
                    },
                    body: '',
                    render: ''
                });

                // Vidjet interfeysini quramiz (Faqat sdelka ichida)
                if (self.system().area === 'lcard') {
                    var html = `
                        <div id="oisha-native-widget" style="margin-top:10px; border:1px solid #d4d4d5; border-radius:3px; background:#fff;">
                            <div style="background:#0088cc; color:white; padding:8px 10px; border-radius:3px 3px 0 0; font-weight:bold;">
                                <span><svg width="14" height="14" viewBox="0 0 24 24" fill="white" style="vertical-align:middle; margin-right:5px;"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm4.64 6.8c-.15 1.58-.8 5.42-1.13 7.19-.14.75-.42 1-.68 1.03-.58.05-1.02-.38-1.58-.75-.88-.58-1.38-.94-2.23-1.5-.99-.65-.35-1.01.22-1.59.15-.15 2.71-2.48 2.76-2.69a.2.2 0 00-.05-.18c-.06-.05-.14-.03-.21-.02-.09.02-1.49.95-4.22 2.79-.4.27-.76.41-1.08.4-.36-.01-1.04-.2-1.55-.37-.63-.2-1.12-.31-1.08-.66.02-.18.27-.36.74-.55 2.92-1.27 4.86-2.11 5.83-2.51 2.78-1.16 3.35-1.36 3.73-1.36.08 0 .27.02.39.12.1.08.13.19.14.27-.01.06.01.24 0 .24z"/></svg></span>
                                Telegram Chat
                            </div>
                            <div id="oisha-native-messages" style="height:250px; overflow-y:auto; padding:10px; background:#f5f5f5;">
                                <div style="text-align:center; color:#888; font-size:12px; margin-top:20px;">Mijoz raqami qidirilmoqda...</div>
                            </div>
                            <div style="display:flex; border-top:1px solid #d4d4d5;">
                                <input type="text" id="oisha-native-input" placeholder="Xabar yozing..." style="flex:1; border:none; padding:10px; outline:none; border-radius:0 0 0 3px;" disabled />
                                <button id="oisha-native-send" style="border:none; background:#0088cc; color:white; padding:0 15px; cursor:pointer; border-radius:0 0 3px 0;" disabled>></button>
                            </div>
                        </div>
                    `;
                    self.components = {
                        widget: $container.append(html)
                    };
                }
                return true;
            },
            init: function () {
                return true;
            },
            bind_actions: function () {
                if (self.system().area !== 'lcard') return true;

                // Raqamni API orqali olish (DOM'dan qidirmaymiz!)
                setTimeout(function() {
                    var leadId = AMOCRM.data.current_entity.id;
                    var contactId = null;
                    
                    // Asosiy kontaktni topamiz
                    var contacts = AMOCRM.data.current_entity.contacts;
                    if (contacts && Object.keys(contacts).length > 0) {
                        contactId = Object.keys(contacts)[0];
                    }

                    if (!contactId) {
                        $('#oisha-native-messages').html('<div style="text-align:center; color:red; font-size:12px; margin-top:20px;">Sdelkada kontakt topilmadi.</div>');
                        return;
                    }

                    // Kontakt ma'lumotlarini olish (AmoCRM JS API)
                    $.get('/api/v4/contacts/' + contactId, function(data) {
                        if (data && data.custom_fields_values) {
                            var phoneField = data.custom_fields_values.find(f => f.field_code === 'PHONE');
                            if (phoneField && phoneField.values.length > 0) {
                                currentPhone = phoneField.values[0].value.replace(/\\D/g, "");
                                loadHistory(currentPhone);
                            } else {
                                $('#oisha-native-messages').html('<div style="text-align:center; color:red; font-size:12px; margin-top:20px;">Kontaktda telefon raqami yo\\'q.</div>');
                            }
                        }
                    });
                }, 1000);

                function loadHistory(phone) {
                    $('#oisha-native-messages').html('<div style="text-align:center; color:#888; font-size:12px; margin-top:20px;">Tarix yuklanmoqda...</div>');
                    
                    $.ajax({
                        url: API_BASE + '/history?phone=' + phone,
                        type: 'GET',
                        success: function(response) {
                            if (response.success) {
                                currentChatId = response.chatId;
                                var html = '';
                                if (response.messages.length === 0) {
                                    html = '<div style="text-align:center; color:#888; font-size:12px; margin-top:20px;">Xabarlar topilmadi.</div>';
                                } else {
                                    response.messages.forEach(function(msg) {
                                        var align = msg.outbound ? 'right' : 'left';
                                        var bg = msg.outbound ? '#e1f5fe' : '#ffffff';
                                        html += '<div style="margin-bottom:8px; text-align:' + align + ';">' +
                                                '<div style="display:inline-block; max-width:80%; padding:8px 12px; border-radius:15px; background:' + bg + '; box-shadow:0 1px 2px rgba(0,0,0,0.1); text-align:left; font-size:13px; line-height:1.4;">' + 
                                                msg.text.replace(/</g, "&lt;") + '</div></div>';
                                    });
                                }
                                $('#oisha-native-messages').html(html);
                                $('#oisha-native-messages').scrollTop($('#oisha-native-messages')[0].scrollHeight);
                                
                                $('#oisha-native-input').prop('disabled', false);
                                $('#oisha-native-send').prop('disabled', false);
                            } else {
                                $('#oisha-native-messages').html('<div style="text-align:center; color:red; font-size:12px; margin-top:20px;">' + response.error + '</div>');
                            }
                        },
                        error: function() {
                            $('#oisha-native-messages').html('<div style="text-align:center; color:red; font-size:12px; margin-top:20px;">Server xatosi.</div>');
                        }
                    });
                }

                $('#oisha-native-send').on('click', function() {
                    sendMessage();
                });
                
                $('#oisha-native-input').on('keypress', function(e) {
                    if(e.which == 13) sendMessage();
                });

                function sendMessage() {
                    var text = $('#oisha-native-input').val().trim();
                    if (!text || !currentChatId) return;

                    $('#oisha-native-input').val('');
                    
                    var html = '<div style="margin-bottom:8px; text-align:right;">' +
                                '<div style="display:inline-block; max-width:80%; padding:8px 12px; border-radius:15px; background:#e1f5fe; box-shadow:0 1px 2px rgba(0,0,0,0.1); text-align:left; font-size:13px; line-height:1.4;">' + 
                                text.replace(/</g, "&lt;") + ' <span style="font-size:10px; color:#888;">(yuborilmoqda...)</span></div></div>';
                    $('#oisha-native-messages').append(html);
                    $('#oisha-native-messages').scrollTop($('#oisha-native-messages')[0].scrollHeight);

                    $.ajax({
                        url: API_BASE + '/send',
                        type: 'POST',
                        contentType: 'application/json',
                        data: JSON.stringify({
                            chat_id: currentChatId,
                            text: text
                        }),
                        success: function(response) {
                            if (response.success) {
                                // Yuborilgandan so'ng qayta yuklash
                                setTimeout(function() { loadHistory(currentPhone); }, 1000);
                            } else {
                                alert("Xatolik: " + response.error);
                            }
                        }
                    });
                }

                return true;
            },
            settings: function () {
                return true;
            },
            onSave: function () {
                return true;
            },
            destroy: function () {
            }
        };
        return this;
    };
    return CustomWidget;
});
