import logging
import re
from typing import Any
from src.services.core.finance.hisobchi_engine import HisobchiEngine, _fmt_money
from src.time_utils import get_local_now

logger = logging.getLogger(__name__)

async def handle_hisobchi_command(
    event, client, engine: HisobchiEngine, analyst: Any
) -> bool:
    try:
        text = (event.message.message or "").strip()

        cmd_match = re.match(r"^/hisobchi\s+(.+)$", text, re.IGNORECASE)
        if not cmd_match:
            return False
        cmd = cmd_match.group(1).strip().lower()

        now = get_local_now()
        period = now.strftime("%Y-%m")

        if cmd.startswith("tahlil") or cmd == "analiz":
            if not analyst:
                await event.reply("⚠️ HisobchiAnalyst yoqilmagan.")
                return True
            await event.reply("⏳ Hisobchi tahlil tayyorlayapti...")
            report = await analyst.analyze_month(period)
            await event.reply(report, parse_mode="html")
            return True

        if cmd.startswith("prognoz") or cmd.startswith("forecast"):
            if not analyst:
                await event.reply("⚠️ HisobchiAnalyst yoqilmagan.")
                return True
            await event.reply("⏳ Prognoz tayyorlanmoqda...")
            result = await analyst.forecast()
            await event.reply(result, parse_mode="html")
            return True

        if cmd.startswith("qarz"):
            debts = await engine.get_debts(active_only=True)
            if not debts:
                await event.reply("✅ Faol qarzlar yo'q.")
                return True
            lines = ["<b>📋 Faol qarzlar:</b>\n"]
            for d in debts:
                icon = "🔴" if d["debt_type"] == "Berilgan" else "🟡"
                due = f", muddat: {d['due_date']}" if d.get("due_date") else ""
                lines.append(
                    f"{icon} {d['person']}: {_fmt_money(d['remaining'])} UZS "
                    f"({d['debt_type']}){due}"
                )
            await event.reply("\n".join(lines), parse_mode="html")
            return True

        if cmd.startswith("byudjet"):
            budgets = await engine.get_budget_status(period)
            if not budgets:
                await event.reply(f"📭 {period} uchun byudjet belgilanmagan.")
                return True
            lines = [f"<b>📊 Byudjet — {period}</b>\n"]
            for b in budgets:
                icon = {"yaxshi": "✅", "ogohlantirish": "⚠️", "yomon": "🚫"}.get(b["status"], "➖")
                lines.append(
                    f"{icon} <b>{b['category']}</b>: {_fmt_money(b['spent'])} / "
                    f"{_fmt_money(b['budget_limit'])} UZS (qoldiq: {_fmt_money(b['remaining'])})"
                )
            await event.reply("\n".join(lines), parse_mode="html")
            return True

        await event.reply(
            "Hisobchi buyruqlari:\n"
            "/hisobchi tahlil — AI tahlil\n"
            "/hisobchi prognoz — Kelajak prognozi\n"
            "/hisobchi qarz — Qarzlar ro'yxati\n"
            "/hisobchi byudjet — Byudjet holati"
        )
        return True
    except Exception as exc:
        logger.error("Error occurred: %s", exc, exc_info=True)
        try:
            await event.reply(f"❌ Xatolik yuz berdi: {str(exc)}")
        except Exception:
            pass
        return True

async def handle_qarz_command(event, engine: HisobchiEngine) -> bool:
    try:
        text = (event.message.message or "").strip()
        m = re.match(r"^/qarz\s+(ber|ol|to[\'\"]?la)\s+(.+?)\s+(\d[\d\s]*)\s*(.*)", text, re.IGNORECASE)
        if not m:
            return False
        action = m.group(1).lower()
        person = m.group(2).strip()
        amount_str = re.sub(r"\s+", "", m.group(3))
        note = m.group(4).strip()

        if not amount_str.isdigit():
            await event.reply("⚠️ Summani to'g'ri kiriting (raqam).")
            return True
        amount = int(amount_str)

        if action in ("ber",):
            debt_type = "Berilgan"
            confirm = f"✅ <b>Qarz berildi</b>\n{person}: {_fmt_money(amount)} UZS"
            if note:
                confirm += f"\n📝 {note}"
            await engine.add_debt(debt_type, person, amount, note=note)
            await event.reply(confirm, parse_mode="html")
            return True

        if action == "ol":
            debt_type = "Olingan"
            confirm = f"✅ <b>Qarz olindi</b>\n{person} dan: {_fmt_money(amount)} UZS"
            if note:
                confirm += f"\n📝 {note}"
            await engine.add_debt(debt_type, person, amount, note=note)
            await event.reply(confirm, parse_mode="html")
            return True

        if action in ("to'la", "tola"):
            debts = await engine.get_debts(active_only=True)
            found = [d for d in debts if person.lower() in d["person"].lower()]
            if not found:
                await event.reply(f"❌ {person} uchun faol qarz topilmadi.")
                return True
            result = await engine.repay_debt(found[0]["id"], amount)
            if result:
                await event.reply(
                    f"✅ <b>Qarz to'landi</b>\n{person}: "
                    f"qoldiq {_fmt_money(result['remaining'])} UZS",
                    parse_mode="html",
                )
            return True
        return True
    except Exception as exc:
        logger.error("Error occurred: %s", exc, exc_info=True)
        try:
            await event.reply(f"❌ Xatolik yuz berdi: {str(exc)}")
        except Exception:
            pass
        return True

async def handle_byudjet_command(event, engine: HisobchiEngine) -> bool:
    try:
        text = (event.message.message or "").strip()
        m = re.match(r"^/byudjet\s+set\s+(.+?)\s+(\d[\d\s]*)", text, re.IGNORECASE)
        if not m:
            return False
        category = m.group(1).strip()
        limit_str = re.sub(r"\s+", "", m.group(2))
        if not limit_str.isdigit():
            await event.reply("⚠️ Limitni raqamda kiriting.")
            return True
        limit = int(limit_str)
        now = get_local_now()
        period = now.strftime("%Y-%m")
        await engine.set_budget(category, period, limit)
        await event.reply(
            f"✅ <b>Byudjet belgilandi</b>\n📂 {category}: <b>{_fmt_money(limit)} UZS</b> ({period})",
            parse_mode="html",
        )
        return True
    except Exception as exc:
        logger.error("Error occurred: %s", exc, exc_info=True)
        try:
            await event.reply(f"❌ Xatolik yuz berdi: {str(exc)}")
        except Exception:
            pass
        return True

async def handle_valyuta_command(event, engine: HisobchiEngine) -> bool:
    try:
        text = (event.message.message or "").strip()
        if not text.lower().startswith("/valyuta"):
            return False

        from src.services.core.hisobchi_rates import fetch_bank_uz_rates

        await event.reply("⏳ Kurslar yangilanmoqda...")
        rates = await fetch_bank_uz_rates()
        if rates and "USD" in rates:
            r = rates["USD"]
            await engine.update_rate("USD", r["buy"], r["sell"], r["cb"])
            await event.reply(
                f"💱 <b>USD/UZS kursi yangilandi</b>\n"
                f"💰 Sotib olish: <b>{r['buy']:,.0f}</b>\n"
                f"💸 Sotish: <b>{r['sell']:,.0f}</b>\n"
                f"🏦 MB kursi: <b>{r['cb']:,.0f}</b>\n"
                f"📅 {r.get('date', '')}",
                parse_mode="html",
            )
        else:
            saved = await engine.get_rates()
            usd = saved.get("USD", {})
            if usd:
                await event.reply(
                    f"💱 <b>USD/UZS (kesh)</b>\n"
                    f"Sotib olish: {usd.get('buy', 0):,.0f}\n"
                    f"Sotish: {usd.get('sell', 0):,.0f}",
                    parse_mode="html",
                )
            else:
                await event.reply("⚠️ Kurslarni yuklab bo'lmadi.")
        return True
    except Exception as exc:
        logger.error("Error occurred: %s", exc, exc_info=True)
        try:
            await event.reply(f"❌ Xatolik yuz berdi: {str(exc)}")
        except Exception:
            pass
        return True

async def handle_kassa_command(event, engine: HisobchiEngine) -> bool:
    try:
        text = (event.message.message or "").strip()
        m = re.match(r"^/kassa\s+(ko\'?rsat|show|list)$", text, re.IGNORECASE)
        if m:
            wallets = await engine.get_kassa()
            if not wallets:
                await event.reply("📭 Kassa hisoblari yo'q.")
                return True
            lines = ["<b>💰 Kassa hisoblari:</b>\n"]
            for w in wallets:
                icon = {"Naqd": "💵", "Karta": "💳", "Jamg'arma": "🏦", "Valyuta": "💱"}.get(w["type"], "💰")
                lines.append(f"{icon} <b>{w['name']}</b>: {_fmt_money(w['balance'])} {w['currency']} ({w['type']})")
            await event.reply("\n".join(lines), parse_mode="html")
            return True

        m = re.match(r"^/kassa\s+add\s+(.+?)\s+(\d[\d\s]*)\s*(.*)", text, re.IGNORECASE)
        if m:
            name = m.group(1).strip()
            amt = int(re.sub(r"\s+", "", m.group(2)))
            rest = m.group(3).strip()
            wallet_type = "Naqd"
            currency = "UZS"
            note = rest
            if rest:
                parts = rest.split()
                if parts[0].upper() in ("USD", "UZS", "EUR", "RUB"):
                    currency = parts[0].upper()
                    note = " ".join(parts[1:])
            await engine.add_kassa(name, currency, amt, wallet_type, note)
            await event.reply(
                f"✅ <b>Kassa ochildi</b>\n{name}: {_fmt_money(amt)} {currency}",
                parse_mode="html",
            )
            return True
        return False
    except Exception as exc:
        logger.error("Error occurred: %s", exc, exc_info=True)
        try:
            await event.reply(f"❌ Xatolik yuz berdi: {str(exc)}")
        except Exception:
            pass
        return True

async def handle_otkazma_command(event, engine: HisobchiEngine) -> bool:
    try:
        text = (event.message.message or "").strip()
        m = re.match(r"^/otkazma\s+(.+?)\s*[-–>]\s*(.+?)\s+(\d[\d\s]*)\s*(.*)", text, re.IGNORECASE)
        if not m:
            return False
        from_name = m.group(1).strip().lower()
        to_name = m.group(2).strip().lower()
        amt = int(re.sub(r"\s+", "", m.group(3)))
        note = m.group(4).strip()

        wallets = await engine.get_kassa()
        from_w = next((w for w in wallets if from_name in w["name"].lower()), None)
        to_w = next((w for w in wallets if to_name in w["name"].lower()), None)

        if not from_w:
            await event.reply(f"❌ '{m.group(1)}' topilmadi.")
            return True
        if not to_w:
            await event.reply(f"❌ '{m.group(2)}' topilmadi.")
            return True

        result = await engine.transfer_balance(from_w["id"], to_w["id"], amt, note)
        if not result:
            await event.reply("⚠️ O'tkazma amalga oshmadi (valyuta kursi topilmadi?).")
            return True

        rate_line = f" (kurs: {result['rate']:,.0f})" if result.get("rate", 1) != 1 else ""
        await event.reply(
            f"✅ <b>O'tkazma amalga oshirildi</b>\n"
            f"📤 {result['from']}: {_fmt_money(result['amount'])} UZS\n"
            f"📥 {result['to']}: {_fmt_money(result['converted'])} UZS{rate_line}\n"
            f"{'📝 ' + result.get('note', '') if result.get('note') else ''}",
            parse_mode="html",
        )
        return True
    except Exception as exc:
        logger.error("Error occurred: %s", exc, exc_info=True)
        try:
            await event.reply(f"❌ Xatolik yuz berdi: {str(exc)}")
        except Exception:
            pass
        return True

async def handle_xodim_command(event, engine: HisobchiEngine) -> bool:
    try:
        text = (event.message.message or "").strip()
        m = re.match(r"^/xodim\s+(add|qo\'?sh|list|ko\'?rsat)\s*(.*)", text, re.IGNORECASE)
        if not m:
            return False
        action = m.group(1).lower()
        rest = m.group(2).strip()

        if action in ("list", "ko'rsat", "korsat"):
            xodimlar = await engine.get_xodimlar()
            if not xodimlar:
                await event.reply("📭 Xodimlar yo'q.")
                return True
            lines = ["<b>👥 Xodimlar:</b>\n"]
            for x in xodimlar:
                perm_icon = {"to'liq": "🔵", "yozish": "🟢", "kuzatish": "⚪"}.get(x["permission"], "⚪")
                lines.append(f"{perm_icon} <b>{x['name']}</b> — {x['role']} ({x['permission']})")
            await event.reply("\n".join(lines), parse_mode="html")
            return True

        if action in ("add", "qo'sh", "qosh"):
            parts = rest.split("|")
            name = parts[0].strip() if parts else ""
            role = parts[1].strip() if len(parts) > 1 else "Xodim"
            perm = parts[2].strip() if len(parts) > 2 else "kuzatish"
            if not name:
                await event.reply("⚠️ Ismni kiriting: /xodim add Ism | Rol | ruxsat")
                return True
            await engine.add_xodim(name, role, permission=perm)
            await event.reply(
                f"✅ <b>Xodim qo'shildi</b>\n👤 {name} — {role} ({perm})",
                parse_mode="html",
            )
            return True
        return False
    except Exception as exc:
        logger.error("Error occurred: %s", exc, exc_info=True)
        try:
            await event.reply(f"❌ Xatolik yuz berdi: {str(exc)}")
        except Exception:
            pass
        return True
