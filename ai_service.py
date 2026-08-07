"""Сервис AI-аналитики для платного доступа (гейт к Проекту 2).

Проект 4 по ТЗ — это платёжный шлюз: он открывает доступ к функциям Проекта 2.
Если папка project2_ai_review_analyst лежит рядом, импортируем её модули и
получаем реальный (или демо-) результат анализа. Иначе возвращаем заглушку.

ПОЧЕМУ НЕ ОБЩИЙ ПАКЕТ shared/: по ТЗ это ЧЕТЫРЕ НЕЗАВИСИМЫХ проекта, каждый
запускается сам по себе из своей папки (python bot.py) со своими библиотеками.
Общий пакет shared/ вынудил бы устанавливать проект как пакет (pip install -e)
или запускать из корня — это сломало бы автономность проектов и их историю
"своя папка = свой бот". Единственная точка кросс-импорта — этот метод, поэтому
мы изолируем загрузку модулей Проекта 2 (sys.path + очистка sys.modules) и
ВОССТАНАВЛИВАЕМ состояние интерпретатора после вызова, чтобы не сломать
последующие импорты в процессе бота Проекта 4.
"""
from __future__ import annotations

import html as _html
import logging
import sys
from pathlib import Path

logger = logging.getLogger(__name__)

PROJECT2_DIR = Path(__file__).resolve().parents[1] / "project2_ai_review_analyst"

# Имена модулей, совпадающие у Проекта 2 и Проекта 4 (config.py и т.п.).
# Python кэширует модули в sys.modules по имени — без очистки Проект 2 мог бы
# подхватить config.py Проекта 4.
_CONFLICTING_MODULES = ("config", "models", "reviews", "llm")


def _load_project2() -> tuple:
    """Загружает модули Проекта 2 и восстанавливает состояние интерпретатора.

    После загрузки возвращаем в sys.modules модули Проекта 4 (config и др.),
    чтобы последующие импорты в процессе бота не подхватывали чужой конфиг.
    """
    sys.path.insert(0, str(PROJECT2_DIR))
    saved = {name: sys.modules.pop(name, None) for name in _CONFLICTING_MODULES}
    try:
        from llm import get_provider  # noqa: PLC0415
        from reviews import mock_reviews  # noqa: PLC0415

        return get_provider, mock_reviews
    finally:
        sys.path.remove(str(PROJECT2_DIR))
        for name, module in saved.items():
            if module is not None and name not in sys.modules:
                sys.modules[name] = module


async def run_analysis(articul: int | None = None) -> str:
    """Запускает анализ отзывов. Возвращает текст для отправки в чат."""
    try:
        get_provider, mock_reviews = _load_project2()
        result = await get_provider().analyze(mock_reviews(20))

        def esc(value: str) -> str:
            return _html.escape(value, quote=False)

        return (
            "🤖 <b>Результат AI-анализа (Проект 2)</b>\n\n"
            "👍 <b>Преимущества:</b>\n"
            + "\n".join(f"• {esc(p)}" for p in result.pros)
            + "\n\n👎 <b>Проблемы:</b>\n"
            + "\n".join(f"• {esc(c)}" for c in result.cons)
            + f"\n\nТональность: <b>{esc(result.sentiment)}</b>"
        )
    except Exception as exc:  # модуль Проекта 2 недоступен / не установлен pydantic
        logger.warning("Не удалось подключить модуль Проекта 2: %s", exc, exc_info=True)
        return (
            "🤖 Доступ к AI-аналитике открыт (подписка активна).\n\n"
            "<i>Не удалось подключить модуль Проекта 2 (проверьте, что папка "
            "project2_ai_review_analyst лежит рядом и установлены его зависимости). "
            "Запустите bot.py из этой папки для реального анализа.</i>"
        )
