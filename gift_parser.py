import asyncio
import logging
from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.tl import functions
from config import TG_API_ID, TG_API_HASH, TG_SESSION_STRING

log = logging.getLogger(__name__)
_client: TelegramClient | None = None


async def get_client() -> TelegramClient:
    global _client
    if _client is None or not _client.is_connected():
        _client = TelegramClient(
            StringSession(TG_SESSION_STRING), TG_API_ID, TG_API_HASH
        )
        await _client.connect()
        if not await _client.is_user_authorized():
            raise RuntimeError(
                "Сессия не авторизована. Создай новую через session_bot.py"
            )
    return _client


async def fetch_user_nfts(username: str) -> list[dict]:
    client = await get_client()
    try:
        entity = await client.get_entity(username)
    except Exception as e:
        log.warning("entity %s: %s", username, e)
        return []

    nfts = []
    offset = ""
    while True:
        try:
            result = await client(functions.payments.GetSavedStarGiftsRequest(
                peer=entity,
                offset=offset,
                limit=100,
                exclude_unsaved=False,
                exclude_unique=False,
            ))
        except Exception:
            log.exception("getSavedStarGifts %s", username)
            break

        for gift in result.gifts:
            inner = gift.gift
            if not getattr(inner, "num", None):
                continue
            title = getattr(inner, "title", "Gift")
            slug = getattr(inner, "slug", None)
            nfts.append({
                "name": title,
                "num": str(inner.num),
                "display": f"{title} #{inner.num:,}",
                "url": (
                    f"https://t.me/nft/{slug}"
                    if slug
                    else f"https://t.me/nft/{title.replace(' ', '')}-{inner.num}"
                ),
            })

        if not getattr(result, "next_offset", None):
            break
        offset = result.next_offset
        await asyncio.sleep(0.3)

    return nfts


def sync_fetch_nfts(username: str) -> list[dict]:
    return asyncio.run(fetch_user_nfts(username))