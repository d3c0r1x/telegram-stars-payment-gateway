# Telegram Stars Payment Gateway

**Payment/subscription component for Telegram AI products.**

[![CI](https://github.com/d3c0r1x/telegram-stars-payment-gateway/actions/workflows/ci.yml/badge.svg)](https://github.com/d3c0r1x/telegram-stars-payment-gateway/actions/workflows/ci.yml)

A focused example of a paid-feature flow: the user selects a plan, pays through Telegram Stars, receives access for the subscription period, and can later receive a refund with access revoked.

## What it demonstrates

- `PreCheckoutQuery` / `SuccessfulPayment` handling;
- subscription state in SQLite;
- trial periods;
- refunds;
- server-side validation of tariff/payment payload;
- tests and GitHub Actions.

## Stack

Python · aiogram 3 · Telegram Stars · SQLite · pytest · GitHub Actions

## Local run

```bash
python -m venv .venv
pip install -r requirements.txt
python bot.py
```

No public demo is provided because the project requires a running Telegram bot/payment environment.
