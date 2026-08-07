"""Конфигурация платёжного шлюза через переменные окружения."""
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

BOT_TOKEN = os.getenv("WB_BOT_TOKEN", "")
DB_PATH = os.getenv("WB_DB_PATH", os.path.join(BASE_DIR, "subscriptions.db"))

# 1 = Telegram Stars (provider_token пустой, валюта XTR) | 0 = тестовый режим ЮKassa
STAR_PAYMENTS = os.getenv("STAR_PAYMENTS", "1") == "1"

PRICE_STARS = int(os.getenv("PRICE_STARS", "50"))       # 50 ⭐ за подписку
PRICE_RUB = int(os.getenv("PRICE_RUB", "199"))          # или 199 ₽ через ЮKassa
# Тестовый токен провайдера для ЮKassa выдаёт @BotFather (меню Payments)
YOOKASSA_PROVIDER_TOKEN = os.getenv("YOOKASSA_PROVIDER_TOKEN", "")

SUBSCRIPTION_DAYS = int(os.getenv("SUBSCRIPTION_DAYS", "30"))
