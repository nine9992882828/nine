import sqlite3
import time
from config import DB_PATH, ADMIN_ID


def db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with db() as conn:
        conn.execute("""CREATE TABLE IF NOT EXISTS authorized (
            user_id INTEGER PRIMARY KEY,
            granted_at INTEGER NOT NULL)""")
        conn.execute("""CREATE TABLE IF NOT EXISTS pending_payments (
            user_id INTEGER PRIMARY KEY,
            amount_nano INTEGER NOT NULL,
            memo TEXT NOT NULL,
            created_at INTEGER NOT NULL)""")
        conn.execute("""CREATE TABLE IF NOT EXISTS offers (
            offer_key TEXT PRIMARY KEY, nft_name TEXT NOT NULL,
            nft_num TEXT NOT NULL, nft_url TEXT NOT NULL,
            amount INTEGER NOT NULL, currency TEXT NOT NULL,
            lang TEXT NOT NULL, chat_id INTEGER NOT NULL,
            message_id INTEGER NOT NULL, business_id TEXT,
            expires_at INTEGER NOT NULL, sender_id INTEGER NOT NULL,
            sender_name TEXT NOT NULL, sender_username TEXT,
            status TEXT NOT NULL DEFAULT 'pending',
            created_at INTEGER NOT NULL)""")
        conn.execute("""CREATE TABLE IF NOT EXISTS last_seen (
            user_id INTEGER PRIMARY KEY,
            seen_at INTEGER NOT NULL)""")
        conn.execute("INSERT OR IGNORE INTO authorized(user_id, granted_at) VALUES (?, ?)",
                     (ADMIN_ID, int(time.time())))
        # миграция для существующих БД
        try:
            conn.execute("ALTER TABLE offers ADD COLUMN sender_username TEXT")
        except sqlite3.OperationalError:
            pass


def touch_user(user_id: int):
    with db() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO last_seen(user_id, seen_at) VALUES (?, ?)",
            (user_id, int(time.time())))


def has_interacted(user_id: int, within_hours: int = 48) -> bool:
    with db() as conn:
        row = conn.execute(
            "SELECT seen_at FROM last_seen WHERE user_id = ?", (user_id,)
        ).fetchone()
        if not row:
            return False
        return int(time.time()) - row["seen_at"] < within_hours * 3600


def is_authorized(user_id: int) -> bool:
    with db() as conn:
        return conn.execute(
            "SELECT 1 FROM authorized WHERE user_id = ?", (user_id,)
        ).fetchone() is not None


def set_authorized(user_id: int, allowed: bool):
    with db() as conn:
        if allowed:
            conn.execute(
                "INSERT OR IGNORE INTO authorized(user_id, granted_at) VALUES (?, ?)",
                (user_id, int(time.time())))
        else:
            conn.execute("DELETE FROM authorized WHERE user_id = ?", (user_id,))


def all_authorized():
    with db() as conn:
        return [r["user_id"] for r in conn.execute("SELECT user_id FROM authorized")]


def save_pending_payment(user_id: int, amount_nano: int, memo: str):
    with db() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO pending_payments(user_id, amount_nano, memo, created_at) "
            "VALUES (?, ?, ?, ?)",
            (user_id, amount_nano, memo, int(time.time())))


def get_pending_payment(user_id: int):
    with db() as conn:
        return conn.execute(
            "SELECT * FROM pending_payments WHERE user_id = ?", (user_id,)).fetchone()


def clear_pending_payment(user_id: int):
    with db() as conn:
        conn.execute("DELETE FROM pending_payments WHERE user_id = ?", (user_id,))


def find_user_by_username(username: str):
    uname = username.lstrip("@").lower()
    with db() as conn:
        row = conn.execute(
            "SELECT user_id FROM last_seen WHERE user_id IN "
            "(SELECT sender_id FROM offers WHERE LOWER(sender_name)=?) LIMIT 1",
            (uname,)).fetchone()
        return row["user_id"] if row else None