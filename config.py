"""Конфигурация платёжного шлюза через переменные окружения."""
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

BOT_TOKEN = os.getenv("WB_BOT_TOKEN", "")
DB_PATH = os.getenv("WB_DB_PATH", os.path.join(BASE_DIR, "subscriptions.db"))

# 1 = Telegram Stars (provider_token пустой, валюта XTR) | 0 = тестовый режим ЮKassa
STAR_PAYMENTS = os.getenv("STAR_PAYMENTS", "1") == "1"

# --- Продвинутый уровень: тарифы ---
# (key, label, stars, rub) — price для Telegram Stars и для ЮKassa (рубли)
TIERS: list[dict] = [
    {"key": "starter", "label": "Старт (30 дней)", "stars": 50, "rub": 199},
    {"key": "pro", "label": "Про (90 дней)", "stars": 120, "rub": 499},
    {"key": "business", "label": "Бизнес (180 дней)", "stars": 200, "rub": 899},
]
# Резервные значения для обратной совместимости (используются в /status и т.п.)
PRICE_STARS = int(os.getenv("PRICE_STARS", "50"))
PRICE_RUB = int(os.getenv("PRICE_RUB", "199"))
# Тестовый токен провайдера для ЮKassa выдаёт @BotFather (меню Payments)
YOOKASSA_PROVIDER_TOKEN = os.getenv("YOOKASSA_PROVIDER_TOKEN", "")

SUBSCRIPTION_DAYS = int(os.getenv("SUBSCRIPTION_DAYS", "30"))

# Бесплатный пробный период (дней); один раз на пользователя
TRIAL_DAYS = int(os.getenv("TRIAL_DAYS", "3"))

# Минимальный интервал между сообщениями пользователя (секунды)
THROTTLE_MIN_INTERVAL = float(os.getenv("THROTTLE_MIN_INTERVAL", "0.7"))


def tier_by_key(key: str) -> dict | None:
    """Ищет тариф по ключу (например 'pro'); None — если нет такого."""
    return next((t for t in TIERS if t["key"] == key), None)


def parse_payload(payload: str) -> dict | None:
    """Разбирает payload счёта 'sub:<key>' в тариф; None — если невалиден.

    Валидация на стороне сервера: даже если клиент подменит payload,
    тариф не из того набора не пройдёт.
    """
    if not payload or not payload.startswith("sub:"):
        return None
    return tier_by_key(payload.split(":", 1)[1])
