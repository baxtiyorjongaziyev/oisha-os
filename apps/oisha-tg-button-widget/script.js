/*
 * Oisha: Telegramda yozish — amoCRM vidjeti.
 * Kartochkadagi har bir telefon va Telegram username maydoni yonida "Telegram"
 * tugmasini qoʻshadi. Bosilganda chat Telegram Desktop (tg://) yoki Web da ochiladi.
 * Server kerak emas, yozishmalar amoCRMʼga yuklanmaydi (buni Oisha Telegram Bridge qiladi).
 */
(function (root, factory) {
  if (typeof define === 'function' && define.amd) {
    define(['jquery'], factory);
  } else if (typeof module === 'object' && module.exports) {
    module.exports = factory(null);
  }
})(this, function ($) {
  var BTN_CLASS = 'oisha-tg-btn';

  // --- Pure helpers (node testlari uchun ham eksport qilinadi) ---
  function normalizePhone(raw, countryCode) {
    var cc = String(countryCode || '998').replace(/\D/g, '') || '998';
    var d = String(raw || '').replace(/\D/g, '');
    if (!d) return null;
    if (d.indexOf('00') === 0) d = d.slice(2);
    if (d.length === 9) d = cc + d; // 90 123 45 67
    else if (d.length === 10 && d.charAt(0) === '8' && cc === '998') d = cc + d.slice(1);
    if (d.length < 10 || d.length > 15) return null;
    return d;
  }

  function normalizeUsername(raw) {
    var s = String(raw || '').trim();
    s = s.replace(/^https?:\/\/(www\.)?(t|telegram)\.me\//i, '').replace(/^@/, '');
    s = s.split(/[/?#\s]/)[0];
    return /^[A-Za-z][A-Za-z0-9_]{3,31}$/.test(s) ? s : null;
  }

  function buildLink(kind, value, mode) {
    var web = String(mode || '').toLowerCase() === 'web';
    if (kind === 'phone') {
      return web ? 'https://t.me/+' + value : 'tg://resolve?phone=' + value;
    }
    return web ? 'https://t.me/' + value : 'tg://resolve?domain=' + value;
  }

  var Widget = function () {
    var self = this;
    var observer = null;

    function settings() {
      var s = (self.get_settings && self.get_settings()) || {};
      return {
        cc: s.country_code || '998',
        mode: s.open_mode || 'desktop',
        usernameField: String(s.username_field || 'telegram').toLowerCase()
      };
    }

    function makeButton(kind, value) {
      var cfg = settings();
      var href = buildLink(kind, value, cfg.mode);
      return $('<a/>', {
        'class': BTN_CLASS,
        href: href,
        target: cfg.mode === 'web' ? '_blank' : '_self',
        rel: 'noopener',
        title: 'Telegramda yozish',
        text: 'Telegram'
      }).css({
        display: 'inline-block', marginLeft: '6px', padding: '1px 8px',
        borderRadius: '10px', background: '#229ED9', color: '#fff',
        fontSize: '11px', lineHeight: '18px', textDecoration: 'none',
        verticalAlign: 'middle', whiteSpace: 'nowrap', cursor: 'pointer'
      }).on('click', function (e) { e.stopPropagation(); });
    }

    function attach($input, kind, value) {
      var $wrap = $input.closest('.control-phone, .linked-form__field__value, .card-cf__field');
      if (!$wrap.length) $wrap = $input.parent();
      var $old = $wrap.find('.' + BTN_CLASS);
      if ($old.length && $old.data('v') === value) return;
      $old.remove();
      if (!value) return;
      var $btn = makeButton(kind, value).data('v', value);
      $wrap.append($btn);
    }

    function fieldLabel($input) {
      var $f = $input.closest('.linked-form__field, .card-cf__field, .cf-field-wrapper');
      return String($f.find('.linked-form__field__label, .card-cf__label, label').first().text() || '').toLowerCase();
    }

    function scan() {
      var cfg = settings();
      $('.control-phone input[type="text"], .control-phone input[type="tel"], input.control-phone__formatted, input[type="tel"]').each(function () {
        var $i = $(this);
        if (!$i.is(':visible')) return;
        attach($i, 'phone', normalizePhone($i.val(), cfg.cc));
      });
      $('.linked-form__field input[type="text"], .card-cf__field input[type="text"]').each(function () {
        var $i = $(this);
        if ($i.closest('.control-phone').length) return;
        var label = fieldLabel($i);
        if (label.indexOf(cfg.usernameField) === -1 && label.indexOf('telegram') === -1) return;
        attach($i, 'username', normalizeUsername($i.val()));
      });
    }

    var pending = null;
    function scheduleScan() {
      if (pending) return;
      pending = setTimeout(function () { pending = null; try { scan(); } catch (e) {} }, 300);
    }

    this.callbacks = {
      render: function () { return true; },
      init: function () { return true; },
      bind_actions: function () {
        scheduleScan();
        $(document).off('.oishaTg')
          .on('change.oishaTg blur.oishaTg', '.control-phone input, .linked-form__field input', scheduleScan);
        if (window.MutationObserver && !observer) {
          var target = document.querySelector('.card-holder, #card_holder, #page_holder') || document.body;
          observer = new MutationObserver(scheduleScan);
          observer.observe(target, { childList: true, subtree: true });
        }
        return true;
      },
      settings: function () { return true; },
      onSave: function () { return true; },
      destroy: function () {
        if (observer) { observer.disconnect(); observer = null; }
        $(document).off('.oishaTg');
        $('.' + BTN_CLASS).remove();
      }
    };
    return this;
  };

  Widget.normalizePhone = normalizePhone;
  Widget.normalizeUsername = normalizeUsername;
  Widget.buildLink = buildLink;
  return Widget;
});
