import logging
import time
import requests
from config import TOKEN

API = f"https://api.telegram.org/bot{TOKEN}"
SESSION = requests.Session()
last_send_at = 0.0
SEND_MIN_INTERVAL = 1.1


def api(method, payload=None, *, respect_interval=False):
    global last_send_at
    payload = payload or {}
    if respect_interval:
        wait = SEND_MIN_INTERVAL - (time.monotonic() - last_send_at)
        if wait > 0:
            time.sleep(wait)
        last_send_at = time.monotonic()
    try:
        r = SESSION.post(f"{API}/{method}", json=payload, timeout=25)
        data = r.json()
        if not data.get("ok"):
            desc = data.get("description", "")
            if "PEER_FLOOD" not in desc:
                logging.warning("%s failed: %s", method, desc)
        return data
    except (requests.RequestException, ValueError) as e:
        logging.warning("%s request failed: %s", method, e)
        return {"ok": False, "description": str(e)}


def send(chat_id, text, keyboard=None, business_id=None, preview_url=None):
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
        "link_preview_options": (
            {"is_disabled": False, "url": preview_url, "show_above_text": True}
            if preview_url else {"is_disabled": True}
        ),
    }
    if keyboard:
        payload["reply_markup"] = keyboard
    if business_id:
        payload["business_connection_id"] = business_id
    return api("sendMessage", payload, respect_interval=True)


def edit(chat_id, message_id, text, keyboard=None, business_id=None, preview_url=None):
    payload = {
        "chat_id": chat_id, "message_id": message_id,
        "text": text, "parse_mode": "HTML",
        "link_preview_options": (
            {"is_disabled": False, "url": preview_url, "show_above_text": True}
            if preview_url else {"is_disabled": True}
        ),
    }
    if keyboard is not None:
        payload["reply_markup"] = keyboard
    if business_id:
        payload["business_connection_id"] = business_id
    return api("editMessageText", payload, respect_interval=True)


def delete_message(chat_id, message_id, business_id=None):
    if business_id:
        return api("deleteBusinessMessages", {
            "business_connection_id": business_id,
            "message_ids": [message_id],
        })
    return api("deleteMessage", {"chat_id": chat_id, "message_id": message_id})


def answer_callback(callback_id, text=None, alert=False):
    payload = {"callback_query_id": callback_id}
    if text:
        payload.update(text=text, show_alert=alert)
    try:
        SESSION.post(f"{API}/answerCallbackQuery", json=payload, timeout=10)
    except Exception:
        pass