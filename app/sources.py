"""Obtención de información desde fuentes confiables.

Fuente principal: Wikipedia (API oficial de MediaWiki), en español con respaldo
en inglés. Cada sección guarda la URL y la revisión exacta del artículo, de modo
que cada pregunta se puede rastrear hasta el texto del que salió.
"""
from __future__ import annotations

import html
import re
import unicodedata

import httpx

USER_AGENT = "EstudioDunlosky/1.0 (aplicacion educativa local; https://github.com/)"
TIMEOUT = httpx.Timeout(20.0, connect=10.0)

SKIP_SECTIONS = {
    "referencias", "notas", "bibliografia", "enlaces externos", "vease tambien", "fuentes",
    "lecturas adicionales", "lectura adicional", "notas y referencias", "otras lecturas", "galeria",
    "references", "notes", "see also", "external links", "further reading", "bibliography",
    "sources", "citations", "footnotes", "gallery", "filmografia", "discografia",
}


class SourceError(Exception):
    pass


def _strip(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", s.lower()) if unicodedata.category(c) != "Mn")


def _clean_snippet(s: str) -> str:
    s = re.sub(r"<[^>]+>", "", s or "")
    return html.unescape(s).strip()


def _remove_braced(text: str, opener: str) -> str:
    """Elimina bloques tipo {\\displaystyle ...} con llaves balanceadas."""
    out = []
    i = 0
    while i < len(text):
        j = text.find(opener, i)
        if j == -1:
            out.append(text[i:])
            break
        out.append(text[i:j])
        depth = 0
        k = j
        while k < len(text):
            if text[k] == "{":
                depth += 1
            elif text[k] == "}":
                depth -= 1
                if depth == 0:
                    k += 1
                    break
            k += 1
        i = k
    return "".join(out)


def clean_extract(text: str) -> str:
    text = unicodedata.normalize("NFC", text)
    text = _remove_braced(text, "{\\displaystyle")
    text = _remove_braced(text, "{\\textstyle")
    text = re.sub(r"\[\d+\]|\[cita requerida\]|\[citation needed\]", "", text)
    text = re.sub(r"\(\s*[;,]?\s*\)", "", text)          # paréntesis vacíos
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r" ([,.;:])", r"\1", text)
    return text


def parse_sections(extract: str, page_title: str) -> list[dict]:
    """Convierte el texto plano con encabezados '== X ==' en secciones."""
    sections = []
    current = {"title": "Introducción", "level": 1, "lines": []}
    skipping_level = None
    for line in extract.split("\n"):
        m = re.match(r"^(={2,6})\s*(.+?)\s*\1\s*$", line.strip())
        if m:
            level = len(m.group(1))
            title = m.group(2).strip()
            if skipping_level is not None and level > skipping_level:
                continue
            skipping_level = None
            if current["lines"]:
                sections.append(current)
            if _strip(title) in SKIP_SECTIONS:
                skipping_level = level
                current = {"title": title, "level": level, "lines": []}
                continue
            current = {"title": title, "level": level, "lines": []}
            continue
        if skipping_level is not None:
            continue
        if line.strip():
            current["lines"].append(line.strip())
    if current["lines"] and skipping_level is None:
        sections.append(current)

    out = []
    for s in sections:
        body = "\n".join(s["lines"]).strip()
        # descartar secciones de puras listas cortas o vacías
        if len(body.split()) < 25:
            continue
        out.append({"title": s["title"], "text": body})
    if not out:
        raise SourceError(f"El artículo «{page_title}» no tiene suficiente texto para estudiar.")
    return out


def _api(lang: str) -> str:
    if lang not in ("es", "en"):
        lang = "es"
    return f"https://{lang}.wikipedia.org/w/api.php"


async def search_wikipedia(query: str, lang: str = "es", limit: int = 8) -> list[dict]:
    params = {
        "action": "query", "list": "search", "srsearch": query, "srlimit": limit,
        "format": "json", "utf8": 1, "srprop": "snippet|wordcount",
    }
    try:
        async with httpx.AsyncClient(headers={"User-Agent": USER_AGENT}, timeout=TIMEOUT) as cli:
            r = await cli.get(_api(lang), params=params)
            r.raise_for_status()
            data = r.json()
    except httpx.HTTPError as e:
        raise SourceError(
            "No se pudo conectar con Wikipedia. Revisá la conexión a internet del equipo "
            f"(detalle: {type(e).__name__})."
        ) from e
    results = []
    for it in data.get("query", {}).get("search", []):
        results.append({
            "title": it["title"],
            "snippet": _clean_snippet(it.get("snippet", "")),
            "words": it.get("wordcount", 0),
            "lang": lang,
            "url": f"https://{lang}.wikipedia.org/wiki/{it['title'].replace(' ', '_')}",
        })
    return results


async def fetch_wikipedia(title: str, lang: str = "es") -> dict:
    params = {
        "action": "query", "prop": "extracts|info|revisions", "explaintext": 1,
        "exsectionformat": "wiki", "titles": title, "redirects": 1, "inprop": "url",
        "rvprop": "ids|timestamp", "format": "json", "utf8": 1, "formatversion": 2,
    }
    try:
        async with httpx.AsyncClient(headers={"User-Agent": USER_AGENT}, timeout=TIMEOUT) as cli:
            r = await cli.get(_api(lang), params=params)
            r.raise_for_status()
            data = r.json()
    except httpx.HTTPError as e:
        raise SourceError(f"No se pudo descargar el artículo de Wikipedia ({type(e).__name__}).") from e

    pages = data.get("query", {}).get("pages", [])
    if not pages or pages[0].get("missing"):
        raise SourceError(f"No existe el artículo «{title}» en Wikipedia ({lang}).")
    page = pages[0]
    extract = clean_extract(page.get("extract", ""))
    rev = (page.get("revisions") or [{}])[0]
    sections = parse_sections(extract, page["title"])
    return {
        "title": page["title"],
        "lang": lang,
        "url": page.get("fullurl", f"https://{lang}.wikipedia.org/wiki/{page['title'].replace(' ', '_')}"),
        "revid": rev.get("revid"),
        "timestamp": rev.get("timestamp"),
        "source_name": f"Wikipedia ({lang})",
        "license": "CC BY-SA 4.0",
        "sections": sections,
    }


def from_user_notes(title: str, text: str) -> dict:
    """Permite estudiar los apuntes propios del usuario con las mismas técnicas."""
    text = unicodedata.normalize("NFC", text).replace("\r\n", "\n")
    # Si el usuario usó encabezados markdown (# Título), los respetamos
    sections = []
    current = {"title": "Apuntes", "lines": []}
    for line in text.split("\n"):
        m = re.match(r"^\s*(#{1,4})\s+(.+)$", line) or re.match(r"^\s*(={2,4})\s*(.+?)\s*={2,4}\s*$", line)
        if m:
            if current["lines"]:
                sections.append(current)
            current = {"title": m.group(2).strip(), "lines": []}
        elif line.strip():
            current["lines"].append(line.strip())
    if current["lines"]:
        sections.append(current)

    out = [{"title": s["title"], "text": "\n".join(s["lines"])} for s in sections
           if len(" ".join(s["lines"]).split()) >= 15]
    if not out:
        raise SourceError("El texto es muy corto: pegá al menos un párrafo (unas 30 palabras).")
    return {
        "title": title or "Mis apuntes",
        "lang": "es",
        "url": None,
        "revid": None,
        "timestamp": None,
        "source_name": "Apuntes propios",
        "license": None,
        "sections": out,
    }
