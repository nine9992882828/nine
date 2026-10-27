import time
import requests
from config import TON_API, TON_API_KEY, WALLET_ADDRESS, PRICE_NANO


def make_ton_link(user_id: int) -> str:
    memo = f"{user_id} access"
    return (
        f"https://app.tonkeeper.com/transfer/{WALLET_ADDRESS}"
        f"?amount={PRICE_NANO}&text={requests.utils.quote(memo)}"
    )


def check_payment(user_id: int) -> dict:
    memo = str(user_id)
    headers = {}
    if TON_API_KEY:
        headers["X-API-Key"] = TON_API_KEY

    try:
        r = requests.get(
            f"{TON_API}/transactions",
            params={"account": WALLET_ADDRESS, "limit": 50},
            headers=headers, timeout=20,
        )
        data = r.json()
    except Exception as e:
        return {"ok": False, "error": f"API error: {e}"}

    if not data or "transactions" not in data:
        return {"ok": False, "error": "Пустой ответ API"}

    now = int(time.time())
    for tx in data["transactions"]:
        try:
            in_msg = tx.get("in_msg") or {}
            value = int(in_msg.get("value", 0))
            comment = in_msg.get("message", "") or ""
            utime = int(tx.get("now", 0) or tx.get("utime", 0))
            if now - utime > 1200:
                continue
            if value < PRICE_NANO:
                continue
            if memo not in comment:
                continue
            return {"ok": True, "tx_hash": tx.get("hash"),
                    "amount": value, "comment": comment}
        except Exception:
            continue

    return {"ok": False, "error": "Платёж не найден. Подождите пару минут и проверьте ещё раз."}