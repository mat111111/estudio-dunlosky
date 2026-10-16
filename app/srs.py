"""Práctica distribuida: algoritmo SM-2 adaptado (repetición espaciada)."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone


def now() -> datetime:
    return datetime.now(timezone.utc)


def iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat(timespec="seconds")


def quality_from(verdict: str, used_hint: bool = False) -> int:
    if verdict == "correct":
        return 4 if used_hint else 5
    if verdict == "partial":
        return 3
    return 1


def schedule(ease: float, interval: float, reps: int, lapses: int, q: int) -> dict:
    """Devuelve el nuevo estado del ítem.

    - Respuesta incorrecta: vuelve a aparecer en 10 minutos (entra en el repaso de hoy).
    - Respuesta correcta: 1 día, 3 días y luego intervalo * facilidad.
    """
    ease = max(1.3, ease + 0.1 - (5 - q) * (0.08 + (5 - q) * 0.02))
    if q < 3:
        reps = 0
        lapses += 1
        interval = 0.0
        due = now() + timedelta(minutes=10)
    else:
        reps += 1
        if reps == 1:
            interval = 1.0
        elif reps == 2:
            interval = 3.0
        else:
            interval = round(max(interval, 1.0) * ease, 1)
        if q == 3:  # parcial: intervalo más corto
            interval = max(1.0, round(interval * 0.6, 1))
        due = now() + timedelta(days=interval)
    return {"ease": round(ease, 2), "interval": interval, "reps": reps, "lapses": lapses, "due": iso(due)}
