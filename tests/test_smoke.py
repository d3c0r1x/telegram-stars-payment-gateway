"""Smoke-тесты: жизненный цикл подписки и интеграция с Проектом 2."""
import asyncio
import os
import tempfile

from ai_service import run_analysis
from db import Database


def test_subscription_lifecycle() -> None:
    """Активация после оплаты -> статус -> отключение."""
    async def run() -> None:
        db = Database(os.path.join(tempfile.gettempdir(), "pytest_sub.db"))
        if os.path.exists(db.path):
            os.remove(db.path)
        await db.init()
        assert not await db.is_subscribed(555)
        await db.activate(555, "tester", 30)
        assert await db.is_subscribed(555)
        assert await db.until(555)
        await db.deactivate(555)
        assert not await db.is_subscribed(555)

    asyncio.run(run())


def test_ai_service_gate_to_project2() -> None:
    """run_analysis загружает модули Проекта 2 и возвращает результат."""
    text = asyncio.run(run_analysis())
    assert "Результат AI-анализа" in text
    assert "Преимущества" in text
    assert "Проблемы" in text
