import asyncio
from telethon import TelegramClient
from config import TG_API_ID, TG_API_HASH, TG_SESSION_NAME


async def main():
    c = TelegramClient(TG_SESSION_NAME, TG_API_ID, TG_API_HASH)
    await c.start()
    me = await c.get_me()
    print(f"OK: {me.first_name} @{me.username} id={me.id}")
    await c.disconnect()


if __name__ == "__main__":
    asyncio.run(main())