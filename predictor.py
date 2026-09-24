"""Логика прогноза загрузки трамвая.

ВАЖНО: пока данных нет, load считается простой эвристикой (baseline_load).
Когда организаторы пришлют данные — заменить baseline_load на обученную модель.
GigaChat используется ТОЛЬКО для текстового объяснения; числа считает модель,
потому что языковая модель не умеет честно оценивать неопределённость.
"""
import logging
import math
import os
from datetime import datetime
from typing import Optional

import holidays

log = logging.getLogger("predictor")
RU_HOLIDAYS = holidays.Russia()


def _peak(hour: float, center: float, width: float) -> float:
    return math.exp(-0.5 * ((hour - center) / width) ** 2)


def is_holiday(ts: datetime) -> bool:
    return ts.date() in RU_HOLIDAYS


def baseline_load(ts: datetime, temp_c: float, precip_mm: float, holiday: bool):
    """Возвращает (загрузка %, неопределённость в п.п., список факторов)."""
    hour = ts.hour + ts.minute / 60
    weekend = ts.weekday() >= 5 or holiday
    factors = []

    if weekend:
        load = 15 + 30 * _peak(hour, 13, 3.5)
        factors.append("Праздничный день" if holiday else "Выходной день")
    else:
        load = (15 + 55 * _peak(hour, 8, 1.3)
                + 50 * _peak(hour, 18, 1.6)
                + 15 * _peak(hour, 13, 3))
        if 7 <= hour <= 9.5:
            factors.append("Утренний час пик")
        elif 16.5 <= hour <= 19.5:
            factors.append("Вечерний час пик")

    uncertainty = 8
    if holiday:
        uncertainty += 4  # праздники редкие — данных мало
    if precip_mm >= 0.5:
        load *= 1.12
        uncertainty += 3
        factors.append("Осадки: больше людей выбирают трамвай")
    if temp_c <= -10 or temp_c >= 30:
        load *= 1.08
        uncertainty += 3
        factors.append("Экстремальная температура")

    if not factors:
        factors.append("Обычные условия")

    load = max(5, min(100, load))
    return round(load), min(uncertainty, 30), factors


def _level(load: int):
    if load < 40:
        return "low", "Свободно"
    if load < 70:
        return "medium", "Умеренно"
    return "high", "Тесно"


def forecast(ts: datetime, temp_c: float, precip_mm: float,
             holiday_override: Optional[bool] = None) -> dict:
    holiday = is_holiday(ts) if holiday_override is None else holiday_override
    load, unc, factors = baseline_load(ts, temp_c, precip_mm, holiday)
    level, label = _level(load)

    hourly = []
    for h in range(5, 24):  # для графика на дашборде; погода считается постоянной
        l, _, _ = baseline_load(ts.replace(hour=h, minute=0), temp_c, precip_mm, holiday)
        hourly.append({"hour": h, "load_percent": l})

    return {
        "load_percent": load,
        "uncertainty_percent": unc,
        "range_low": max(0, load - unc),
        "range_high": min(100, load + unc),
        "level": level,
        "level_label": label,
        "is_weekend": ts.weekday() >= 5,
        "is_holiday": holiday,
        "factors": factors,
        "hourly": hourly,
    }


# ---------- GigaChat ----------
_client = None


def _get_client():
    global _client
    if _client is None:
        from gigachat import GigaChat  # импорт здесь, чтобы API запускался и без ключа
        _client = GigaChat(
            credentials=os.environ["GIGACHAT_CREDENTIALS"],
            scope=os.getenv("GIGACHAT_SCOPE", "GIGACHAT_API_PERS"),
            model=os.getenv("GIGACHAT_MODEL", "GigaChat"),
            verify_ssl_certs=os.getenv("GIGACHAT_VERIFY_SSL", "false").lower() == "true",
            timeout=20,
        )
    return _client

WEEKDAYS = ["понедельник", "вторник", "среда", "четверг",
            "пятница", "суббота", "воскресенье"]

def explain(route: str, ts: datetime, result: dict) -> str:
    fallback = "; ".join(result["factors"]) + "."
    if not os.getenv("GIGACHAT_CREDENTIALS"):
        return fallback

    prompt = (
        "Ты — ассистент городского транспорта. Модель уже посчитала прогноз загрузки "
        "трамвая; числа менять и придумывать новые нельзя. Объясни пассажиру в 2–3 "
        "предложениях, почему загрузка такая, и дай один практический совет "
        "(например, когда лучше поехать). Не пиши «сегодня» или «завтра», называй "
        "день недели и время из данных. Упомяни, что прогноз приблизительный, "
        "с указанной погрешностью.\n\n"
        f"Маршрут: {route}\n"
        f"Время: {ts:%d.%m.%Y %H:%M}, день недели: {WEEKDAYS[ts.weekday()]}\n"
        f"Праздник: {'да' if result['is_holiday'] else 'нет'}\n"
        f"Загрузка: {result['load_percent']}% (±{result['uncertainty_percent']} п.п.)\n"
        f"Факторы: {', '.join(result['factors'])}"
    )
    try:
        resp = _get_client().chat(prompt)
        return resp.choices[0].message.content.strip()
    except Exception:
        log.exception("GigaChat недоступен, отдаю резервный текст")
        return fallback