def start_kb(has_access: bool):
    if has_access:
        return None
    return {"inline_keyboard": [
        [{"text": "🛒 Купить доступ", "callback_data": "buy"}],
        [{"text": "🤔 Уже покупал", "callback_data": "already_bought"}],
    ]}


def buy_kb(price_gram: int, ton_link: str):
    return {"inline_keyboard": [
        [{"text": f"💎 Оплатить {price_gram} GRAM", "url": ton_link}],
        [{"text": "🔍 Проверить оплату", "callback_data": "check_payment"}],
        [{"text": "⬅️ Назад", "callback_data": "back_to_start"}],
    ]}


def back_kb():
    return {"inline_keyboard": [[
        {"text": "⬅️ Назад", "callback_data": "back_to_start"}
    ]]}


def admin_kb():
    return {"inline_keyboard": [
        [{"text": "👤 Выдать доступ", "callback_data": "admin_grant"}],
        [{"text": "🚫 Забрать доступ", "callback_data": "admin_revoke"}],
        [{"text": "📢 Рассылка", "callback_data": "admin_broadcast"}],
    ]}


def cancel_kb():
    return {"inline_keyboard": [[
        {"text": "❌ Отмена", "callback_data": "admin_cancel"}
    ]]}