"""SQLite-БД статусов подписки пользователей (aiosqlite, по ТЗ)."""
from __future__ import annotations

from datetime import date, timedelta

import aiosqlite


class Database:
    def __init__(self, path: str) -> None:
        self.path = path

    async def init(self) -> None:
        async with aiosqlite.connect(self.path) as db:
            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS users (
                    user_id          INTEGER PRIMARY KEY,
                    username         TEXT,
                    subscribed_until TEXT,
                    created_at       TEXT
                )
                """
            )
            await db.commit()

    async def is_subscribed(self, user_id: int) -> bool:
        until = await self.until(user_id)
        if not until:
            return False
        try:
            return date.fromisoformat(until) >= date.today()
        except ValueError:
            return False

    async def activate(self, user_id: int, username: str | None, days: int) -> None:
        """После successful_payment продлевает/активирует подписку на N дней."""
        until = (date.today() + timedelta(days=days)).isoformat()
        async with aiosqlite.connect(self.path) as db:
            await db.execute(
                """
                INSERT INTO users (user_id, username, subscribed_until, created_at)
                VALUES (?, ?, ?, date('now'))
                ON CONFLICT(user_id) DO UPDATE SET
                    username = excluded.username,
                    subscribed_until = excluded.subscribed_until
                """,
                (user_id, username or "", until),
            )
            await db.commit()

    async def deactivate(self, user_id: int) -> None:
        async with aiosqlite.connect(self.path) as db:
            await db.execute(
                "UPDATE users SET subscribed_until = NULL WHERE user_id = ?",
                (user_id,),
            )
            await db.commit()

    async def until(self, user_id: int) -> str | None:
        async with aiosqlite.connect(self.path) as db:
            async with db.execute(
                "SELECT subscribed_until FROM users WHERE user_id = ?", (user_id,)
            ) as cur:
                row = await cur.fetchone()
        return row[0] if row else None
