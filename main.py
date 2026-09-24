#это мой файл, сюда не писать
import os
from datetime import datetime
from typing import List, Optional

from dotenv import load_dotenv

load_dotenv()  # читает .env до того, как код начнёт обращаться к ключу

from fastapi import FastAPI  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
from pydantic import BaseModel, Field  # noqa: E402

import predictor  # noqa: E402

app = FastAPI(title="Tram Load Forecast API", version="0.1.0")

# Без CORS браузер фронтендера заблокирует запросы к API
origins = os.getenv("CORS_ORIGINS", "*").split(",")
app.add_middleware(CORSMiddleware, allow_origins=origins,
                   allow_methods=["*"], allow_headers=["*"])


class ForecastRequest(BaseModel):
    route: str = Field(..., examples=["5"])
    timestamp: datetime = Field(..., examples=["2026-09-28T08:30:00"])
    temperature_c: float = Field(10, examples=[12.5])
    precipitation_mm: float = Field(0, examples=[0.0])
    is_holiday: Optional[bool] = Field(
        None, description="Если не передать — определится автоматически по календарю РФ")


class HourPoint(BaseModel):
    hour: int
    load_percent: int


class ForecastResponse(BaseModel):
    route: str
    timestamp: datetime
    load_percent: int
    uncertainty_percent: int
    range_low: int
    range_high: int
    level: str
    level_label: str
    is_weekend: bool
    is_holiday: bool
    factors: List[str]
    explanation: str
    hourly: List[HourPoint]


@app.get("/health")
def health():
    return {"status": "ok"}


# обычная def (не async): вызов GigaChat синхронный, FastAPI сам вынесет его в поток
@app.post("/api/forecast", response_model=ForecastResponse)
def forecast(req: ForecastRequest):
    result = predictor.forecast(req.timestamp, req.temperature_c,
                                req.precipitation_mm, req.is_holiday)
    explanation = predictor.explain(req.route, req.timestamp, result)
    return {"route": req.route, "timestamp": req.timestamp,
            "explanation": explanation, **result}