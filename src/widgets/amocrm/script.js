define(['jquery', 'underscore', 'twigjs'], function ($, _, Twig) {
  return function () {
    var self = this;

    this.callbacks = {
      render: function () {
        console.log('Oisha-OS: Rendering Widget...');
        return true;
      },
      init: function () {
        console.log('Oisha-OS: Initializing Logic...');
        return true;
      },
      bind_actions: function () {
        console.log('Oisha-OS: Binding Actions...');
        
        // Triggered when opening a lead card
        self.on('card:load', function () {
          self.loadOishaChat();
        });

        return true;
      },
      settings: function () {
        return true;
      },
      onSave: function () {
        return true;
      },
      destroy: function () {
        console.log('Oisha-OS: Cleanup...');
      }
    };

    /**
     * Oisha Chat Interface Initialization
     */
    this.loadOishaChat = function () {
      var cardData = AMOCRM.data.current_card;
      var contactData = cardData.contacts.db[0]; 
      
      // Attempt to find Telegram ID from custom fields
      var tgId = null;
      if (contactData && contactData.custom_fields) {
        Object.keys(contactData.custom_fields).forEach(function(key) {
          var field = contactData.custom_fields[key];
          if (field.name === 'Telegram ID' || field.id == 123456) { // User can adjust ID
            tgId = field.values[0].value;
          }
        });
      }

      // Fallback to internal ID if no TG ID field found (not recommended for sync)
      var targetId = tgId || (contactData ? contactData.id : null);
      
      if (!targetId) return;

      var vpsUrl = self.get_settings().oisha_vps_url;
      var secret = self.get_settings().oisha_secret;

      // Premium Telegram-style template
      var html = `
        <div class="oisha-widget-container">
          <div class="oisha-header">
            <img src="https://telegram.org/img/t_logo.png" width="24" height="24">
            <div class="oisha-title">Oisha Intelligence Chat</div>
          </div>
          <div class="oisha-chat-box" id="oisha-chat-history">
            <div style="text-align:center; padding:20px; color:#707579;">Suhbat yuklanmoqda...</div>
          </div>
          <div class="oisha-input-group">
            <input type="text" class="oisha-input" id="oisha-msg-input" placeholder="Xabar yozing...">
            <button class="oisha-send-btn" id="oisha-send-trigger">YUBORISH</button>
          </div>
        </div>
      `;

      // Append to the AmoCRM right sidebar or a specific tab
      $('.card-widgets__container').prepend(html);

      // Fetch History
      self.fetchHistory(vpsUrl, userId, secret);

      // Bind Send Event
      $('#oisha-send-trigger').on('click', function() {
        var text = $('#oisha-msg-input').val();
        if (text) self.sendMessage(vpsUrl, userId, text, secret);
      });

      // Enter key support
      $('#oisha-msg-input').on('keypress', function(e) {
        if (e.which == 13) $('#oisha-send-trigger').click();
      });
    };

    this.fetchHistory = function (url, userId, secret) {
      $.get(url + '/api/chat/history/' + userId + '?secret_key=' + secret, function(data) {
        if (data.history) {
          var chatHtml = '';
          data.history.forEach(function(msg) {
            var roleClass = msg.role === 'model' ? 'me' : 'user';
            chatHtml += '<div class="oisha-message ' + roleClass + '">' + msg.parts[0].text + '</div>';
          });
          $('#oisha-chat-history').html(chatHtml);
          // Scroll to bottom
          var objDiv = document.getElementById("oisha-chat-history");
          objDiv.scrollTop = objDiv.scrollHeight;
        }
      });
    };

    this.sendMessage = function (url, userId, text, secret) {
      $('#oisha-send-trigger').prop('disabled', true).text('...');
      
      $.ajax({
        url: url + '/api/chat/send',
        method: 'POST',
        contentType: 'application/json',
        data: JSON.stringify({
          user_id: parseInt(userId),
          text: text,
          secret_key: secret
        }),
        success: function(response) {
          $('#oisha-msg-input').val('');
          $('#oisha-send-trigger').prop('disabled', false).text('YUBORISH');
          // Update local UI
          $('#oisha-chat-history').append('<div class="oisha-message me">' + text + '</div>');
          var objDiv = document.getElementById("oisha-chat-history");
          objDiv.scrollTop = objDiv.scrollHeight;
        },
        error: function() {
          alert('Xabar yuborishda xatolik yuz berdi. VPS ulanishini tekshiring.');
          $('#oisha-send-trigger').prop('disabled', false).text('YUBORISH');
        }
      });
    };

    return this;
  };
});
