"""Modo IA opcional (Claude API).

La app funciona completa sin esto. Si el usuario configura una clave de la API
de Anthropic, se usa para:
  1. corregir respuestas abiertas de forma semántica (no solo por palabras), y
  2. generar preguntas adicionales de mejor calidad.

Toda pregunta generada por IA debe citar un fragmento literal de la fuente; si
la cita no aparece en el texto descargado, la pregunta se descarta. Así la
información siempre queda verificada contra la fuente, no contra el modelo.
"""
from __future__ import annotations

import json
import re

import httpx
from rapidfuzz import fuzz

from . import textproc as tp

API_URL = "https://api.anthropic.com/v1/messages"
API_VERSION = "2023-06-01"
DEFAULT_MODEL = "claude-sonnet-5-5"


class AIConfig:
    def __init__(self, key: str | None, model: str | None):
        self.key = (key or "").strip() or None
        self.model = (model or "").strip() or DEFAULT_MODEL

    @property
    def enabled(self) -> bool:
        return bool(self.key)


async def _call(cfg: AIConfig, system: str, user: str, max_tokens: int = 1500) -> str:
    headers = {
        "x-api-key": cfg.key,
        "anthropic-version": API_VERSION,
        "content-type": "application/json",
    }
    body = {
        "model": cfg.model,
        "max_tokens": max_tokens,
        "system": system,
        "messages": [{"role": "user", "content": user}],
    }
    async with httpx.AsyncClient(timeout=httpx.Timeout(60.0, connect=10.0)) as cli:
        r = await cli.post(API_URL, headers=headers, json=body)
        r.raise_for_status()
        data = r.json()
    return "".join(b.get("text", "") for b in data.get("content", []) if b.get("type") == "text")


def _json_block(text: str):
    m = re.search(r"```(?:json)?\s*(.+?)```", text, re.S)
    if m:
        text = m.group(1)
    start = min([i for i in (text.find("{"), text.find("[")) if i != -1], default=-1)
    if start == -1:
        raise ValueError("sin JSON")
    return json.loads(text[start: max(text.rfind("}"), text.rfind("]")) + 1])


async def test_connection(cfg: AIConfig) -> tuple[bool, str]:
    try:
        out = await _call(cfg, "Respondé solo con la palabra OK.", "ping", max_tokens=10)
        return True, out.strip() or "OK"
    except httpx.HTTPStatusError as e:
        return False, f"La API respondió {e.response.status_code}: revisá la clave y el modelo."
    except Exception as e:  # noqa: BLE001
        return False, f"No se pudo conectar ({type(e).__name__})."


GRADE_SYSTEM = (
    "Sos un profesor que corrige respuestas de estudiantes comparándolas EXCLUSIVAMENTE con el "
    "fragmento de la fuente que se te da. No uses conocimiento externo para dar por correcta una "
    "respuesta que la fuente no respalda. Sé justo con sinónimos y paráfrasis. Respondé solo JSON."
)


async def grade_open(cfg: AIConfig, question: str, reference: str, context: str, answer: str) -> dict | None:
    user = (
        f"Pregunta: {question}\n\nRespuesta esperada (según la fuente): {reference}\n\n"
        f"Fragmento de la fuente: {context}\n\nRespuesta del estudiante: {answer}\n\n"
        'Devolvé JSON: {"verdict": "correct"|"partial"|"incorrect", "score": 0..1, '
        '"feedback": "1-2 oraciones en español rioplatense explicando qué está bien y qué falta o es erróneo", '
        '"missing": ["conceptos de la fuente que faltaron"], "errors": ["afirmaciones del estudiante que contradicen la fuente"]}'
    )
    try:
        data = _json_block(await _call(cfg, GRADE_SYSTEM, user, 600))
        if data.get("verdict") not in ("correct", "partial", "incorrect"):
            return None
        return {
            "verdict": data["verdict"],
            "score": float(data.get("score", 0)),
            "feedback": str(data.get("feedback", "")),
            "missing": [str(x) for x in data.get("missing", [])][:8],
            "errors": [str(x) for x in data.get("errors", [])][:5],
            "matched": [],
            "by": "ia",
        }
    except Exception:  # noqa: BLE001 - cualquier falla vuelve a la corrección heurística
        return None


GEN_SYSTEM = (
    "Generás preguntas de estudio a partir de un texto fuente. Cada pregunta debe poder responderse "
    "solo con el texto y debe incluir una cita literal (copiada exacta) del fragmento que la respalda. "
    "Priorizá comprensión: causas, relaciones, comparaciones y definiciones, no detalles triviales. "
    "Respondé solo con JSON."
)


async def generate_questions(cfg: AIConfig, title: str, section_title: str, text: str, n: int = 5) -> list[dict]:
    user = (
        f"Tema: {title}\nSección: {section_title}\n\nTexto fuente:\n\"\"\"\n{text[:6000]}\n\"\"\"\n\n"
        f"Generá {n} preguntas en español. Mezclá tipos: 'open' (respuesta corta a desarrollar), "
        "'why' (por qué / cómo se relaciona) y 'mc' (opción múltiple con 4 opciones plausibles). "
        'Formato: [{"kind": "open"|"why"|"mc", "question": "...", "answer": "respuesta correcta breve", '
        '"options": ["..."] (solo mc, incluye la correcta), "quote": "cita literal del texto"}]'
    )
    try:
        data = _json_block(await _call(cfg, GEN_SYSTEM, user, 2500))
    except Exception:  # noqa: BLE001
        return []
    norm_text = tp.normalize(text)
    out = []
    for q in data if isinstance(data, list) else []:
        try:
            kind = q["kind"] if q["kind"] in ("open", "why", "mc") else "open"
            quote = str(q.get("quote", "")).strip()
            # Verificación: la cita tiene que existir en la fuente descargada
            if not quote or fuzz.partial_ratio(tp.normalize(quote), norm_text) < 90:
                continue
            item = {
                "kind": kind, "prompt": str(q["question"]).strip(), "answer": str(q["answer"]).strip(),
                "context": quote, "hint": None, "options": None, "origin": "ia",
            }
            if kind == "mc":
                opts = [str(o) for o in q.get("options", [])][:4]
                if item["answer"] not in opts or len(opts) < 3:
                    continue
                item["options"] = opts
            out.append(item)
        except (KeyError, TypeError):
            continue
    return out
