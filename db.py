"""SQLite-БД статусов подписки пользователей (aiosqlite, по ТЗ).

Продвинутый уровень:
  - таблица payments — журнал платежей (тариф, сумма, charge_id, возврат);
  - used_trial — бесплатный пробный период выдаётся один раз;
  - refund_payment() — отметка возврата по charge_id (для /refund).
"""
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
                    created_at       TEXT,
                    used_trial       INTEGER NOT NULL DEFAULT 0
                )
                """
            )
            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS payments (
                    id                         INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id                    INTEGER,
                    username                   TEXT,
                    amount                     INTEGER,
                    currency                   TEXT,
                    tier                       TEXT,
                    telegram_payment_charge_id TEXT,
                    created_at                 TEXT,
                    refunded                   INTEGER NOT NULL DEFAULT 0
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
        """Продлевает/активирует подписку на N дней от сегодня."""
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

    # --- пробный период ---

    async def has_used_trial(self, user_id: int) -> bool:
        async with aiosqlite.connect(self.path) as db:
            async with db.execute(
                "SELECT used_trial FROM users WHERE user_id = ?", (user_id,)
            ) as cur:
                row = await cur.fetchone()
        return bool(row and row[0])

    async def mark_trial_used(self, user_id: int) -> None:
        async with aiosqlite.connect(self.path) as db:
            await db.execute(
                """
                INSERT INTO users (user_id, used_trial) VALUES (?, 1)
                ON CONFLICT(user_id) DO UPDATE SET used_trial = 1
                """,
                (user_id,),
            )
            await db.commit()

    # --- журнал платежей ---

    async def add_payment(
        self,
        user_id: int,
        username: str | None,
        amount: int,
        currency: str,
        tier: str,
        charge_id: str,
    ) -> None:
        async with aiosqlite.connect(self.path) as db:
            await db.execute(
                """
                INSERT INTO payments
                    (user_id, username, amount, currency, tier,
                     telegram_payment_charge_id, created_at)
                VALUES (?, ?, ?, ?, ?, ?, datetime('now'))
                """,
                (user_id, username or "", amount, currency, tier, charge_id),
            )
            await db.commit()

    async def payment_history(self, user_id: int, limit: int = 10) -> list[dict]:
        async with aiosqlite.connect(self.path) as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute(
                """
                SELECT * FROM payments WHERE user_id = ?
                ORDER BY id DESC LIMIT ?
                """,
                (user_id, limit),
            )
            rows = await cur.fetchall()
        return [dict(row) for row in rows]

    async def last_charge_id(self, user_id: int) -> str | None:
        """charge_id последнего не-возвращённого платежа (для /refund)."""
        async with aiosqlite.connect(self.path) as db:
            async with db.execute(
                """
                SELECT telegram_payment_charge_id FROM payments
                WHERE user_id = ? AND refunded = 0
                ORDER BY id DESC LIMIT 1
                """,
                (user_id,),
            ) as cur:
                row = await cur.fetchone()
        return row[0] if row else None

    async def refund_payment(self, user_id: int, charge_id: str) -> bool:
        """Отмечает платёж возвращённым; True — если такой платёж найден."""
        async with aiosqlite.connect(self.path) as db:
            cur = await db.execute(
                "UPDATE payments SET refunded = 1 "
                "WHERE user_id = ? AND telegram_payment_charge_id = ? AND refunded = 0",
                (user_id, charge_id),
            )
            await db.commit()
            return cur.rowcount > 0
