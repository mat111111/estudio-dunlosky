"""Modo IA opcional: Claude (API de Anthropic) o Gemini (API de Google).

La app funciona completa sin esto. Si se configura una clave, se usa para:
  1. corregir respuestas abiertas de forma semántica (no solo por palabras), y
  2. generar preguntas adicionales de mejor calidad.

Toda pregunta generada por IA debe citar un fragmento literal de la fuente; si
la cita no aparece en el texto descargado, la pregunta se descarta. Así la
información siempre queda verificada contra la fuente, no contra el modelo.
"""
from __future__ import annotations

import asyncio
import json
import re

import httpx
from rapidfuzz import fuzz

from . import textproc as tp

ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_VERSION = "2023-06-01"
GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"

PROVIDERS = {
    "anthropic": {"name": "Claude (Anthropic)", "default_model": "claude-haiku-5-5"},
    "gemini": {"name": "Gemini (Google)", "default_model": "gemini-3.5-flash-lite"},
}


class AIConfig:
    def __init__(self, key: str | None, model: str | None, provider: str = "anthropic"):
        self.provider = provider if provider in PROVIDERS else "anthropic"
        self.key = (key or "").strip() or None
        self.model = (model or "").strip() or PROVIDERS[self.provider]["default_model"]

    @property
    def enabled(self) -> bool:
        return bool(self.key)

    @property
    def label(self) -> str:
        return f"{PROVIDERS[self.provider]['name']}, {self.model}"


async def _call_anthropic(cfg: AIConfig, system: str, user: str, max_tokens: int) -> str:
    headers = {"x-api-key": cfg.key, "anthropic-version": ANTHROPIC_VERSION, "content-type": "application/json"}
    body = {"model": cfg.model, "max_tokens": max_tokens, "system": system,
            "messages": [{"role": "user", "content": user}]}
    async with httpx.AsyncClient(timeout=httpx.Timeout(60.0, connect=10.0)) as cli:
        r = await cli.post(ANTHROPIC_URL, headers=headers, json=body)
        r.raise_for_status()
        data = r.json()
    return "".join(b.get("text", "") for b in data.get("content", []) if b.get("type") == "text")


async def _call_gemini(cfg: AIConfig, system: str, user: str, max_tokens: int, want_json: bool,
                       tools: list | None = None, raw: bool = False):
    headers = {"x-goog-api-key": cfg.key, "content-type": "application/json"}
    gen = {"maxOutputTokens": max_tokens + 1024}  # el razonamiento interno comparte este límite
    if want_json and not tools:
        gen["responseMimeType"] = "application/json"
    body = {
        "systemInstruction": {"parts": [{"text": system}]},
        "contents": [{"role": "user", "parts": [{"text": user}]}],
        "generationConfig": {**gen, "thinkingConfig": {"thinkingLevel": "low"}},
    }
    if tools:
        body["tools"] = tools
    url = GEMINI_URL.format(model=cfg.model)
    async with httpx.AsyncClient(timeout=httpx.Timeout(90.0, connect=10.0)) as cli:
        r = await cli.post(url, headers=headers, json=body)
        if r.status_code == 400 and "thinking" in r.text.lower():
            # algunos modelos no aceptan configurar el razonamiento: se reintenta sin eso
            body["generationConfig"] = gen
            r = await cli.post(url, headers=headers, json=body)
        r.raise_for_status()
        data = r.json()
    parts = (((data.get("candidates") or [{}])[0].get("content") or {}).get("parts")) or []
    text = "".join(p.get("text", "") for p in parts if not p.get("thought"))
    return (text, data) if raw else text


TRANSIENT = {429, 500, 502, 503, 504, 529}  # sobrecarga o límite momentáneo: vale la pena reintentar
GEMINI_FALLBACK = ["gemini-3.6-flash", "gemini-3.5-flash-lite", "gemini-3.8-flash"]


async def _call_once(cfg: AIConfig, model: str, system: str, user: str, max_tokens: int, want_json: bool,
                     tools: list | None = None, raw: bool = False):
    c = AIConfig(cfg.key, model, cfg.provider)
    if cfg.provider == "gemini":
        return await _call_gemini(c, system, user, max_tokens, want_json, tools, raw)
    return await _call_anthropic(c, system, user, max_tokens)


async def _call(cfg: AIConfig, system: str, user: str, max_tokens: int = 1500, want_json: bool = True,
                tools: list | None = None, raw: bool = False):
    """Llama a la IA con reintentos.

    Si el modelo está sobrecargado (503) o se pasó un límite por minuto (429), espera y
    reintenta. En Gemini, si el modelo elegido sigue sin responder, prueba otro modelo Flash.
    Guarda en cfg.used_model el modelo que finalmente respondió.
    """
    models = [cfg.model]
    if cfg.provider == "gemini":
        models += [m for m in GEMINI_FALLBACK if m != cfg.model]
    last: Exception | None = None
    for model in models:
        for wait in (0, 2, 5):
            if wait:
                await asyncio.sleep(wait)
            try:
                out = await _call_once(cfg, model, system, user, max_tokens, want_json, tools, raw)
                cfg.used_model = model
                return out
            except httpx.HTTPStatusError as e:
                last = e
                if e.response.status_code not in TRANSIENT:
                    raise
                if e.response.status_code == 429 and "quota" in e.response.text.lower() and "day" in e.response.text.lower():
                    raise  # cuota diaria agotada: reintentar no sirve
            except (httpx.TimeoutException, httpx.TransportError) as e:
                last = e
        if isinstance(last, httpx.HTTPStatusError) and last.response.status_code == 429:
            break  # un límite de uso afecta a todos los modelos por igual
    raise last  # type: ignore[misc]


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
        await _call(cfg, "Respondé solo con la palabra OK.", "ping", max_tokens=10, want_json=False)
        used = getattr(cfg, "used_model", cfg.model)
        if used != cfg.model:
            return True, f"Funciona, pero {cfg.model} estaba saturado y respondió {used}. La app cambia sola de modelo cuando hace falta."
        return True, "OK"
    except httpx.HTTPStatusError as e:
        code = e.response.status_code
        hint = {400: "la clave o el nombre del modelo no son válidos", 401: "la clave no es válida",
                403: "la clave no tiene permiso (¿la API está habilitada en ese proyecto?)",
                404: "ese modelo no existe o tu clave no tiene acceso; probá con otro de la lista",
                429: "se superó el límite de uso (en el nivel gratuito hay un máximo por minuto y por día)",
                500: "error momentáneo del servicio; probá de nuevo en un rato",
                503: "el servicio está saturado en este momento; probá de nuevo en unos minutos",
                529: "el servicio está saturado en este momento; probá de nuevo en unos minutos",
                }.get(code, "revisá la clave y el modelo")
        return False, f"La API respondió {code}: {hint}."
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
    "Sos un profesor universitario que escribe preguntas de examen en español (variante rioplatense, "
    "registro neutro), con ortografía, tildes, puntuación y concordancia impecables. Tus preguntas "
    "evalúan comprensión real, no memoria de frases: piden explicar, distinguir, relacionar, aplicar a "
    "un caso o predecir qué pasaría. Escribís siempre con tus propias palabras. Respondés solo JSON."
)

GEN_RULES = """Reglas obligatorias:
1. Redactá cada pregunta con tus propias palabras. PROHIBIDO copiar oraciones del texto, dejar espacios en blanco, pedir que se complete una palabra o preguntar por una palabra suelta.
2. Cada pregunta tiene que entenderse sola: no uses "según el texto", "en el párrafo", "el autor".
3. Evitá datos triviales (fechas, nombres propios, cifras) salvo que sean centrales para entender el tema.
4. Niveles: 1 = reconocer o identificar un concepto; 2 = comprender (explicar con otras palabras, distinguir conceptos parecidos, clasificar); 3 = aplicar o razonar (caso práctico, causa y efecto, predecir, comparar, detectar un error).
5. "mc": exactamente 4 opciones, una sola correcta. Las incorrectas son errores conceptuales plausibles (confusiones típicas de un estudiante), con largo y estructura parecidos a la correcta. Nada de "todas/ninguna de las anteriores" ni opciones absurdas.
6. "tf": una afirmación escrita por vos (no copiada). "answer" es "Verdadero" o "Falso". Las falsas contienen un error conceptual creíble, no un cambio de palabra evidente.
7. "open" y "why": "answer" es una respuesta modelo de 1 a 3 oraciones.
8. "explanation": por qué la respuesta es correcta y, en "mc", por qué cada distractor es incorrecto (2 a 4 oraciones).
9. "quote": copiá TEXTUAL, sin cambiar nada, el fragmento del texto (una oración o parte) que respalda la respuesta.
10. Antes de responder, revisá ortografía, tildes, signos de apertura (¿ ¡) y concordancia de cada pregunta y opción."""


def _ngrams(words: list[str], n: int) -> set[tuple]:
    return {tuple(words[i:i + n]) for i in range(len(words) - n + 1)}


def copies_source(text: str, source_ngrams: set[tuple], n: int = 8) -> bool:
    """True si el texto contiene un tramo de n palabras copiado literalmente de la fuente."""
    return bool(_ngrams(tp.normalize(text).split(), n) & source_ngrams)


def validate_question(q: dict, norm_text: str, source_ngrams: set[tuple]) -> dict | None:
    """Controles de calidad: formato, cita verificable y que no sea una copia del texto."""
    try:
        kind = str(q.get("kind", "")).strip().lower()
        if kind not in ("mc", "tf", "open", "why"):
            return None
        question = re.sub(r"\s+", " ", str(q.get("question", ""))).strip()
        answer = re.sub(r"\s+", " ", str(q.get("answer", ""))).strip()
        quote = str(q.get("quote", "")).strip()
        if len(question) < 15 or not answer or "___" in question or "…" * 2 in question:
            return None
        if not quote or fuzz.partial_ratio(tp.normalize(quote), norm_text) < 90:
            return None  # la cita no existe en la fuente: posible invención
        if copies_source(question, source_ngrams):
            return None  # copia literal del texto
        level = int(q.get("level") or 2)
        level = 1 if kind == "tf" else max(1, min(3, level))
        item = {"kind": kind, "prompt": question, "answer": answer, "context": quote, "hint": None,
                "options": None, "origin": "ia", "level": level,
                "explanation": re.sub(r"\s+", " ", str(q.get("explanation") or "")).strip() or None}
        if kind == "mc":
            opts = [re.sub(r"\s+", " ", str(o)).strip() for o in (q.get("options") or [])]
            opts = [o for o in opts if o]
            if len(opts) != 4 or len({tp.normalize(o) for o in opts}) != 4 or answer not in opts:
                return None
            if any(re.search(r"todas las anteriores|ninguna de las anteriores", o, re.I) for o in opts):
                return None
            item["options"] = opts
        elif kind == "tf":
            if tp.normalize(answer) not in ("verdadero", "falso"):
                return None
            item["answer"] = "Verdadero" if tp.normalize(answer) == "verdadero" else "Falso"
            item["options"] = ["Verdadero", "Falso"]
            if copies_source(question, source_ngrams, 10):
                return None
        return item
    except (TypeError, ValueError, AttributeError):
        return None


async def generate_questions(cfg: AIConfig, title: str, section_title: str, text: str, n: int = 8) -> list[dict]:
    """Genera un banco de preguntas de calidad para un fragmento del tema (todos los niveles)."""
    n = max(4, min(n, 12))
    n1 = max(1, round(n * 0.25))
    n3 = max(1, round(n * 0.35))
    n2 = n - n1 - n3
    user = (
        f"Tema: {title}\nSección: {section_title}\n\nTexto fuente:\n\"\"\"\n{text[:7000]}\n\"\"\"\n\n"
        f"Escribí {n} preguntas: {n1} de nivel 1, {n2} de nivel 2 y {n3} de nivel 3. "
        "Usá sobre todo 'mc' (opción múltiple conceptual), y además algunas 'tf', 'why' (por qué / causa y efecto) "
        "y 'open' (explicar con tus palabras).\n\n" + GEN_RULES + "\n\n"
        'Formato: [{"kind": "mc"|"tf"|"open"|"why", "level": 1|2|3, "question": "...", "answer": "...", '
        '"options": ["...", "...", "...", "..."] (solo mc, incluye la correcta textual), '
        '"explanation": "...", "quote": "fragmento textual del texto"}]'
    )
    try:
        data = _json_block(await _call(cfg, GEN_SYSTEM, user, 4000))
    except Exception:  # noqa: BLE001
        return []
    norm_text = tp.normalize(text)
    src_ngrams = _ngrams(norm_text.split(), 8)
    out, seen = [], set()
    for q in data if isinstance(data, list) else []:
        item = validate_question(q, norm_text, src_ngrams) if isinstance(q, dict) else None
        if item and tp.normalize(item["prompt"]) not in seen:
            seen.add(tp.normalize(item["prompt"]))
            out.append(item)
    return out


# --------------------------------------------------------------------------- #
# Explicaciones ("¿por qué?")
# --------------------------------------------------------------------------- #
EXPLAIN_SYSTEM = (
    "Sos un profesor particular paciente. Explicás en español rioplatense, claro y concreto, para un "
    "estudiante. Te basás en los fragmentos de la fuente que se te dan; si algo no está en ellos, lo "
    "aclarás en lugar de inventarlo. Respondé solo JSON."
)


async def explain_concept(cfg: AIConfig, topic: str, term: str, excerpts: list[str]) -> dict | None:
    user = (
        f"Tema: {topic}\nConcepto: {term}\n\nFragmentos de la fuente:\n"
        + "\n".join(f"- {e}" for e in excerpts[:8])
        + '\n\nDevolvé JSON: {"que_es": "qué es, en 1-2 oraciones simples", '
        '"por_que": "por qué es así o por qué importa dentro del tema, 2-3 oraciones", '
        '"ejemplo": "un ejemplo o analogía concreta y breve", "relacion": "con qué otros conceptos del tema se conecta, 1 oración"}'
    )
    try:
        data = _json_block(await _call(cfg, EXPLAIN_SYSTEM, user, 700))
        return {k: str(data.get(k, "")).strip() for k in ("que_es", "por_que", "ejemplo", "relacion")}
    except Exception:  # noqa: BLE001
        return None


async def concept_map(cfg: AIConfig, topic: str, text: str) -> dict | None:
    """Mapa conceptual al estilo de Novak: conceptos (sustantivos) unidos por frases de enlace."""
    user = (
        f"Tema: {topic}\n\nTexto de estudio:\n{text[:9000]}\n\n"
        "Armá un mapa conceptual del tema basado SOLO en el texto. Reglas: entre 8 y 16 conceptos breves "
        "(1 a 4 palabras, sin verbos); el primero es el concepto central; cada relación tiene una frase de enlace "
        "corta con verbo (por ejemplo «se divide en», «ocurre en», «produce», «es un tipo de») de modo que "
        "«concepto origen + frase + concepto destino» forme una afirmación verdadera según el texto; organizá de lo "
        "general a lo particular; incluí alguna relación cruzada entre ramas si el texto la justifica. "
        'Devolvé JSON: {"conceptos": ["..."], "relaciones": [{"desde": "...", "frase": "...", "hasta": "..."}]}'
    )
    try:
        data = _json_block(await _call(cfg, EXPLAIN_SYSTEM, user, 1500))
    except Exception:  # noqa: BLE001
        return None
    concepts = [str(c).strip()[:60] for c in data.get("conceptos", []) if str(c).strip()][:18]
    names = {c.lower() for c in concepts}
    rels = []
    for r in data.get("relaciones", []):
        a, b = str(r.get("desde", "")).strip(), str(r.get("hasta", "")).strip()
        if a.lower() in names and b.lower() in names and a.lower() != b.lower():
            rels.append({"from": a, "to": b, "label": str(r.get("frase", "")).strip()[:50]})
    if len(concepts) < 3 or not rels:
        return None
    return {"concepts": concepts, "links": rels[:30]}


async def explain_answer(cfg: AIConfig, question: str, answer: str, options: list | None, context: str) -> str | None:
    user = (
        f"Pregunta: {question}\nRespuesta correcta: {answer}\n"
        + (f"Opciones: {', '.join(options)}\n" if options else "")
        + f"Fragmento de la fuente (y su contexto): {context}\n\n"
        'Explicá por qué esa es la respuesta correcta y, si hay opciones, por qué las otras no. '
        'Devolvé JSON: {"explicacion": "3-4 oraciones"}'
    )
    try:
        data = _json_block(await _call(cfg, EXPLAIN_SYSTEM, user, 500))
        return str(data.get("explicacion", "")).strip() or None
    except Exception:  # noqa: BLE001
        return None


# --------------------------------------------------------------------------- #
# Búsqueda web (Google, a través de Gemini) y material de estudio generado
# --------------------------------------------------------------------------- #
class SearchUnavailable(Exception):
    pass


async def web_search(cfg: AIConfig, query: str) -> dict:
    """Busca en Google usando la herramienta de búsqueda de Gemini.

    Devuelve las páginas que Google encontró (para importarlas como fuente) y el
    widget de sugerencias de búsqueda que Google exige mostrar.
    """
    if cfg.provider != "gemini" or not cfg.enabled:
        raise SearchUnavailable("La búsqueda en Google necesita una clave de Gemini.")
    system = "Buscás material de estudio confiable en la web. Respondé en español, breve."
    user = (f"Buscá en Google páginas con buena información para estudiar «{query}»: apuntes universitarios, "
            "documentación oficial, artículos de divulgación o académicos. Resumí en 3 oraciones qué encontraste.")
    text, data = await _call(cfg, system, user, 600, want_json=False, tools=[{"google_search": {}}], raw=True)
    meta = ((data.get("candidates") or [{}])[0].get("groundingMetadata")) or {}
    chunks = meta.get("groundingChunks") or []
    snippets: dict[int, str] = {}
    for sup in meta.get("groundingSupports") or []:
        seg = (sup.get("segment") or {}).get("text", "")
        for i in sup.get("groundingChunkIndices") or []:
            snippets.setdefault(i, seg)
    results, seen = [], set()
    for i, ch in enumerate(chunks):
        web = ch.get("web") or {}
        uri, title = web.get("uri"), (web.get("title") or "").strip()
        if not uri or (title, uri) in seen:
            continue
        seen.add((title, uri))
        results.append({"site": "web", "source_name": title or "Web", "lang": "es", "title": title or uri,
                        "snippet": snippets.get(i, ""), "words": 0, "url": uri})
    return {"results": results, "summary": text.strip(),
            "suggestions_html": (meta.get("searchEntryPoint") or {}).get("renderedContent"),
            "queries": meta.get("webSearchQueries") or []}


MATERIAL_SYSTEM = (
    "Sos un docente universitario que escribe apuntes de estudio en español rioplatense. Escribís SOLO "
    "a partir de las fuentes que se te dan: no agregás datos que no estén en ellas. Organizás la "
    "información de forma didáctica: de lo general a lo particular, con definiciones, causas, ejemplos "
    "y relaciones entre conceptos."
)

LEVEL_TEXT = {
    "basico": "nivel básico: para alguien que recién empieza, lenguaje simple, con ejemplos cotidianos",
    "intermedio": "nivel intermedio: estudiante universitario, con vocabulario técnico explicado",
    "avanzado": "nivel avanzado: preparación de examen, con detalle técnico, comparaciones y casos",
}


async def generate_material(cfg: AIConfig, query: str, level: str, focus: str, sources: list[dict]) -> str:
    """Arma un apunte con secciones '## Título' a partir de los textos de las fuentes."""
    blocks = []
    budget = 14000
    for i, src in enumerate(sources, 1):
        body = "\n".join(f"{s['title']}: {s['text']}" for s in src["sections"])
        part = body[: max(2000, budget // max(len(sources), 1))]
        blocks.append(f"[Fuente {i}: {src['source_name']}, «{src['title']}»]\n{part}")
    user = (
        f"Tema: {query}\nNivel: {LEVEL_TEXT.get(level, LEVEL_TEXT['intermedio'])}\n"
        + (f"Enfoque pedido por el estudiante: {focus}\n" if focus else "")
        + "\nFuentes:\n" + "\n\n".join(blocks)
        + "\n\nEscribí un apunte de estudio de 800 a 1500 palabras. Usá títulos de sección con '## ' "
          "(entre 4 y 8 secciones), párrafos completos (no solo viñetas) y, al final de cada sección, "
          "una línea 'Fuente: N' indicando el número de la fuente usada. No incluyas preguntas."
    )
    text = await _call(cfg, MATERIAL_SYSTEM, user, 3500, want_json=False)
    text = re.sub(r"^```\w*\n?|```$", "", text.strip(), flags=re.M).strip()
    return text
