import json
import logging
import time
import requests

from config import TOKEN, ADMIN_ID
from database import init_db, touch_user
from business_helpers import API, SESSION
from user import cmd_start, cb_buy, cb_already_bought, cb_check_payment, cb_back, cmd_my_nfts
from admin import (
    admin_panel, cb_admin_grant, cb_admin_revoke, cb_admin_broadcast,
    cb_admin_cancel, handle_admin_input,
)
from offers import handle_offer_message, handle_offer_callback

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")


def handle_callback(callback):
    data = callback.get("data", "")
    if data == "buy":
        cb_buy(callback)
    elif data == "already_bought":
        cb_already_bought(callback)
    elif data == "check_payment":
        cb_check_payment(callback)
    elif data == "back_to_start":
        cb_back(callback)
    elif data == "noop":
        pass
    elif data == "admin_grant":
        cb_admin_grant(callback)
    elif data == "admin_revoke":
        cb_admin_revoke(callback)
    elif data == "admin_broadcast":
        cb_admin_broadcast(callback)
    elif data == "admin_cancel":
        cb_admin_cancel(callback)
    else:
        handle_offer_callback(callback)


def handle_message(msg, business_id=None):
    user_id = msg.get("from", {}).get("id")
    if user_id:
        touch_user(int(user_id))

    text = (msg.get("text") or "").strip()
    cmd = text.split()[0].split("@")[0].lower() if text else ""

    if handle_admin_input(msg):
        return
    if text.startswith("/start"):
        cmd_start(msg, business_id=business_id); return
    if cmd == "/admin" and user_id == ADMIN_ID:
        admin_panel(msg); return
    if cmd == "/my_nfts":
        cmd_my_nfts(msg, business_id=business_id); return

    # ловим сообщение вида "t.me/nft/... 45000"
    if handle_offer_message(msg, business_id=business_id):
        return


def main():
    init_db()
    me = requests.get(f"{API}/getMe").json()
    if not me.get("ok"):
        raise RuntimeError("Неверный токен бота")
    logging.info("Bot @%s запущен", me["result"]["username"])

    offset = 0
    while True:
        try:
            r = SESSION.get(f"{API}/getUpdates", params={
                "offset": offset, "timeout": 30,
                "allowed_updates": json.dumps([
                    "message", "callback_query",
                    "business_message", "business_connection",
                ]),
            }, timeout=35)
            data = r.json()
            for upd in data.get("result", []):
                offset = upd["update_id"] + 1
                try:
                    if "message" in upd:
                        handle_message(upd["message"])
                    elif "business_message" in upd:
                        m = upd["business_message"]
                        biz = m.get("business_connection_id")
                        logging.info("BIZ MSG: chat=%s biz=%s text=%s",
                                     m["chat"]["id"], biz, (m.get("text") or "")[:60])
                        handle_message(m, business_id=biz)
                    elif "business_connection" in upd:
                        bc = upd["business_connection"]
                        logging.info("BIZ CONN: id=%s enabled=%s can_reply=%s",
                                     bc.get("id"),
                                     bc.get("is_enabled"),
                                     (bc.get("rights") or {}).get("can_reply"))
                    elif "callback_query" in upd:
                        handle_callback(upd["callback_query"])
                except Exception:
                    logging.exception("Update %s error", upd.get("update_id"))
        except KeyboardInterrupt:
            break
        except Exception:
            logging.exception("Polling error")
            time.sleep(3)


if __name__ == "__main__":
    main()