"""Платёжный шлюз для AI-подписки (aiogram v3, Telegram Bot Payments API).

Стек (строго по ТЗ): aiogram (PreCheckoutQuery, SuccessfulPayment) + SQLite
(aiosqlite — статус пользователя после оплаты).

Два режима оплаты:
  1) Telegram Stars — STAR_PAYMENTS=1 (provider_token="", валюта XTR);
  2) тестовый режим ЮKassa — STAR_PAYMENTS=0 + YOOKASSA_PROVIDER_TOKEN
     (тестовый токен выдаёт @BotFather → меню Payments).

Запуск:  python bot.py  (задайте WB_BOT_TOKEN).
"""
from __future__ import annotations

import asyncio
import html as _html
import logging
import os

from aiogram import Bot, Dispatcher, F, Router
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command, CommandStart
from aiogram.types import LabeledPrice, Message, PreCheckoutQuery

import config
from ai_service import run_analysis
from db import Database

# Логирование в консоль и в файл bot.log рядом с ботом
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    handlers=[
        logging.FileHandler(os.path.join(config.BASE_DIR, "bot.log"), encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)

router = Router()
db = Database(config.DB_PATH)

PAYLOAD = "ai_subscription"


def _invoice() -> dict:
    """Параметры счёта: Telegram Stars или ЮKassa (тест)."""
    if config.STAR_PAYMENTS:
        return {
            "title": "Подписка на AI-аналитику",
            "description": "Доступ к AI-анализу отзывов Wildberries на 30 дней.",
            "payload": PAYLOAD,
            "provider_token": "",  # пустой токен = Telegram Stars
            "currency": "XTR",     # Stars; amount = число звёзд
            "prices": [LabeledPrice(label="⭐ Подписка (30 дней)", amount=config.PRICE_STARS)],
        }
    return {
        "title": "Подписка на AI-аналитику",
        "description": "Доступ к AI-анализу отзывов Wildberries на 30 дней.",
        "payload": PAYLOAD,
        "provider_token": config.YOOKASSA_PROVIDER_TOKEN,  # тестовый токен ЮKassa
        "currency": "RUB",
        # Сумма в минимальных единицах валюты (копейках)
        "prices": [LabeledPrice(label="Подписка (30 дней)", amount=config.PRICE_RUB * 100)],
    }


@router.message(CommandStart())
async def cmd_start(message: Message) -> None:
    await message.answer(
        "Добро пожаловать в <b>AI-аналитику Wildberries</b>!\n\n"
        "/subscribe — оплатить подписку\n"
        "/status — статус подписки\n"
        "/unsubscribe — отключить подписку\n"
        "/analyze — AI-анализ (доступен после оплаты)\n\n"
        f"Способ оплаты: <b>{'Telegram Stars' if config.STAR_PAYMENTS else 'ЮKassa (тест)'}</b>"
    )


@router.message(Command("subscribe"))
async def cmd_subscribe(message: Message) -> None:
    if await db.is_subscribed(message.from_user.id):
        await message.answer("У вас уже есть активная подписка. Статус: /status")
        return
    try:
        await message.bot.send_invoice(
            chat_id=message.chat.id,
            **_invoice(),
        )
    except Exception as exc:
        # Например, у бота не включены Payments в @BotFather или неверный токен ЮKassa
        logger.exception("Не удалось выставить счёт")
        await message.answer(
            "⚠️ Не удалось создать платёжный инвойс. Убедитесь, что у бота в "
            "@BotFather включён раздел Payments (и задан тестовый токен ЮKassa, "
            "если STAR_PAYMENTS=0).\n\nПодробности: "
            f"<code>{_html.escape(str(exc))}</code>"
        )


@router.pre_checkout_query()
async def on_pre_checkout(query: PreCheckoutQuery) -> None:
    """Обязательный обработчик: подтверждает платёж (по ТЗ)."""
    await query.answer(ok=True, error_message="Платёж отклонён")


@router.message(F.successful_payment)
async def on_successful_payment(message: Message) -> None:
    """После успешной оплаты обновляем статус пользователя в SQLite (по ТЗ)."""
    payment = message.successful_payment
    await db.activate(message.from_user.id, message.from_user.username, config.SUBSCRIPTION_DAYS)
    amount = _format_amount(payment.currency, payment.total_amount)
    await message.answer(
        f"✅ Оплата получена: <b>{amount}</b>\n"
        f"Подписка активирована на <b>{config.SUBSCRIPTION_DAYS} дней</b>.\n"
        "Теперь доступна команда /analyze"
    )


@router.message(Command("status"))
async def cmd_status(message: Message) -> None:
    until = await db.until(message.from_user.id)
    if until and await db.is_subscribed(message.from_user.id):
        await message.answer(f"✅ Подписка активна до <b>{until}</b>")
    else:
        await message.answer("❌ Подписка не активна. /subscribe")


@router.message(Command("unsubscribe"))
async def cmd_unsubscribe(message: Message) -> None:
    await db.deactivate(message.from_user.id)
    await message.answer("Подписка отключена. /subscribe — вернуть доступ.")


@router.message(Command("analyze"))
async def cmd_analyze(message: Message) -> None:
    """Гейт: AI-функция доступна только после оплаты подписки."""
    if not await db.is_subscribed(message.from_user.id):
        await message.answer(
            "🔒 Для доступа к AI-аналитике оплатите подписку: /subscribe"
        )
        return
    status = await message.answer("🧠 Запускаю AI-анализ…")
    text = await run_analysis()
    await status.edit_text(text)


def _format_amount(currency: str, amount: int) -> str:
    """Stars приходят целыми, остальные валюты — в минимальных единицах."""
    if currency == "XTR":
        return f"{amount} ⭐"
    return f"{amount / 100:.2f} {currency}"


async def main() -> None:
    if not config.BOT_TOKEN:
        raise SystemExit("Не задан WB_BOT_TOKEN. Скопируйте .env.example и задайте токен.")
    bot = Bot(token=config.BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher()
    dp.include_router(router)
    await db.init()
    logger.info("Платёжный шлюз запущен. Способ оплаты: %s",
                "Telegram Stars" if config.STAR_PAYMENTS else "ЮKassa (тест)")
    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
