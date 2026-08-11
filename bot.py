"""Платёжный шлюз для AI-подписки (aiogram v3, Telegram Bot Payments API).

Стек (строго по ТЗ): aiogram (PreCheckoutQuery, SuccessfulPayment) + SQLite
(aiosqlite — статус пользователя после оплаты).

Два режима оплаты:
  1) Telegram Stars — STAR_PAYMENTS=1 (provider_token="", валюта XTR);
  2) тестовый режим ЮKassa — STAR_PAYMENTS=0 + YOOKASSA_PROVIDER_TOKEN
     (тестовый токен выдаёт @BotFather → меню Payments).

Продвинутый уровень:
  - три тарифа (Старт/Про/Бизнес) через инлайн-кнопки;
  - серверная валидация payload счёта (config.parse_payload);
  - журнал платежей (/payments) и возврат последнего платежа (/refund —
    refund_star_payment + отзыв доступа);
  - бесплатный пробный период (/trial, один раз на пользователя);
  - middlewares: троттлинг и логирование.

Запуск:  python bot.py  (задайте WB_BOT_TOKEN).
"""
from __future__ import annotations

import asyncio
import html as _html
import logging
import os
from datetime import date

from aiogram import Bot, Dispatcher, F, Router
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command, CommandStart
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardMarkup,
    LabeledPrice,
    Message,
    PreCheckoutQuery,
)
from aiogram.utils.keyboard import InlineKeyboardBuilder

import config
from ai_service import run_analysis
from db import Database
from middlewares import LoggingMiddleware, ThrottlingMiddleware

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


def _tiers_keyboard() -> InlineKeyboardMarkup:
    """Инлайн-кнопки выбора тарифа: callback tier:<key>."""
    kb = InlineKeyboardBuilder()
    for tier in config.TIERS:
        price = f"{tier['stars']} ⭐" if config.STAR_PAYMENTS else f"{tier['rub']} ₽"
        kb.button(text=f"{tier['label']} — {price}", callback_data=f"tier:{tier['key']}")
    kb.adjust(1)
    return kb.as_markup()


def _invoice(tier: dict) -> dict:
    """Параметры счёта: Telegram Stars или ЮKassa (тест)."""
    if config.STAR_PAYMENTS:
        return {
            "title": f"Подписка «{tier['label']}»",
            "description": "Доступ к AI-анализу отзывов Wildberries.",
            "payload": f"sub:{tier['key']}",
            "provider_token": "",  # пустой токен = Telegram Stars
            "currency": "XTR",     # Stars; amount = число звёзд
            "prices": [LabeledPrice(label=f"⭐ {tier['label']}", amount=tier["stars"])],
        }
    return {
        "title": f"Подписка «{tier['label']}»",
        "description": "Доступ к AI-анализу отзывов Wildberries.",
        "payload": f"sub:{tier['key']}",
        "provider_token": config.YOOKASSA_PROVIDER_TOKEN,  # тестовый токен ЮKassa
        "currency": "RUB",
        # Сумма в минимальных единицах валюты (копейках)
        "prices": [LabeledPrice(label=f"{tier['label']}", amount=tier["rub"] * 100)],
    }


@router.message(CommandStart())
async def cmd_start(message: Message) -> None:
    await message.answer(
        "Добро пожаловать в <b>AI-аналитику Wildberries</b>!\n\n"
        "/subscribe — выбрать тариф и оплатить\n"
        "/trial — бесплатный пробный период (один раз)\n"
        "/status — статус подписки\n"
        "/payments — история платежей\n"
        "/refund — возврат последнего платежа\n"
        "/unsubscribe — отключить подписку\n"
        "/analyze — AI-анализ (доступен после оплаты)\n\n"
        f"Способ оплаты: <b>{'Telegram Stars' if config.STAR_PAYMENTS else 'ЮKassa (тест)'}</b>"
    )


@router.message(Command("subscribe"))
async def cmd_subscribe(message: Message) -> None:
    if await db.is_subscribed(message.from_user.id):
        await message.answer("У вас уже есть активная подписка. Статус: /status")
        return
    await message.answer("Выберите тариф:", reply_markup=_tiers_keyboard())


@router.callback_query(F.data.startswith("tier:"))
async def on_tier_selected(callback: CallbackQuery) -> None:
    """Пользователь выбрал тариф — выставляем счёт."""
    tier = config.tier_by_key(callback.data.split(":", 1)[1])
    if tier is None:
        await callback.answer("Неизвестный тариф.", show_alert=True)
        return
    try:
        await callback.message.bot.send_invoice(
            chat_id=callback.message.chat.id,
            **_invoice(tier),
        )
    except Exception as exc:
        logger.exception("Не удалось выставить счёт")
        await callback.answer(
            "⚠️ Не удалось создать платёжный инвойс. Убедитесь, что у бота в "
            "@BotFather включён раздел Payments (и задан тестовый токен ЮKassa, "
            "если STAR_PAYMENTS=0).",
            show_alert=True,
        )
        return
    await callback.answer("Счёт выставлен ✅")


@router.pre_checkout_query()
async def on_pre_checkout(query: PreCheckoutQuery) -> None:
    """Обязательный обработчик (по ТЗ). Плюс серверная валидация payload."""
    if config.parse_payload(query.invoice_payload) is None:
        await query.answer(ok=False, error_message="Неизвестный тариф подписки")
        return
    await query.answer(ok=True, error_message="Платёж отклонён")


@router.message(F.successful_payment)
async def on_successful_payment(message: Message) -> None:
    """После успешной оплаты обновляем статус в SQLite (по ТЗ) и пишем в журнал."""
    payment = message.successful_payment
    tier = config.parse_payload(payment.invoice_payload)
    if tier is None:  # не должно случиться (валидируется в pre_checkout), но на всякий
        await message.answer("⚠️ Ошибка: неизвестный тариф платежа.")
        return
    # Идемпотентность: Telegram доставляет апдейты at-least-once — повторная
    # доставка того же successful_payment не должна продлевать подписку дважды.
    inserted = await db.add_payment(
        message.from_user.id,
        message.from_user.username,
        payment.total_amount,
        payment.currency,
        tier["key"],
        payment.telegram_payment_charge_id,
    )
    if not inserted:
        await message.answer("ℹ️ Этот платёж уже был обработан ранее.")
        return
    await db.activate(
        message.from_user.id, message.from_user.username, _days_for(tier)
    )
    amount = _format_amount(payment.currency, payment.total_amount)
    await message.answer(
        f"✅ Оплата получена: <b>{amount}</b>\n"
        f"Тариф: <b>{_html.escape(tier['label'])}</b>\n"
        f"Доступ открыт. Теперь доступна команда /analyze"
    )


def _days_for(tier: dict) -> int:
    """Длительность тарифа в днях (по ключу, из конфига)."""
    mapping = {"starter": 30, "pro": 90, "business": 180}
    return mapping.get(tier["key"], config.SUBSCRIPTION_DAYS)


def _days_left(until: str) -> int:
    """Сколько дней осталось до конца подписки (по ISO-дате из БД)."""
    try:
        return (date.fromisoformat(until) - date.today()).days
    except ValueError:
        return 0


def _tier_label(key: str) -> str:
    """Человекочитаемое название тарифа по ключу (или сам ключ)."""
    tier = config.tier_by_key(key)
    return tier["label"] if tier else key


@router.message(Command("trial"))
async def cmd_trial(message: Message) -> None:
    """Бесплатный пробный период — один раз на пользователя."""
    if await db.has_used_trial(message.from_user.id):
        await message.answer("Вы уже использовали пробный период. /subscribe")
        return
    if await db.is_subscribed(message.from_user.id):
        await message.answer("У вас уже есть активная подписка. /status")
        return
    await db.activate(message.from_user.id, message.from_user.username, config.TRIAL_DAYS)
    await db.mark_trial_used(message.from_user.id)
    await message.answer(
        f"🎁 Пробный доступ активирован на <b>{config.TRIAL_DAYS} дней</b>!\n"
        "Попробуйте: /analyze"
    )


@router.message(Command("refund"))
async def cmd_refund(message: Message) -> None:
    """Возврат последнего платежа (Telegram Stars) + отзыв доступа."""
    if not config.STAR_PAYMENTS:
        await message.answer(
            "Возврат доступен только для Telegram Stars. В тестовом режиме "
            "ЮKassa возврат оформляется в кабинете ЮKassa."
        )
        return
    charge_id = await db.last_charge_id(message.from_user.id)
    if charge_id is None:
        await message.answer("Возвращать нечего: нет не-возвращённых платежей.")
        return
    try:
        # Встроенный метод aiogram: возврат звёзд по charge_id (только XTR)
        await message.bot.refund_star_payment(
            user_id=message.from_user.id,
            telegram_payment_charge_id=charge_id,
        )
    except Exception as exc:
        logger.exception("Ошибка возврата")
        await message.answer(
            f"⚠️ Не удалось оформить возврат: {_html.escape(str(exc))}\n"
            "(Возврат работает для Telegram Stars.)"
        )
        return
    await db.refund_payment(message.from_user.id, charge_id)
    await db.deactivate(message.from_user.id)
    await message.answer(
        "💸 Платёж возвращён, подписка отключена. Спасибо за честность!"
    )


@router.message(Command("payments"))
async def cmd_payments(message: Message) -> None:
    rows = await db.payment_history(message.from_user.id)
    if not rows:
        await message.answer("Платежей пока нет. /subscribe")
        return
    lines = []
    for r in rows:
        status = "↩️ возвращён" if r["refunded"] else "✅ оплачен"
        lines.append(
            f"• {r['created_at']} — {_format_amount(r['currency'], r['amount'])} "
            f"(тариф: {_tier_label(r['tier'])}) — {status}"
        )
    await message.answer("🧾 <b>История платежей</b>\n\n" + "\n".join(lines[:10]))


@router.message(Command("status"))
async def cmd_status(message: Message) -> None:
    until = await db.until(message.from_user.id)
    if until and await db.is_subscribed(message.from_user.id):
        left = _days_left(until)
        suffix = f" (осталось {left} дн.)" if left >= 0 else ""
        await message.answer(f"✅ Подписка активна до <b>{until}</b>{suffix}")
    else:
        await message.answer("❌ Подписка не активна. /subscribe или /trial")


@router.message(Command("unsubscribe"))
async def cmd_unsubscribe(message: Message) -> None:
    await db.deactivate(message.from_user.id)
    await message.answer("Подписка отключена. /subscribe — вернуть доступ.")


@router.message(Command("analyze"))
async def cmd_analyze(message: Message) -> None:
    """Гейт: AI-функция доступна только после оплаты подписки."""
    if not await db.is_subscribed(message.from_user.id):
        await message.answer(
            "🔒 Для доступа к AI-аналитике оплатите подписку: /subscribe "
            "(или попробуйте бесплатно: /trial)"
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
    dp.message.middleware(ThrottlingMiddleware(min_interval=config.THROTTLE_MIN_INTERVAL))
    dp.update.middleware(LoggingMiddleware())
    await db.init()
    logger.info(
        "Платёжный шлюз запущен. Способ оплаты: %s. Тарифы: %s",
        "Telegram Stars" if config.STAR_PAYMENTS else "ЮKassa (тест)",
        [t["key"] for t in config.TIERS],
    )
    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
