"""Тесты P4: жизненный цикл подписки, тарифы, payload, триал, платежи.

Запуск: python -m pytest tests -q
"""
import asyncio

import config
from ai_service import run_analysis
from db import Database


def _make_db(tmp_path) -> Database:
    return Database(str(tmp_path / "sub.db"))


def test_subscription_lifecycle(tmp_path) -> None:
    """Активация после оплаты -> статус -> отключение."""
    async def run() -> None:
        db = _make_db(tmp_path)
        await db.init()
        assert not await db.is_subscribed(555)
        await db.activate(555, "tester", 30)
        assert await db.is_subscribed(555)
        assert await db.until(555)
        await db.deactivate(555)
        assert not await db.is_subscribed(555)

    asyncio.run(run())


def test_trial_once(tmp_path) -> None:
    """Пробный период выдаётся один раз."""
    async def run() -> None:
        db = _make_db(tmp_path)
        await db.init()
        assert not await db.has_used_trial(777)
        await db.mark_trial_used(777)
        assert await db.has_used_trial(777)

    asyncio.run(run())


def test_payments_and_refund(tmp_path) -> None:
    """Журнал платежей: добавление, поиск charge_id, возврат."""
    async def run() -> None:
        db = _make_db(tmp_path)
        await db.init()
        await db.add_payment(1, "alice", 50, "XTR", "starter", "charge-1")
        await db.add_payment(1, "alice", 120, "XTR", "pro", "charge-2")
        hist = await db.payment_history(1)
        assert len(hist) == 2 and hist[0]["tier"] == "pro"
        assert await db.last_charge_id(1) == "charge-2"
        assert await db.refund_payment(1, "charge-2")
        assert await db.last_charge_id(1) == "charge-1"  # возвращённый не берём
        assert not await db.refund_payment(1, "charge-2")  # повторный возврат — False

    asyncio.run(run())


def test_tiers_and_payload_validation() -> None:
    """Серверная валидация payload: принимает только известные тарифы."""
    assert config.parse_payload("sub:starter") is not None
    assert config.parse_payload("sub:pro")["stars"] == 120
    assert config.parse_payload("sub:hacked_tier") is None  # подмена payload отклонена
    assert config.parse_payload("other:starter") is None
    assert config.parse_payload("") is None
    assert config.tier_by_key("unknown") is None
    # длительности тарифов согласованы с ключами
    from bot import _days_for
    assert _days_for(config.tier_by_key("starter")) == 30
    assert _days_for(config.tier_by_key("pro")) == 90
    assert _days_for(config.tier_by_key("business")) == 180


def test_ai_service_gate_to_project2() -> None:
    """Интеграция с Проектом 2: полный результат, если модуль рядом.

    В изолированном CI (репозиторий без папки project2_ai_review_analyst)
    run_analysis честно возвращает заглушку — бот не падает, и это тоже
    проверяется.
    """
    text = asyncio.run(run_analysis())
    if "Результат AI-анализа" in text:  # полная интеграция (Проект 2 рядом)
        assert "Преимущества" in text
        assert "Проблемы" in text
    else:  # изолированная сборка: работает честная заглушка
        assert "Доступ к AI-аналитике открыт" in text


def test_status_helpers() -> None:
    """Остаток дней подписки и человекочитаемые названия тарифов."""
    from datetime import date, timedelta

    from bot import _days_left, _tier_label

    assert _days_left((date.today() + timedelta(days=1)).isoformat()) == 1
    assert _days_left(date.today().isoformat()) == 0
    assert _days_left("не дата") == 0
    assert _tier_label("pro") == "Про (90 дней)"
    assert _tier_label("неизвестный") == "неизвестный"
