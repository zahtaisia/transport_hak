# Как подключить API (для фронтендера)

**Базовый адрес:** `http://<IP-бэкендера>:8000` (локально — `http://localhost:8000`)
**Интерактивная документация (можно тыкать кнопками):** `/docs`
**Проверка, что сервер жив:** `GET /health` → `{"status":"ok"}`

## Запрос

`POST /api/forecast`, тело — JSON:

```json
{
  "route": "5",
  "timestamp": "2026-09-28T08:30:00",
  "temperature_c": 12.5,
  "precipitation_mm": 0,
  "is_holiday": null
}
```

`is_holiday` можно не передавать — определится автоматически.

## Ответ

```json
{
  "route": "5",
  "timestamp": "2026-09-28T08:30:00",
  "load_percent": 74,
  "uncertainty_percent": 8,
  "range_low": 66,
  "range_high": 82,
  "level": "high",
  "level_label": "Тесно",
  "is_weekend": false,
  "is_holiday": false,
  "factors": ["Утренний час пик"],
  "explanation": "Текст от ИИ-ассистента для пассажира...",
  "hourly": [{"hour": 5, "load_percent": 18}, {"hour": 6, "load_percent": 30}]
}
```

- `load_percent` — прогноз загрузки, 0–100
- `uncertainty_percent` — неопределённость в процентных пунктах («74% ± 8»)
- `range_low` / `range_high` — готовый диапазон для полосы на шкале
- `level` — `low` / `medium` / `high` (для цвета: зелёный / жёлтый / красный)
- `hourly` — точки для графика загрузки по часам
- `explanation` — готовый текст для карточки ассистента

## Пример на JavaScript

```js
const API = "http://localhost:8000";

async function getForecast(params) {
  const res = await fetch(`${API}/api/forecast`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(params),
  });
  if (!res.ok) throw new Error(`Ошибка API: ${res.status}`);
  return res.json();
}

getForecast({
  route: "5",
  timestamp: "2026-09-28T08:30:00",
  temperature_c: 12.5,
  precipitation_mm: 0,
}).then((d) => {
  console.log(`${d.load_percent}% ± ${d.uncertainty_percent}`, d.explanation);
});
```

## Важно

- Ответ может идти 1–3 секунды (ИИ пишет объяснение) — покажите индикатор загрузки.
- Ошибка 422 — неверный формат запроса, подробности в теле ответа.
- API-ключа GigaChat у фронтенда быть не должно — он живёт только на сервере.