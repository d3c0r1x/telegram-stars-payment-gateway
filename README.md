# Платёжный шлюз для AI-подписки (Проект 4)

Бот даёт доступ к AI-аналитике (Проект 2) только после оплаты подписки:
**Telegram Stars** или **тестовый режим ЮKassa**. Статус пользователя хранится
в SQLite и обновляется обработчиком `successful_payment`.

## Стек (строго по ТЗ)

| Библиотека | Зачем                                                        |
|------------|--------------------------------------------------------------|
| aiogram    | `PreCheckoutQuery` + `SuccessfulPayment` (Telegram Bot Payments API) |
| aiosqlite  | SQLite: статус подписки пользователя (в ТЗ — «SQLite база данных») |

## Команды

- `/subscribe` — оплатить подписку (инвойс)
- `/status` — статус подписки
- `/unsubscribe` — отключить
- `/analyze` — AI-анализ (доступен **только** после оплаты; делегирует в Проект 2)

## Запуск

```bash
pip install -r requirements.txt
export WB_BOT_TOKEN=123456:ABC...
python bot.py
```

## Настройка оплаты

1. **Telegram Stars** (по умолчанию): `STAR_PAYMENTS=1`. Ничего дополнительно
   настраивать не нужно — `provider_token=""`, валюта `XTR`.
   Официально: [Telegram Bot API — Payments](https://core.telegram.org/bots/payments)
   и раздел про Stars в [документации](https://core.telegram.org/bots/api#sendinvoice).
2. **ЮKassa (тест)**: `STAR_PAYMENTS=0` + `YOOKASSA_PROVIDER_TOKEN` — тестовый
   токен провайдера выдаёт **@BotFather → Payments**. Валюта `RUB`, сумма в
   копейках (×100).

## Честное примечание

- Для приёма реальных платежей бот должен быть создан в BotFather с включённым
  режимом Payments; для Stars дополнительная сертификация не нужна.
- Бот работает и без активной оплаты: `/subscribe` покажет инвойс, но без
  подтверждения платежа (обработчик `pre_checkout_query`) доступ не откроется —
  это поведение соответствует ТЗ.
