"""Buscadores adicionales: académicos, de programación y de la web.

Toda la web, sin clave:
  - SearXNG: metabuscador que consulta a la vez Google, Bing, DuckDuckGo, Brave, Qwant, Startpage,
    Mojeek, Wikipedia y muchos más. Corre en su propio contenedor (docker-compose) y la app le pregunta
    por su API JSON. También tiene categorías de programación, ciencia y videos.
  - Marginalia: buscador independiente de la "web pequeña" (blogs, apuntes personales, sitios sin publicidad)
  - Hacker News: artículos de tecnología y programación
  - MDN Web Docs: documentación de programación web, en español

Sin clave:
  - OpenAlex: artículos académicos de todo el mundo (resumen y, si es de acceso abierto, texto)
  - Semantic Scholar, Crossref y DOAJ: artículos académicos (resúmenes), DOAJ solo acceso abierto
  - Open Library: libros con su descripción
  - arXiv: preprints de computación, matemática y física (resumen y versión HTML si existe)
  - Europe PMC: artículos de biología y salud (resumen)
  - Stack Overflow en español y en inglés: preguntas y respuestas de programación

Google:
  - Google Libros (sin clave): libros con su descripción
  - Serper y SerpApi (con clave): resultados de Google y de Google Académico
  - (Google vía Gemini está en ai.py: usa la búsqueda de Google integrada en Gemini)

Con clave (se carga en Ajustes):
  - Tavily: buscador web pensado para IA (1.000 búsquedas gratis por mes)
  - Brave Search: buscador web independiente
  - Web vía Claude: la herramienta de búsqueda de la API de Claude

Cada buscador devuelve resultados con el mismo formato que los wikis, y cada resultado
sabe cómo descargarse como fuente (``fetch``) para generar preguntas a partir de él.
"""
from __future__ import annotations

import asyncio
import html
import re
import xml.etree.ElementTree as ET
from urllib.parse import quote

import httpx

from . import sources
from .sources import SourceError, USER_AGENT

TIMEOUT = httpx.Timeout(20.0, connect=10.0)
CONTACT = "estudio-dunlosky@example.org"  # OpenAlex pide un mail de contacto para su "polite pool"

PROVIDERS: dict[str, dict] = {
    "searxng": {"name": "Toda la web (SearXNG)", "group": "Toda la web",
                "about": "Google, Bing, DuckDuckGo, Brave, Qwant, Startpage y más, a la vez", "keyname": "searxng",
                "needs_env": "SEARXNG_URL"},
    "searxng_it": {"name": "Programación en toda la web", "group": "Toda la web",
                   "about": "GitHub, Stack Overflow, MDN, documentación y más (vía SearXNG)", "keyname": "searxng",
                   "needs_env": "SEARXNG_URL"},
    "searxng_science": {"name": "Ciencia en toda la web", "group": "Toda la web",
                        "about": "Google Académico, arXiv, PubMed y más (vía SearXNG)", "keyname": "searxng",
                        "needs_env": "SEARXNG_URL"},
    "marginalia": {"name": "Marginalia", "group": "Toda la web", "about": "Buscador independiente: blogs y apuntes personales (en inglés)"},
    "hackernews": {"name": "Hacker News", "group": "Toda la web", "about": "Artículos de tecnología y programación (en inglés)"},
    "exa": {"name": "Exa", "group": "Toda la web", "about": "Buscador web por significado (US$10 gratis por mes)",
            "key": "exa_key", "env": "EXA_API_KEY"},
    "mdn": {"name": "MDN Web Docs", "group": "Programación", "about": "Documentación de HTML, CSS y JavaScript, en español"},
    "openalex": {"name": "OpenAlex", "group": "Académicos", "about": "Artículos académicos de todo el mundo",
                 "key": "openalex_key", "env": "OPENALEX_API_KEY", "key_optional": True},
    "arxiv": {"name": "arXiv", "group": "Académicos", "about": "Computación, matemática y física (preprints)"},
    "europepmc": {"name": "Europe PMC", "group": "Académicos", "about": "Biología, medicina y salud"},
    "semanticscholar": {"name": "Semantic Scholar", "group": "Académicos", "about": "Artículos científicos de todas las áreas"},
    "crossref": {"name": "Crossref", "group": "Académicos", "about": "Artículos de revistas de todo el mundo (con resumen)"},
    "doaj": {"name": "DOAJ", "group": "Académicos", "about": "Revistas científicas de acceso abierto (mucho en español)"},
    "openlibrary": {"name": "Open Library", "group": "Enciclopedias y libros", "about": "Libros con su descripción (Internet Archive)"},
    "so_es": {"name": "Stack Overflow en español", "group": "Programación", "about": "Preguntas y respuestas de programación"},
    "so_en": {"name": "Stack Overflow", "group": "Programación", "about": "La comunidad de programación más grande (en inglés)"},
    "se_net": {"name": "Network Engineering", "group": "Redes y sistemas", "about": "Redes: routing, switching, protocolos (en inglés)"},
    "se_serverfault": {"name": "Server Fault", "group": "Redes y sistemas", "about": "Administración de servidores y redes (en inglés)"},
    "se_unix": {"name": "Unix & Linux", "group": "Redes y sistemas", "about": "Linux, Unix, shell y sistemas operativos (en inglés)"},
    "se_superuser": {"name": "Super User", "group": "Redes y sistemas", "about": "Computadoras, Windows y sistemas operativos (en inglés)"},
    "se_dba": {"name": "Database Administrators", "group": "Bases de datos", "about": "SQL, diseño y administración de bases de datos (en inglés)"},
    "se_math": {"name": "Mathematics Stack Exchange", "group": "Matemática", "about": "Preguntas y respuestas de matemática (en inglés)"},
    "se_cs": {"name": "Computer Science", "group": "Programación", "about": "Algoritmos, complejidad y teoría de la computación (en inglés)"},
    "se_softeng": {"name": "Software Engineering", "group": "Programación", "about": "Diseño, arquitectura y buenas prácticas (en inglés)"},
    "se_codereview": {"name": "Code Review", "group": "Programación", "about": "Revisión de código con explicaciones (en inglés)"},
    "se_security": {"name": "Information Security", "group": "Redes y sistemas", "about": "Seguridad informática (en inglés)"},
    "se_electronics": {"name": "Electrical Engineering", "group": "Ciencias", "about": "Electrónica, circuitos y Arduino (en inglés)"},
    "se_physics": {"name": "Physics", "group": "Ciencias", "about": "Preguntas y respuestas de física (en inglés)"},
    "se_stats": {"name": "Cross Validated", "group": "Matemática", "about": "Estadística y probabilidad (en inglés)"},
    "se_datascience": {"name": "Data Science", "group": "Programación", "about": "Ciencia de datos y aprendizaje automático (en inglés)"},
    "serper": {"name": "Google (Serper)", "group": "Google", "about": "Resultados de Google (2.500 búsquedas gratis al registrarte)",
               "key": "serper_key", "env": "SERPER_API_KEY"},
    "serper_scholar": {"name": "Google Académico (Serper)", "group": "Google",
                       "about": "Artículos, tesis y libros académicos de Google Scholar", "keyname": "serper"},
    "serpapi": {"name": "Google (SerpApi)", "group": "Google", "about": "Resultados de Google (250 búsquedas gratis por mes)",
                "key": "serpapi_key", "env": "SERPAPI_API_KEY"},
    "serpapi_scholar": {"name": "Google Académico (SerpApi)", "group": "Google",
                        "about": "Artículos, tesis y libros académicos de Google Scholar", "keyname": "serpapi"},
    "google_books": {"name": "Google Libros", "group": "Google", "about": "Libros con su descripción (sin clave)",
                     "keyname": "google", "key_optional": True},
    "tavily": {"name": "Tavily", "group": "Web", "about": "Buscador web (1.000 búsquedas gratis por mes)",
               "key": "tavily_key", "env": "TAVILY_API_KEY"},
    "brave": {"name": "Brave Search", "group": "Web", "about": "Buscador web independiente",
              "key": "brave_key", "env": "BRAVE_API_KEY"},
    "claude_web": {"name": "Web (vía Claude)", "group": "Web", "about": "Búsqueda web de la API de Claude",
                   "needs": "anthropic"},
}
SO_SITES = {"so_es": "es.stackoverflow", "so_en": "stackoverflow", "se_net": "networkengineering",
            "se_serverfault": "serverfault", "se_unix": "unix", "se_superuser": "superuser", "se_dba": "dba",
            "se_math": "math", "se_cs": "cs", "se_softeng": "softwareengineering", "se_codereview": "codereview",
            "se_security": "security", "se_electronics": "electronics", "se_physics": "physics", "se_stats": "stats",
            "se_datascience": "datascience"}
SEARXNG_CATEGORY = {"searxng": "general", "searxng_it": "it", "searxng_science": "science"}


def key_name(site: str) -> str | None:
    """Nombre de la clave que usa un buscador (varios comparten la misma, por ejemplo Serper y Serper Académico)."""
    meta = PROVIDERS[site]
    return meta.get("keyname") or (site if meta.get("key") else None)


def _client(**headers) -> httpx.AsyncClient:
    return httpx.AsyncClient(headers={"User-Agent": USER_AGENT, **headers}, timeout=TIMEOUT, follow_redirects=True)


def _words(text: str, n: int = 35) -> str:
    w = (text or "").split()
    return " ".join(w[:n])


def _plain(fragment: str) -> str:
    """HTML corto (snippets, cuerpos de Stack Overflow) a texto plano."""
    text = re.sub(r"<(br|/p|/li|/pre|/h\d)\s*/?>", "\n", fragment or "", flags=re.I)
    text = re.sub(r"<[^>]+>", "", text)
    return html.unescape(text)


def _result(site: str, title: str, url: str, snippet: str, words: int = 0, ref: str | None = None,
            meta: str = "") -> dict:
    return {"site": site, "source_name": PROVIDERS[site]["name"], "lang": "es", "title": title.strip() or url,
            "snippet": _words(snippet), "words": words, "url": url, "ref": ref, "meta": meta, "kind": "provider"}


# --------------------------------------------------------------------------- #
# Categorías del buscador: qué fuentes conviene usar para cada área
# --------------------------------------------------------------------------- #
CATEGORIES: dict[str, dict] = {
    "programacion": {"label": "Programación", "hint": "programación",
                     "sites": ["searxng", "searxng_it", "so_es", "so_en", "mdn", "wikilibros", "wikipedia_es", "web", "serper", "serpapi",
                               "exa", "tavily", "brave", "se_cs", "se_softeng", "hackernews"]},
    "redes": {"label": "Redes", "hint": "redes de computadoras", "arxiv": ["cs.NI"],
              "sites": ["searxng", "searxng_it", "wikipedia_es", "wikilibros", "se_net", "se_serverfault", "se_security", "web",
                        "serper", "serpapi", "exa", "tavily", "brave", "arxiv", "google_books"]},
    "matematica": {"label": "Matemática", "hint": "matemática",
                   "sites": ["searxng", "searxng_science", "wikipedia_es", "wikilibros", "wikiversidad", "se_math", "se_stats", "web",
                             "serper", "serpapi", "exa", "tavily", "brave", "serper_scholar", "serpapi_scholar", "google_books"]},
    "bases_datos": {"label": "Bases de datos", "hint": "bases de datos", "arxiv": ["cs.DB"],
                    "sites": ["searxng", "searxng_it", "wikipedia_es", "wikilibros", "se_dba", "so_es", "web", "serper", "serpapi",
                              "exa", "tavily", "brave"]},
    "sistemas_operativos": {"label": "Sistemas operativos", "hint": "sistemas operativos", "arxiv": ["cs.OS"],
                            "sites": ["searxng", "searxng_it", "wikipedia_es", "wikilibros", "se_unix", "se_superuser", "web", "serper",
                                      "serpapi", "exa", "tavily", "brave", "google_books"]},
    "ciencias": {"label": "Ciencias y salud", "hint": "",
                 "sites": ["searxng", "searxng_science", "wikipedia_es", "wikiversidad", "openalex", "semanticscholar", "doaj",
                           "europepmc", "web", "serper", "serpapi", "serper_scholar", "serpapi_scholar", "exa", "tavily",
                           "se_physics", "se_electronics"]},
    "otros": {"label": "Otros", "hint": "",
              "sites": ["searxng", "wikipedia_es", "wikilibros", "wikiversidad", "web", "serper", "serpapi", "exa", "tavily", "brave",
                       "marginalia", "openalex", "doaj", "google_books", "openlibrary"]},
}


# --------------------------------------------------------------------------- #
# OpenAlex
# --------------------------------------------------------------------------- #
def _openalex_abstract(inv: dict | None) -> str:
    if not inv:
        return ""
    pos = [(i, w) for w, idxs in inv.items() for i in idxs]
    return " ".join(w for _, w in sorted(pos))


def _openalex_meta(w: dict) -> str:
    year = w.get("publication_year") or ""
    venue = (((w.get("primary_location") or {}).get("source") or {}).get("display_name")) or ""
    cites = w.get("cited_by_count")
    parts = [str(year), venue, f"{cites} citas" if cites else ""]
    return ", ".join(p for p in parts if p)


async def search_openalex(q: str, key: str | None) -> list[dict]:
    base = {"search": q, "per-page": 4, "filter": "has_abstract:true", "mailto": CONTACT,
            "select": "id,display_name,publication_year,abstract_inverted_index,primary_location,cited_by_count,language"}
    if key:
        base["api_key"] = key
    async with _client() as cli:
        es = cli.get("https://api.openalex.org/works", params={**base, "filter": "has_abstract:true,language:es", "per-page": 3})
        al = cli.get("https://api.openalex.org/works", params=base)
        responses = await asyncio.gather(es, al, return_exceptions=True)
    out, seen = [], set()
    for r in responses:
        if isinstance(r, Exception):
            continue
        if r.status_code == 429:
            raise SourceError("Se alcanzó el límite diario de OpenAlex. Con una clave gratuita (Ajustes) el límite es 10 veces mayor.")
        if r.status_code >= 400:
            continue
        for w in r.json().get("results", []):
            wid = (w.get("id") or "").rsplit("/", 1)[-1]
            if not wid or wid in seen:
                continue
            seen.add(wid)
            abstract = _openalex_abstract(w.get("abstract_inverted_index"))
            out.append(_result("openalex", w.get("display_name") or "", f"https://openalex.org/{wid}", abstract,
                               len(abstract.split()), wid, _openalex_meta(w)))
    return out


async def fetch_openalex(ref: str, key: str | None) -> dict:
    params = {"mailto": CONTACT}
    if key:
        params["api_key"] = key
    async with _client() as cli:
        r = await cli.get(f"https://api.openalex.org/works/{quote(ref)}", params=params)
    if r.status_code >= 400:
        raise SourceError("No se pudo descargar el artículo de OpenAlex.")
    w = r.json()
    title = w.get("display_name") or "Artículo"
    abstract = _openalex_abstract(w.get("abstract_inverted_index"))
    authors = ", ".join(a.get("author", {}).get("display_name", "") for a in (w.get("authorships") or [])[:4])
    sections = []
    if abstract:
        sections.append({"title": "Resumen", "text": abstract})
    # si el artículo es de acceso abierto y tiene versión web, se suma el texto completo
    oa = (w.get("open_access") or {}).get("oa_url") or ""
    url = (w.get("doi") or (w.get("primary_location") or {}).get("landing_page_url") or f"https://openalex.org/{ref}")
    if oa and not oa.lower().endswith(".pdf"):
        try:
            full = await sources.fetch_url(oa)
            sections += full["sections"][:20]
            url = full["url"]
        except SourceError:
            pass
    if not sections or sum(len(s["text"].split()) for s in sections) < 40:
        raise SourceError("Ese artículo no tiene resumen ni texto disponible para estudiar.")
    return {"title": title, "lang": w.get("language") or "es", "url": url, "revid": None, "timestamp": None,
            "source_name": f"OpenAlex{', ' + authors if authors else ''} ({w.get('publication_year') or 's/f'})",
            "license": None, "sections": sections}


# --------------------------------------------------------------------------- #
# arXiv
# --------------------------------------------------------------------------- #
ATOM = {"a": "http://www.w3.org/2005/Atom"}


def _arxiv_entries(xml_text: str) -> list[dict]:
    root = ET.fromstring(xml_text)
    out = []
    for e in root.findall("a:entry", ATOM):
        aid = (e.findtext("a:id", default="", namespaces=ATOM) or "").rsplit("/abs/", 1)[-1]
        title = " ".join((e.findtext("a:title", default="", namespaces=ATOM) or "").split())
        summary = " ".join((e.findtext("a:summary", default="", namespaces=ATOM) or "").split())
        year = (e.findtext("a:published", default="", namespaces=ATOM) or "")[:4]
        authors = [a.findtext("a:name", default="", namespaces=ATOM) for a in e.findall("a:author", ATOM)]
        if aid and summary:
            out.append({"id": aid, "title": title, "summary": summary, "year": year, "authors": authors})
    return out


async def search_arxiv(q: str, cats: list[str] | None = None) -> list[dict]:
    query = " AND ".join(f"all:{w}" for w in q.split()[:6])
    if cats:
        query = f"({' OR '.join(f'cat:{c}' for c in cats)}) AND {query}"
    async with _client() as cli:
        r = await cli.get("https://export.arxiv.org/api/query",
                          params={"search_query": query, "start": 0, "max_results": 6, "sortBy": "relevance"})
    r.raise_for_status()
    return [_result("arxiv", e["title"], f"https://arxiv.org/abs/{e['id']}", e["summary"], len(e["summary"].split()),
                    e["id"], f"{e['year']}, {', '.join(e['authors'][:2])}") for e in _arxiv_entries(r.text)]


async def fetch_arxiv(ref: str) -> dict:
    async with _client() as cli:
        r = await cli.get("https://export.arxiv.org/api/query", params={"id_list": ref})
    r.raise_for_status()
    entries = _arxiv_entries(r.text)
    if not entries:
        raise SourceError("No se encontró ese artículo en arXiv.")
    e = entries[0]
    sections = [{"title": "Resumen", "text": e["summary"]}]
    try:  # muchos artículos tienen versión HTML con el texto completo
        full = await sources.fetch_url(f"https://arxiv.org/html/{ref}")
        sections += full["sections"][:25]
    except SourceError:
        pass
    return {"title": e["title"], "lang": "en", "url": f"https://arxiv.org/abs/{ref}", "revid": None, "timestamp": None,
            "source_name": f"arXiv, {', '.join(e['authors'][:3])} ({e['year']})", "license": None, "sections": sections}


# --------------------------------------------------------------------------- #
# Europe PMC
# --------------------------------------------------------------------------- #
async def search_europepmc(q: str) -> list[dict]:
    async with _client() as cli:
        r = await cli.get("https://www.ebi.ac.uk/europepmc/webservices/rest/search",
                          params={"query": f"{q} AND HAS_ABSTRACT:Y", "format": "json", "pageSize": 6, "resultType": "core"})
    r.raise_for_status()
    out = []
    for it in r.json().get("resultList", {}).get("result", []):
        abstract = _plain(it.get("abstractText") or "")
        ref = f"{it.get('source')}:{it.get('id')}"
        url = f"https://europepmc.org/article/{it.get('source')}/{it.get('id')}"
        out.append(_result("europepmc", _plain(it.get("title") or ""), url, abstract, len(abstract.split()), ref,
                           f"{it.get('pubYear') or ''}, {(it.get('journalInfo') or {}).get('journal', {}).get('title', '')}".strip(", ")))
    return out


async def fetch_europepmc(ref: str) -> dict:
    src, _, pid = ref.partition(":")
    async with _client() as cli:
        r = await cli.get("https://www.ebi.ac.uk/europepmc/webservices/rest/search",
                          params={"query": f"EXT_ID:{pid} AND SRC:{src}", "format": "json", "resultType": "core"})
    r.raise_for_status()
    res = r.json().get("resultList", {}).get("result", [])
    if not res or not res[0].get("abstractText"):
        raise SourceError("Ese artículo no tiene resumen disponible.")
    it = res[0]
    return {"title": _plain(it.get("title") or "Artículo"), "lang": "en",
            "url": f"https://europepmc.org/article/{src}/{pid}", "revid": None, "timestamp": None,
            "source_name": f"Europe PMC ({it.get('pubYear') or 's/f'})", "license": None,
            "sections": [{"title": "Resumen", "text": _plain(it["abstractText"])}]}


# --------------------------------------------------------------------------- #
# Stack Overflow (API de Stack Exchange)
# --------------------------------------------------------------------------- #
async def search_stackoverflow(q: str, site_key: str) -> list[dict]:
    site = SO_SITES[site_key]
    async with _client() as cli:
        r = await cli.get("https://api.stackexchange.com/2.3/search/advanced",
                          params={"order": "desc", "sort": "relevance", "q": q, "site": site, "pagesize": 6,
                                  "answers": 1, "filter": "withbody"})
    r.raise_for_status()
    data = r.json()
    if data.get("error_id"):
        raise SourceError("Stack Overflow no respondió (límite diario alcanzado).")
    out = []
    for it in data.get("items", []):
        body = _plain(it.get("body", ""))
        meta = f"{it.get('score', 0)} votos, {it.get('answer_count', 0)} respuestas" + (", con respuesta aceptada" if it.get("is_answered") else "")
        out.append(_result(site_key, html.unescape(it.get("title", "")), it.get("link", ""), body,
                           len(body.split()), str(it.get("question_id")), meta))
    return out


async def fetch_stackoverflow(ref: str, site_key: str) -> dict:
    site = SO_SITES[site_key]
    async with _client() as cli:
        q, a = await asyncio.gather(
            cli.get(f"https://api.stackexchange.com/2.3/questions/{ref}", params={"site": site, "filter": "withbody"}),
            cli.get(f"https://api.stackexchange.com/2.3/questions/{ref}/answers",
                    params={"site": site, "filter": "withbody", "sort": "votes", "order": "desc", "pagesize": 3}))
    q.raise_for_status()
    a.raise_for_status()
    items = q.json().get("items", [])
    if not items:
        raise SourceError("No se encontró esa pregunta.")
    qi = items[0]
    sections = []
    _, qtext = sources.html_to_text(f"<article>{qi.get('body', '')}</article>")
    if qtext.strip():
        sections.append({"title": "La pregunta", "text": qtext})
    for n, ans in enumerate(a.json().get("items", []), 1):
        _, atext = sources.html_to_text(f"<article>{ans.get('body', '')}</article>")
        label = "Respuesta aceptada" if ans.get("is_accepted") else f"Respuesta {n}"
        if atext.strip():
            sections.append({"title": f"{label} ({ans.get('score', 0)} votos)", "text": atext})
    sections = [s for s in sections if len(s["text"].split()) >= 15]
    if not sections:
        raise SourceError("Esa pregunta no tiene suficiente texto para estudiar.")
    return {"title": html.unescape(qi.get("title", "Pregunta")), "lang": "es" if site_key == "so_es" else "en",
            "url": qi.get("link"), "revid": None, "timestamp": None,
            "source_name": PROVIDERS[site_key]["name"], "license": "CC BY-SA 4.0", "sections": sections}


# --------------------------------------------------------------------------- #
# Buscadores web con clave
# --------------------------------------------------------------------------- #
async def search_tavily(q: str, key: str) -> list[dict]:
    async with _client(Authorization=f"Bearer {key}") as cli:
        r = await cli.post("https://api.tavily.com/search", json={"query": q, "max_results": 7, "search_depth": "basic"})
    if r.status_code in (401, 403):
        raise SourceError("La clave de Tavily no es válida.")
    if r.status_code == 429 or r.status_code == 432:
        raise SourceError("Se terminaron las búsquedas de Tavily de este mes.")
    r.raise_for_status()
    return [_result("tavily", it.get("title", ""), it.get("url", ""), it.get("content", ""))
            for it in r.json().get("results", []) if it.get("url")]


async def search_brave(q: str, key: str) -> list[dict]:
    async with _client(**{"X-Subscription-Token": key, "Accept": "application/json"}) as cli:
        r = await cli.get("https://api.search.brave.com/res/v1/web/search", params={"q": q, "count": 7})
    if r.status_code in (401, 403, 422):
        raise SourceError("La clave de Brave Search no es válida o no tiene un plan activo.")
    if r.status_code == 429:
        raise SourceError("Se alcanzó el límite de Brave Search.")
    r.raise_for_status()
    return [_result("brave", _plain(it.get("title", "")), it.get("url", ""), _plain(it.get("description", "")))
            for it in (r.json().get("web") or {}).get("results", []) if it.get("url")]


# --------------------------------------------------------------------------- #
# Google: Serper, SerpApi y Google Libros
# --------------------------------------------------------------------------- #
def _serper_error(r: httpx.Response) -> None:
    if r.status_code in (401, 403):
        raise SourceError("La clave de Serper no es válida.")
    if r.status_code in (400, 402) and "credit" in r.text.lower():
        raise SourceError("Se terminaron los créditos de Serper.")
    if r.status_code == 429:
        raise SourceError("Se alcanzó el límite de Serper; probá en un momento.")
    r.raise_for_status()


async def search_serper(q: str, key: str, scholar: bool = False) -> list[dict]:
    site = "serper_scholar" if scholar else "serper"
    body = {"q": q, "hl": "es"} if scholar else {"q": q, "gl": "ar", "hl": "es", "num": 8}
    async with _client(**{"X-API-KEY": key, "Content-Type": "application/json"}) as cli:
        r = await cli.post(f"https://google.serper.dev/{'scholar' if scholar else 'search'}", json=body)
    _serper_error(r)
    out = []
    for it in r.json().get("organic", []):
        url = it.get("link") or it.get("pdfUrl")
        if not url:
            continue
        meta = ", ".join(str(x) for x in (it.get("publicationInfo"), it.get("year"),
                                            f"{it['citedBy']} citas" if it.get("citedBy") else None) if x) if scholar else (it.get("date") or "")
        out.append(_result(site, it.get("title", ""), url, it.get("snippet", ""), meta=meta))
    return out


def _serpapi_error(r: httpx.Response) -> None:
    try:
        err = r.json().get("error")
    except ValueError:
        err = None
    if r.status_code in (401, 403) or (err and "invalid api key" in err.lower()):
        raise SourceError("La clave de SerpApi no es válida.")
    if r.status_code == 429 or (err and ("run out" in err.lower() or "limit" in err.lower())):
        raise SourceError("Se terminaron las búsquedas de SerpApi de este mes.")
    if err and "hasn't returned any results" in err.lower():
        return
    if err:
        raise SourceError(f"SerpApi: {err}")
    r.raise_for_status()


async def search_serpapi(q: str, key: str, scholar: bool = False) -> list[dict]:
    site = "serpapi_scholar" if scholar else "serpapi"
    params = {"engine": "google_scholar" if scholar else "google", "q": q, "hl": "es", "api_key": key}
    if not scholar:
        params.update({"gl": "ar", "google_domain": "google.com.ar", "num": 8})
    async with _client() as cli:
        r = await cli.get("https://serpapi.com/search.json", params=params)
    _serpapi_error(r)
    out = []
    for it in r.json().get("organic_results", []):
        url = it.get("link")
        if not url:
            continue
        meta = ""
        if scholar:
            pub = (it.get("publication_info") or {}).get("summary") or ""
            cites = ((it.get("inline_links") or {}).get("cited_by") or {}).get("total")
            meta = ", ".join(x for x in (pub, f"{cites} citas" if cites else "") if x)
        out.append(_result(site, it.get("title", ""), url, it.get("snippet", ""), meta=meta or it.get("date", "")))
    return out


async def search_google_books(q: str, key: str | None = None) -> list[dict]:
    params = {"q": q, "maxResults": 8, "printType": "books", "langRestrict": "es", "orderBy": "relevance"}
    if key:
        params["key"] = key
    async with _client() as cli:
        r = await cli.get("https://www.googleapis.com/books/v1/volumes", params=params)
        data = r.json() if r.status_code < 400 else {}
        if not data.get("items"):  # sin resultados en español: cualquier idioma
            params.pop("langRestrict")
            r = await cli.get("https://www.googleapis.com/books/v1/volumes", params=params)
            data = r.json() if r.status_code < 400 else {}
    if r.status_code == 429:
        raise SourceError("Google Libros alcanzó su límite diario; probá más tarde.")
    out = []
    for it in data.get("items", []):
        v = it.get("volumeInfo") or {}
        desc = _plain(v.get("description") or (it.get("searchInfo") or {}).get("textSnippet") or "")
        if len(desc.split()) < 25:
            continue  # sin descripción no hay de dónde sacar preguntas
        meta = ", ".join(x for x in (", ".join(v.get("authors", [])[:2]), (v.get("publishedDate") or "")[:4],
                                     v.get("publisher") or "") if x)
        title = v.get("title", "") + (f": {v['subtitle']}" if v.get("subtitle") else "")
        out.append(_result("google_books", title, v.get("infoLink") or f"https://books.google.com/books?id={it.get('id')}",
                           desc, len(desc.split()), it.get("id"), meta))
    return out


async def fetch_google_books(ref: str, key: str | None = None) -> dict:
    params = {"key": key} if key else {}
    async with _client() as cli:
        r = await cli.get(f"https://www.googleapis.com/books/v1/volumes/{quote(ref)}", params=params)
    if r.status_code >= 400:
        raise SourceError("No se pudo abrir ese libro en Google Libros.")
    v = r.json().get("volumeInfo") or {}
    _, desc = sources.html_to_text(f"<article>{v.get('description') or ''}</article>")
    if len(desc.split()) < 40:
        raise SourceError("Ese libro tiene una descripción muy corta para estudiar. Abrí su vista previa en Google Libros.")
    authors = ", ".join(v.get("authors", [])[:3])
    sections = [{"title": "De qué trata el libro", "text": desc}]
    cats = v.get("categories") or []
    if cats:
        sections.append({"title": "Temas", "text": "El libro trata sobre " + ", ".join(cats) + "."})
    return {"title": v.get("title") or "Libro", "lang": v.get("language") or "es",
            "url": v.get("infoLink") or v.get("previewLink"), "revid": None, "timestamp": None,
            "source_name": f"Google Libros{', ' + authors if authors else ''} ({(v.get('publishedDate') or 's/f')[:4]})",
            "license": None, "sections": sections[:1] if len(sections[0]["text"].split()) > 80 else sections}


# --------------------------------------------------------------------------- #
# Toda la web: SearXNG (metabuscador propio), Marginalia, Hacker News, Exa
# --------------------------------------------------------------------------- #
async def search_searxng(q: str, base: str, category: str = "general") -> list[dict]:
    site = {v: k for k, v in SEARXNG_CATEGORY.items()}[category]
    async with _client(Accept="application/json") as cli:
        r = await cli.get(base.rstrip("/") + "/search",
                          params={"q": q, "format": "json", "language": "es", "categories": category, "safesearch": 1})
    if r.status_code == 403:
        raise SourceError("SearXNG no tiene habilitado el formato JSON (revisá searxng/settings.yml).")
    r.raise_for_status()
    out, seen = [], set()
    for it in r.json().get("results", []):
        url = it.get("url") or ""
        if not url.startswith(("http://", "https://")) or url in seen:
            continue
        seen.add(url)
        engines = it.get("engines") or ([it["engine"]] if it.get("engine") else [])
        meta = "vía " + ", ".join(engines[:4]) if engines else ""
        out.append(_result(site, _plain(it.get("title", "")), url, _plain(it.get("content", "")), meta=meta))
        if len(out) >= 10:
            break
    return out


async def search_marginalia(q: str) -> list[dict]:
    async with _client() as cli:
        r = await cli.get(f"https://api.marginalia.nu/public/search/{quote(q)}", params={"count": 8, "index": 0})
    if r.status_code == 503:
        raise SourceError("Marginalia está saturado (límite compartido); probá en un rato.")
    r.raise_for_status()
    return [_result("marginalia", it.get("title", ""), it.get("url", ""), it.get("description", ""))
            for it in r.json().get("results", []) if it.get("url")]


async def search_hackernews(q: str) -> list[dict]:
    async with _client() as cli:
        r = await cli.get("https://hn.algolia.com/api/v1/search",
                          params={"query": q, "tags": "story", "hitsPerPage": 10})
    r.raise_for_status()
    out = []
    for it in r.json().get("hits", []):
        url = it.get("url")
        if not url:
            continue
        meta = f"{it.get('points') or 0} puntos, {it.get('num_comments') or 0} comentarios, {(it.get('created_at') or '')[:4]}"
        out.append(_result("hackernews", it.get("title", ""), url, "", meta=meta))
    return out[:8]


async def search_exa(q: str, key: str) -> list[dict]:
    async with _client(**{"x-api-key": key, "Content-Type": "application/json"}) as cli:
        r = await cli.post("https://api.exa.ai/search", json={
            "query": q, "numResults": 8, "type": "auto", "contents": {"text": {"maxCharacters": 400}}})
    if r.status_code in (401, 403):
        raise SourceError("La clave de Exa no es válida.")
    if r.status_code in (402, 429):
        raise SourceError("Se terminaron los créditos de Exa de este mes.")
    r.raise_for_status()
    return [_result("exa", it.get("title") or "", it.get("url", ""), it.get("text") or it.get("summary") or "",
                    meta=(it.get("publishedDate") or "")[:10]) for it in r.json().get("results", []) if it.get("url")]


async def search_mdn(q: str) -> list[dict]:
    async with _client() as cli:
        r = await cli.get("https://developer.mozilla.org/api/v1/search", params={"q": q, "locale": "es", "size": 8})
        data = r.json() if r.status_code < 400 else {}
        if not data.get("documents"):
            r = await cli.get("https://developer.mozilla.org/api/v1/search", params={"q": q, "locale": "en-US", "size": 8})
            data = r.json() if r.status_code < 400 else {}
    return [_result("mdn", d.get("title", ""), "https://developer.mozilla.org" + d["mdn_url"], d.get("summary", ""),
                    meta="español" if d.get("locale", "").startswith("es") else "inglés")
            for d in data.get("documents", []) if d.get("mdn_url", "").startswith("/")]


# --------------------------------------------------------------------------- #
# Académicos sin clave: Semantic Scholar, Crossref, DOAJ; libros: Open Library
# --------------------------------------------------------------------------- #
S2_FIELDS = "title,abstract,year,venue,citationCount,url,authors,openAccessPdf"


async def search_semanticscholar(q: str) -> list[dict]:
    async with _client() as cli:
        r = await cli.get("https://api.semanticscholar.org/graph/v1/paper/search",
                          params={"query": q, "limit": 8, "fields": S2_FIELDS})
    if r.status_code == 429:
        raise SourceError("Semantic Scholar está saturado (límite compartido); probá en un momento.")
    r.raise_for_status()
    out = []
    for p in r.json().get("data") or []:
        abstract = p.get("abstract") or ""
        if not abstract:
            continue
        meta = ", ".join(x for x in (str(p.get("year") or ""), p.get("venue") or "",
                                     f"{p['citationCount']} citas" if p.get("citationCount") else "") if x)
        out.append(_result("semanticscholar", p.get("title", ""), p.get("url") or "", abstract, len(abstract.split()),
                           p.get("paperId"), meta))
    return out


async def fetch_semanticscholar(ref: str) -> dict:
    async with _client() as cli:
        r = await cli.get(f"https://api.semanticscholar.org/graph/v1/paper/{quote(ref)}", params={"fields": S2_FIELDS})
    if r.status_code >= 400:
        raise SourceError("No se pudo descargar el artículo de Semantic Scholar.")
    p = r.json()
    if not p.get("abstract"):
        raise SourceError("Ese artículo no tiene resumen disponible.")
    authors = ", ".join(a.get("name", "") for a in (p.get("authors") or [])[:3])
    return {"title": p.get("title") or "Artículo", "lang": "en", "url": p.get("url"), "revid": None, "timestamp": None,
            "source_name": f"Semantic Scholar, {authors} ({p.get('year') or 's/f'})", "license": None,
            "sections": [{"title": "Resumen", "text": p["abstract"]}]}


def _jats(text: str) -> str:
    """Los resúmenes de Crossref vienen en XML JATS."""
    text = re.sub(r"<jats:title>.*?</jats:title>", "", text or "", flags=re.S)
    return " ".join(_plain(text).split())


async def search_crossref(q: str) -> list[dict]:
    async with _client() as cli:
        r = await cli.get("https://api.crossref.org/works", params={
            "query": q, "rows": 8, "filter": "has-abstract:true", "mailto": CONTACT,
            "select": "DOI,title,abstract,container-title,issued,author,URL,language"})
    r.raise_for_status()
    out = []
    for it in (r.json().get("message") or {}).get("items", []):
        abstract = _jats(it.get("abstract", ""))
        title = (it.get("title") or [""])[0]
        if not abstract or not title:
            continue
        year = (((it.get("issued") or {}).get("date-parts") or [[None]])[0] or [None])[0]
        meta = ", ".join(x for x in (str(year or ""), (it.get("container-title") or [""])[0]) if x)
        out.append(_result("crossref", _plain(title), it.get("URL") or f"https://doi.org/{it['DOI']}", abstract,
                           len(abstract.split()), it.get("DOI"), meta))
    return out


async def fetch_crossref(ref: str) -> dict:
    async with _client() as cli:
        r = await cli.get(f"https://api.crossref.org/works/{quote(ref, safe='/')}", params={"mailto": CONTACT})
    if r.status_code >= 400:
        raise SourceError("No se pudo descargar el artículo de Crossref.")
    it = r.json().get("message") or {}
    abstract = _jats(it.get("abstract", ""))
    if len(abstract.split()) < 30:
        raise SourceError("Ese artículo no tiene un resumen suficiente para estudiar.")
    authors = ", ".join(f"{a.get('given', '')} {a.get('family', '')}".strip() for a in (it.get("author") or [])[:3])
    year = (((it.get("issued") or {}).get("date-parts") or [[None]])[0] or [None])[0]
    return {"title": _plain((it.get("title") or ["Artículo"])[0]), "lang": it.get("language") or "es",
            "url": it.get("URL") or f"https://doi.org/{ref}", "revid": None, "timestamp": None,
            "source_name": f"Crossref, {authors} ({year or 's/f'})", "license": None,
            "sections": [{"title": "Resumen", "text": abstract}]}


async def search_doaj(q: str) -> list[dict]:
    async with _client() as cli:
        r = await cli.get(f"https://doaj.org/api/search/articles/{quote(q)}", params={"pageSize": 8, "page": 1})
    r.raise_for_status()
    out = []
    for it in r.json().get("results", []):
        b = it.get("bibjson") or {}
        abstract = _plain(b.get("abstract") or "")
        if len(abstract.split()) < 25:
            continue
        link = next((ln.get("url") for ln in b.get("link") or [] if ln.get("url")), f"https://doaj.org/article/{it.get('id')}")
        meta = ", ".join(x for x in (str(b.get("year") or ""), (b.get("journal") or {}).get("title") or "") if x)
        out.append(_result("doaj", _plain(b.get("title", "")), link, abstract, len(abstract.split()), it.get("id"), meta))
    return out


async def fetch_doaj(ref: str) -> dict:
    async with _client() as cli:
        r = await cli.get(f"https://doaj.org/api/articles/{quote(ref)}")
    if r.status_code >= 400:
        raise SourceError("No se pudo descargar el artículo de DOAJ.")
    b = r.json().get("bibjson") or {}
    abstract = _plain(b.get("abstract") or "")
    link = next((ln.get("url") for ln in b.get("link") or [] if ln.get("url")), f"https://doaj.org/article/{ref}")
    sections = [{"title": "Resumen", "text": abstract}] if abstract else []
    try:  # los artículos de acceso abierto suelen tener el texto completo en la web de la revista
        if link and not link.lower().endswith(".pdf"):
            full = await sources.fetch_url(link)
            sections += full["sections"][:20]
    except SourceError:
        pass
    if not sections:
        raise SourceError("Ese artículo no tiene resumen disponible.")
    authors = ", ".join(a.get("name", "") for a in (b.get("author") or [])[:3])
    return {"title": _plain(b.get("title") or "Artículo"), "lang": "es", "url": link, "revid": None, "timestamp": None,
            "source_name": f"DOAJ, {authors} ({b.get('year') or 's/f'})", "license": "Acceso abierto", "sections": sections}


async def search_openlibrary(q: str) -> list[dict]:
    async with _client() as cli:
        r = await cli.get("https://openlibrary.org/search.json", params={
            "q": q, "limit": 10, "fields": "key,title,author_name,first_publish_year,subject"})
    r.raise_for_status()
    out = []
    for d in r.json().get("docs", []):
        if not d.get("key", "").startswith("/works/"):
            continue
        meta = ", ".join(x for x in (", ".join((d.get("author_name") or [])[:2]), str(d.get("first_publish_year") or "")) if x)
        snippet = "Temas: " + ", ".join((d.get("subject") or [])[:8]) if d.get("subject") else ""
        out.append(_result("openlibrary", d.get("title", ""), f"https://openlibrary.org{d['key']}", snippet,
                           ref=d["key"], meta=meta))
    return out[:8]


async def fetch_openlibrary(ref: str) -> dict:
    if not re.fullmatch(r"/works/OL\d+W", ref or ""):
        raise SourceError("Referencia de Open Library no válida.")
    async with _client() as cli:
        r = await cli.get(f"https://openlibrary.org{ref}.json")
    if r.status_code >= 400:
        raise SourceError("No se pudo abrir ese libro en Open Library.")
    w = r.json()
    desc = w.get("description")
    desc = desc.get("value") if isinstance(desc, dict) else (desc or "")
    desc = re.sub(r"\(\[source\]\[\d+\]\)|\[\d+\]:.*$", "", desc, flags=re.M).strip()
    if len(desc.split()) < 40:
        raise SourceError("Ese libro no tiene una descripción suficiente para estudiar.")
    sections = [{"title": "De qué trata el libro", "text": desc}]
    if w.get("subjects"):
        sections.append({"title": "Temas", "text": "El libro trata sobre " + ", ".join(w["subjects"][:12]) + "."})
    return {"title": w.get("title") or "Libro", "lang": "es", "url": f"https://openlibrary.org{ref}", "revid": None,
            "timestamp": None, "source_name": "Open Library", "license": None, "sections": sections}


async def search_claude_web(q: str, key: str, model: str) -> list[dict]:
    headers = {"x-api-key": key, "anthropic-version": "2023-06-01", "content-type": "application/json"}
    body = {"model": model, "max_tokens": 1024,
            "tools": [{"type": "web_search_20250305", "name": "web_search", "max_uses": 2}],
            "messages": [{"role": "user", "content":
                          f"Buscá páginas web con buena información para estudiar «{q}» (apuntes universitarios, "
                          "documentación oficial, artículos). Respondé con una oración."}]}
    async with httpx.AsyncClient(timeout=httpx.Timeout(90.0, connect=10.0)) as cli:
        r = await cli.post("https://api.anthropic.com/v1/messages", headers=headers, json=body)
    if r.status_code == 400 and "web search" in r.text.lower():
        raise SourceError("La búsqueda web no está habilitada en tu organización de la Console de Claude.")
    r.raise_for_status()
    out, seen = [], set()
    for block in r.json().get("content", []):
        if block.get("type") != "web_search_tool_result" or not isinstance(block.get("content"), list):
            continue
        for res in block["content"]:
            url = res.get("url")
            if res.get("type") == "web_search_result" and url and url not in seen:
                seen.add(url)
                out.append(_result("claude_web", res.get("title", ""), url, "", meta=res.get("page_age") or ""))
    return out


async def search(site: str, q: str, keys: dict, hint: str = "", arxiv_cats: list[str] | None = None) -> list[dict]:
    """Busca en un proveedor. `hint` agrega contexto de la categoría a los buscadores web generales."""
    web_q = f"{q} {hint}".strip() if hint and hint.lower() not in q.lower() else q
    if site in SEARXNG_CATEGORY:
        return await search_searxng(web_q if site == "searxng" else q, keys["searxng"], SEARXNG_CATEGORY[site])
    if site == "marginalia":
        return await search_marginalia(q)
    if site == "hackernews":
        return await search_hackernews(q)
    if site == "exa":
        return await search_exa(web_q, keys["exa"])
    if site == "mdn":
        return await search_mdn(q)
    if site == "semanticscholar":
        return await search_semanticscholar(q)
    if site == "crossref":
        return await search_crossref(q)
    if site == "doaj":
        return await search_doaj(q)
    if site == "openlibrary":
        return await search_openlibrary(q)
    if site == "openalex":
        return await search_openalex(q, keys.get("openalex"))
    if site == "arxiv":
        return await search_arxiv(q, arxiv_cats)
    if site == "europepmc":
        return await search_europepmc(q)
    if site in SO_SITES:
        return await search_stackoverflow(q, site)
    if site in ("serper", "serper_scholar"):
        return await search_serper(web_q if site == "serper" else q, keys["serper"], scholar=site == "serper_scholar")
    if site in ("serpapi", "serpapi_scholar"):
        return await search_serpapi(web_q if site == "serpapi" else q, keys["serpapi"], scholar=site == "serpapi_scholar")
    if site == "google_books":
        return await search_google_books(q, keys.get("google"))
    if site == "tavily":
        return await search_tavily(web_q, keys["tavily"])
    if site == "brave":
        return await search_brave(web_q, keys["brave"])
    if site == "claude_web":
        return await search_claude_web(web_q, keys["anthropic"], keys.get("anthropic_model") or "claude-haiku-5-5")
    raise SourceError("Buscador desconocido.")


async def fetch(site: str, ref: str | None, url: str | None, keys: dict) -> dict:
    """Descarga un resultado como fuente de estudio."""
    try:
        if site == "openalex" and ref:
            return await fetch_openalex(ref, keys.get("openalex"))
        if site == "arxiv" and ref:
            return await fetch_arxiv(ref)
        if site == "europepmc" and ref:
            return await fetch_europepmc(ref)
        if site in SO_SITES and ref:
            return await fetch_stackoverflow(ref, site)
        if site == "google_books" and ref:
            return await fetch_google_books(ref, keys.get("google"))
        if site == "semanticscholar" and ref:
            return await fetch_semanticscholar(ref)
        if site == "crossref" and ref:
            return await fetch_crossref(ref)
        if site == "doaj" and ref:
            return await fetch_doaj(ref)
        if site == "openlibrary" and ref:
            return await fetch_openlibrary(ref)
    except httpx.HTTPError as e:
        raise SourceError(f"No se pudo descargar de {PROVIDERS[site]['name']} ({type(e).__name__}).") from e
    if url:
        return await sources.fetch_url(url)
    raise SourceError("Fuente incompleta.")
