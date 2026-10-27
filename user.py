from config import ADMIN_ID, WALLET_ADDRESS, PRICE_GRAM, PRICE_NANO, START_BANNER
from database import (
    is_authorized, save_pending_payment, get_pending_payment,
    clear_pending_payment, set_authorized,
)
from keyboards import start_kb, buy_kb, back_kb
from texts import t, detect_lang
from ton import make_ton_link, check_payment
from business_helpers import send, edit, answer_callback, api


def cmd_start(msg, business_id=None):
    chat_id = msg["chat"]["id"]
    user = msg.get("from", {})
    user_id = user["id"]
    lang = detect_lang(user.get("language_code"))

    has = is_authorized(user_id)
    text = t(lang, "start_has_access") if has else t(lang, "start_no_access")
    kb = start_kb(has)

    if START_BANNER and not business_id:
        payload = {
            "chat_id": chat_id,
            "photo": START_BANNER,
            "caption": text,
            "parse_mode": "HTML",
        }
        if kb:
            payload["reply_markup"] = kb
        api("sendPhoto", payload)
    else:
        send(chat_id, text, kb, business_id=business_id)


def cb_buy(callback):
    chat_id = callback["message"]["chat"]["id"]
    user_id = callback["from"]["id"]
    lang = detect_lang(callback["from"].get("language_code"))
    if is_authorized(user_id):
        answer_callback(callback["id"], "✅ У вас уже есть доступ", alert=True)
        edit(chat_id, callback["message"]["message_id"],
             t(lang, "start_has_access"), start_kb(True))
        return
    memo = f"{user_id} access"
    save_pending_payment(user_id, PRICE_NANO, memo)
    text = t(lang, "buy").format(wallet=WALLET_ADDRESS, price=PRICE_GRAM, memo=memo)
    edit(chat_id, callback["message"]["message_id"], text,
         buy_kb(PRICE_GRAM, make_ton_link(user_id)))
    answer_callback(callback["id"])


def cb_already_bought(callback):
    chat_id = callback["message"]["chat"]["id"]
    lang = detect_lang(callback["from"].get("language_code"))
    user_id = callback["from"]["id"]
    edit(chat_id, callback["message"]["message_id"],
         t(lang, "already_bought"), back_kb())
    answer_callback(callback["id"])
    send(ADMIN_ID,
         f"📩 Пользователь <code>{user_id}</code> нажал «Уже покупал».")


def cb_check_payment(callback):
    user_id = callback["from"]["id"]
    lang = detect_lang(callback["from"].get("language_code"))
    chat_id = callback["message"]["chat"]["id"]
    if is_authorized(user_id):
        answer_callback(callback["id"], "✅ Доступ уже открыт", alert=True); return
    pending = get_pending_payment(user_id)
    if not pending:
        answer_callback(callback["id"], "Сначала нажмите «Купить».", alert=True); return
    answer_callback(callback["id"], "🔄 Проверяю блокчейн...")
    result = check_payment(user_id)
    if result.get("ok"):
        set_authorized(user_id, True)
        clear_pending_payment(user_id)
        edit(chat_id, callback["message"]["message_id"],
             t(lang, "payment_ok"), start_kb(True))
        send(ADMIN_ID,
             f"💰 Новая оплата!\n• User: <code>{user_id}</code>\n"
             f"• TX: <code>{result['tx_hash']}</code>")
    else:
        err = result.get("error", "Оплата не найдена")
        answer_callback(callback["id"],
                        t(lang, "payment_no").format(error=err), alert=True)


def cb_back(callback):
    chat_id = callback["message"]["chat"]["id"]
    user_id = callback["from"]["id"]
    lang = detect_lang(callback["from"].get("language_code"))
    has = is_authorized(user_id)
    text = t(lang, "start_has_access") if has else t(lang, "start_no_access")
    edit(chat_id, callback["message"]["message_id"], text, start_kb(has))
    answer_callback(callback["id"])


def cmd_my_nfts(msg, business_id=None):
    from gift_parser import sync_fetch_nfts
    user = msg["from"]
    username = user.get("username")
    chat_id = msg["chat"]["id"]
    if not username:
        send(chat_id, "Нет @username.", business_id=business_id); return
    nfts = sync_fetch_nfts(username)
    if not nfts:
        send(chat_id, "NFT не найдены.", business_id=business_id); return
    lines = ["📦 <b>Ваши NFT:</b>\n"]
    for i, n in enumerate(nfts, 1):
        lines.append(f"{i}. <a href='{n['url']}'>{n['display']}</a>")
    send(chat_id, "\n".join(lines), business_id=business_id)