# Telegram Stars Payment Gateway

> **Прикладной платёжный компонент.** Я использовал проект как отдельный модуль, на котором отрабатывал полноценный flow платной функции Telegram: тариф → checkout → успешная оплата → доступ на период подписки → refund → отзыв доступа.
>
> Репозиторий небольшой, но задача в нём прикладная: важно корректно обработать состояние платежа, проверить payload на сервере и не доверять данным клиента.

[![CI](https://github.com/d3c0r1x/telegram-stars-payment-gateway/actions/workflows/ci.yml/badge.svg)](https://github.com/d3c0r1x/telegram-stars-payment-gateway/actions/workflows/ci.yml)

## Возможности

- Telegram Stars;
- `PreCheckoutQuery`;
- `SuccessfulPayment`;
- подписки;
- бесплатный trial;
- SQLite;
- refunds;
- отзыв подписки после refund;
- серверная проверка tariff/payment payload;
- tests + GitHub Actions.

## Flow

```
user
 ↓
choose tariff
 ↓
invoice / checkout
 ↓
PreCheckoutQuery
 ↓
SuccessfulPayment
 ↓
subscription activated
 ↓
period expires / refund
 ↓
access revoked
```

## Тарифы

Текущая конфигурация задаётся в `config.py`:

| Тариф | Stars | Срок |
|---|---:|---:|
| starter | 50 | 30 дней |
| pro | 120 | 90 дней |
| business | 200 | 180 дней |

Trial по умолчанию — 3 дня.

## Структура

```
bot.py          # Telegram payment flow
config.py       # tariffs and env
db.py           # subscription state
ai_service.py   # optional paid AI integration
middlewares.py  # throttling / logging
tests/
  test_smoke.py
```

## Запуск

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python bot.py
```

Windows:

```bat
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
python bot.py
```

В `.env` токен читается из `WB_BOT_TOKEN` — это историческое имя переменной в текущем коде.

## Telegram Stars

Для Stars используется:

```
STAR_PAYMENTS=1
```

Provider token для Stars не нужен.

## Test / YuKassa compatibility

При:

```
STAR_PAYMENTS=0
```

код переключается на тестовый provider flow, где используется `YOOKASSA_PROVIDER_TOKEN`.

## Пример пользовательского сценария

1. пользователь открывает бота;
2. выбирает `starter`;
3. получает invoice;
4. Telegram вызывает `PreCheckoutQuery`;
5. сервер проверяет payload;
6. приходит `SuccessfulPayment`;
7. в SQLite записывается срок подписки;
8. при refund доступ аннулируется.

## Security principle

Клиент не должен иметь возможность сам выбрать тариф через произвольный payload.

Проверка проходит через:

```
parse_payload()
  ↓
tier_by_key()
  ↓
known tariff
```

Таким образом backend сам определяет, существует ли выбранный тариф.

## Конфигурация

Основные переменные:

| Переменная | Назначение |
|---|---|
| `WB_BOT_TOKEN` | Telegram Bot Token |
| `STAR_PAYMENTS` | Stars / test provider |
| `YOOKASSA_PROVIDER_TOKEN` | test provider |
| `TRIAL_DAYS` | trial |
| `PRICE_STARS` | compatibility value |
| `SUBSCRIPTION_DAYS` | compatibility value |
| `THROTTLE_MIN_INTERVAL` | anti-spam |

## Тесты

```bash
pytest -q
```

CI проверяет smoke/payment logic без реального платежа.

## Ограничения

- нет публичного demo checkout;
- реальная оплата требует настроенного Telegram payment environment;
- production-версия потребует более богатого audit trail и мониторинга платежей.

## AI-assisted development

AI использовался для черновой реализации и рутинной работы.

Архитектура payment flow, проверка сценариев, debugging и финальная валидация — моя зона ответственности.

## Лицензия

MIT.
