from config import ADMIN_ID
from database import set_authorized, is_authorized, all_authorized, find_user_by_username
from keyboards import admin_kb, cancel_kb
from business_helpers import send, edit, answer_callback, api


admin_state = {}


def admin_panel(msg):
    if msg["from"]["id"] != ADMIN_ID:
        return
    send(msg["chat"]["id"], "🛠 <b>Админ-панель</b>", admin_kb())


def cb_admin_grant(callback):
    if callback["from"]["id"] != ADMIN_ID:
        answer_callback(callback["id"], "Нет прав", alert=True); return
    admin_state[ADMIN_ID] = {"action": "grant"}
    edit(callback["message"]["chat"]["id"], callback["message"]["message_id"],
         "Введите ID или @username, кому выдать доступ:", cancel_kb())
    answer_callback(callback["id"])


def cb_admin_revoke(callback):
    if callback["from"]["id"] != ADMIN_ID:
        answer_callback(callback["id"], "Нет прав", alert=True); return
    admin_state[ADMIN_ID] = {"action": "revoke"}
    edit(callback["message"]["chat"]["id"], callback["message"]["message_id"],
         "Введите ID или @username, у кого забрать доступ:", cancel_kb())
    answer_callback(callback["id"])


def cb_admin_broadcast(callback):
    if callback["from"]["id"] != ADMIN_ID:
        answer_callback(callback["id"], "Нет прав", alert=True); return
    admin_state[ADMIN_ID] = {"action": "broadcast"}
    edit(callback["message"]["chat"]["id"], callback["message"]["message_id"],
         "Отправьте текст рассылки (можно с HTML):", cancel_kb())
    answer_callback(callback["id"])


def cb_admin_cancel(callback):
    admin_state.pop(ADMIN_ID, None)
    edit(callback["message"]["chat"]["id"], callback["message"]["message_id"],
         "🛠 <b>Админ-панель</b>", admin_kb())
    answer_callback(callback["id"], "Отменено")


def _resolve_user(text: str):
    text = text.strip()
    if text.startswith("@"):
        return find_user_by_username(text)
    try:
        return int(text)
    except ValueError:
        return None


def handle_admin_input(msg) -> bool:
    if msg["from"]["id"] != ADMIN_ID:
        return False
    state = admin_state.get(ADMIN_ID)
    if not state:
        return False

    chat_id = msg["chat"]["id"]
    text = (msg.get("text") or "").strip()
    action = state["action"]

    try:
        api("deleteMessage", {"chat_id": chat_id, "message_id": msg["message_id"]})
    except Exception:
        pass

    if action == "grant":
        uid = _resolve_user(text)
        if not uid:
            send(chat_id, "❌ Не нашёл. Введите числовой ID.", cancel_kb())
            return True
        set_authorized(uid, True)
        admin_state.pop(ADMIN_ID, None)
        send(chat_id, f"✅ Доступ выдан <code>{uid}</code>.", admin_kb())
        try:
            send(uid, "✅ Вам выдан доступ.")
        except Exception:
            pass
        return True

    if action == "revoke":
        uid = _resolve_user(text)
        if not uid:
            send(chat_id, "❌ Не нашёл. Введите числовой ID.", cancel_kb())
            return True
        set_authorized(uid, False)
        admin_state.pop(ADMIN_ID, None)
        send(chat_id, f"🚫 Доступ забран у <code>{uid}</code>.", admin_kb())
        try:
            send(uid, "🚫 Ваш доступ отозван.")
        except Exception:
            pass
        return True

    if action == "broadcast":
        admin_state.pop(ADMIN_ID, None)
        ok, fail = 0, 0
        import time
        for uid in all_authorized():
            if uid == ADMIN_ID:
                continue
            r = send(uid, text)
            if r.get("ok"):
                ok += 1
            else:
                fail += 1
            time.sleep(0.05)
        send(chat_id, f"📢 Рассылка завершена.\n✅ Доставлено: {ok}\n❌ Ошибок: {fail}",
             admin_kb())
        return True

    return False