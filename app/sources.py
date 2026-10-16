"""Obtención de información desde fuentes confiables.

Fuentes integradas (todas con la API oficial de MediaWiki y licencia libre):
  - Wikipedia en español e inglés, y Wikipedia en inglés simple (explicaciones más sencillas)
  - Wikilibros: libros de texto escritos de forma colaborativa
  - Wikiversidad: cursos y material didáctico

Además se puede importar cualquier página web (por ejemplo, documentación técnica o
artículos académicos) a partir de su URL, y los apuntes propios del usuario.

Cada sección guarda la URL (y en los wikis, la revisión exacta), de modo que cada
pregunta se puede rastrear hasta el texto del que salió.
"""
from __future__ import annotations

import asyncio
import html
import ipaddress
import re
import socket
import unicodedata
from html.parser import HTMLParser
from urllib.parse import quote, unquote, urljoin, urlparse

import httpx

USER_AGENT = "EstudioDunlosky/1.1 (aplicacion educativa de codigo abierto)"
TIMEOUT = httpx.Timeout(20.0, connect=10.0)
MAX_PAGE_BYTES = 4_000_000

SITES: dict[str, dict] = {
    "wikipedia_es": {"host": "es.wikipedia.org", "name": "Wikipedia (es)", "lang": "es",
                     "about": "Enciclopedia general"},
    "wikilibros": {"host": "es.wikibooks.org", "name": "Wikilibros (es)", "lang": "es",
                   "about": "Libros de texto y manuales"},
    "wikiversidad": {"host": "es.wikiversity.org", "name": "Wikiversidad (es)", "lang": "es",
                     "about": "Cursos y material didáctico"},
    "wikipedia_en": {"host": "en.wikipedia.org", "name": "Wikipedia (en)", "lang": "en",
                     "about": "La enciclopedia más completa, en inglés"},
    "simple_en": {"host": "simple.wikipedia.org", "name": "Simple English Wikipedia", "lang": "en",
                  "about": "Explicaciones en inglés sencillo"},
    "wikibooks_en": {"host": "en.wikibooks.org", "name": "Wikibooks (en)", "lang": "en",
                     "about": "Libros de texto en inglés"},
}
DEFAULT_SEARCH = ["wikipedia_es", "wikilibros", "wikiversidad"]
LANG_TO_SITE = {"es": "wikipedia_es", "en": "wikipedia_en"}

SKIP_SECTIONS = {
    "referencias", "notas", "bibliografia", "enlaces externos", "vease tambien", "fuentes",
    "lecturas adicionales", "lectura adicional", "notas y referencias", "otras lecturas", "galeria",
    "references", "notes", "see also", "external links", "further reading", "bibliography",
    "sources", "citations", "footnotes", "gallery", "filmografia", "discografia", "enlaces",
    "referencias y notas", "contenidos", "indice", "tabla de contenidos", "navegacion",
}


class SourceError(Exception):
    pass


def _strip(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", s.lower()) if unicodedata.category(c) != "Mn").strip()


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
    text = re.sub(r"\[\d+\]|\[cita requerida\]|\[citation needed\]|\[editar\]|\[edit\]", "", text)
    text = re.sub(r"\(\s*[;,]?\s*\)", "", text)          # paréntesis vacíos
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r" ([,.;:])", r"\1", text)
    return text


def parse_sections(extract: str, page_title: str, min_words: int = 25) -> list[dict]:
    """Convierte texto plano con encabezados '== X ==' en secciones."""
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
            current = {"title": title, "level": level, "lines": []}
            if _strip(title) in SKIP_SECTIONS:
                skipping_level = level
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
        if len(body.split()) < min_words:
            continue
        out.append({"title": s["title"], "text": body})
    if not out:
        raise SourceError(f"«{page_title}» no tiene suficiente texto para estudiar.")
    return out


# --------------------------------------------------------------------------- #
# HTML → texto con secciones (para páginas web y como respaldo en los wikis)
# --------------------------------------------------------------------------- #
class _TextExtractor(HTMLParser):
    SKIP = {"script", "style", "noscript", "nav", "header", "footer", "aside", "form", "button",
            "svg", "figure", "figcaption", "table", "sup", "iframe", "select", "template"}
    BLOCK = {"p", "li", "dd", "dt", "blockquote", "pre"}
    HEAD = {"h1", "h2", "h3", "h4"}
    SKIP_CLASSES = re.compile(r"\b(navbox|reflist|reference|mw-editsection|toc|infobox|metadata|noprint|"
                              r"sidebar|breadcrumb|cookie|advert|share|comments?|footer|menu)\b", re.I)

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.lines: list[str] = []
        self.buf: list[str] = []
        self.skip_depth = 0
        self.stack: list[tuple[str, bool]] = []
        self.mode = None
        self.title = ""
        self.in_title = False

    def handle_starttag(self, tag, attrs):
        if tag in ("br", "img", "hr", "meta", "link", "input", "wbr"):
            if tag == "br" and not self.skip_depth:
                self.buf.append(" ")
            return
        a = dict(attrs)
        skip = tag in self.SKIP or bool(self.SKIP_CLASSES.search(a.get("class", "") or "")) \
            or a.get("role") in ("navigation", "banner", "contentinfo") or a.get("aria-hidden") == "true"
        self.stack.append((tag, skip))
        if skip:
            self.skip_depth += 1
        if tag == "title":
            self.in_title = True
        if self.skip_depth:
            return
        if tag in self.HEAD or tag in self.BLOCK:
            self._flush()
            self.mode = tag

    def handle_endtag(self, tag):
        if tag == "title":
            self.in_title = False
        # cerrar hasta encontrar la etiqueta (HTML real no siempre está balanceado)
        for i in range(len(self.stack) - 1, -1, -1):
            if self.stack[i][0] == tag:
                for t, sk in self.stack[i:]:
                    if sk:
                        self.skip_depth -= 1
                del self.stack[i:]
                break
        if not self.skip_depth and (tag in self.HEAD or tag in self.BLOCK):
            self._flush()

    def handle_data(self, data):
        if self.in_title:
            self.title += data
        if self.skip_depth or self.mode is None:
            return
        self.buf.append(data)

    def _flush(self):
        text = re.sub(r"\s+", " ", "".join(self.buf)).strip()
        self.buf = []
        if not text:
            self.mode = None
            return
        if self.mode in self.HEAD:
            level = {"h1": 1, "h2": 2, "h3": 3, "h4": 4}[self.mode]
            if level >= 2:
                self.lines.append(f"{'=' * level} {text} {'=' * level}")
            elif not self.title:
                self.title = text
        elif self.mode in self.BLOCK:
            # ítems muy cortos (menús, etiquetas) no aportan
            if len(text.split()) >= 4 or self.mode == "p":
                if self.mode == "li" and not re.search(r"[.:;!?]$", text):
                    text += "."
                self.lines.append(text)
        self.mode = None


def _main_html(doc: str) -> str:
    """Si la página tiene <article> o <main>, nos quedamos con eso."""
    for tag in ("article", "main"):
        m = re.search(rf"<{tag}\b[^>]*>(.*)</{tag}>", doc, re.S | re.I)
        if m and len(m.group(1)) > 1500:
            return m.group(1)
    m = re.search(r'<div[^>]+(?:id|class)="[^"]*(?:mw-parser-output|content|post|entry)[^"]*"[^>]*>(.*)', doc, re.S | re.I)
    return m.group(1) if m else doc


def html_to_text(doc: str) -> tuple[str, str]:
    title_m = re.search(r"<title[^>]*>(.*?)</title>", doc, re.S | re.I)
    page_title = html.unescape(re.sub(r"\s+", " ", title_m.group(1))).strip() if title_m else ""
    parser = _TextExtractor()
    parser.feed(_main_html(doc))
    parser.close()
    parser._flush()
    text = "\n".join(parser.lines)
    # el título suele traer " - Sitio": nos quedamos con la parte principal
    page_title = re.split(r"\s+[|\-–—]\s+", page_title)[0].strip() or parser.title.strip()
    return page_title, clean_extract(text)


# --------------------------------------------------------------------------- #
# Wikis (MediaWiki)
# --------------------------------------------------------------------------- #
def _api(site: str) -> str:
    if site not in SITES:
        raise SourceError("Fuente desconocida.")
    return f"https://{SITES[site]['host']}/w/api.php"


def _page_url(site: str, title: str) -> str:
    return f"https://{SITES[site]['host']}/wiki/{quote(title.replace(' ', '_'))}"


async def _get_json(cli: httpx.AsyncClient, url: str, params: dict) -> dict:
    r = await cli.get(url, params=params)
    r.raise_for_status()
    return r.json()


async def search_site(site: str, query: str, limit: int = 6) -> list[dict]:
    params = {"action": "query", "list": "search", "srsearch": query, "srlimit": limit,
              "format": "json", "utf8": 1, "srprop": "snippet|wordcount", "srnamespace": 0}
    try:
        async with httpx.AsyncClient(headers={"User-Agent": USER_AGENT}, timeout=TIMEOUT) as cli:
            data = await _get_json(cli, _api(site), params)
    except httpx.HTTPError as e:
        raise SourceError(f"No se pudo conectar con {SITES[site]['name']} ({type(e).__name__}).") from e
    out = []
    for it in data.get("query", {}).get("search", []):
        if it.get("wordcount", 0) < 60:
            continue
        out.append({
            "site": site, "source_name": SITES[site]["name"], "lang": SITES[site]["lang"],
            "title": it["title"], "snippet": _clean_snippet(it.get("snippet", "")),
            "words": it.get("wordcount", 0), "url": _page_url(site, it["title"]),
        })
    return out


async def search_many(query: str, sites: list[str]) -> dict:
    """Busca en varias fuentes a la vez. Devuelve resultados por fuente y errores por fuente."""
    sites = [s for s in sites if s in SITES] or DEFAULT_SEARCH
    tasks = [search_site(s, query) for s in sites]
    res = await asyncio.gather(*tasks, return_exceptions=True)
    groups, errors = [], []
    for site, r in zip(sites, res):
        if isinstance(r, Exception):
            errors.append({"site": site, "name": SITES[site]["name"], "message": str(r)})
        else:
            groups.append({"site": site, "name": SITES[site]["name"], "about": SITES[site]["about"], "results": r})
    if errors and not groups:
        raise SourceError(errors[0]["message"] + " Revisá la conexión a internet del equipo.")
    return {"groups": groups, "errors": errors}


async def fetch_wiki(title: str, site: str = "wikipedia_es") -> dict:
    api = _api(site)
    meta = SITES[site]
    try:
        async with httpx.AsyncClient(headers={"User-Agent": USER_AGENT}, timeout=TIMEOUT) as cli:
            data = await _get_json(cli, api, {
                "action": "query", "prop": "extracts|info|revisions", "explaintext": 1,
                "exsectionformat": "wiki", "titles": title, "redirects": 1, "inprop": "url",
                "rvprop": "ids|timestamp", "format": "json", "utf8": 1, "formatversion": 2,
            })
            pages = data.get("query", {}).get("pages", [])
            if not pages or pages[0].get("missing"):
                raise SourceError(f"No existe «{title}» en {meta['name']}.")
            page = pages[0]
            extract = page.get("extract")
            if not extract:
                # Respaldo: si el wiki no ofrece extractos de texto, se convierte el HTML renderizado
                parsed = await _get_json(cli, api, {"action": "parse", "page": page["title"], "prop": "text",
                                                    "redirects": 1, "format": "json", "formatversion": 2,
                                                    "disableeditsection": 1})
                _, extract = html_to_text(parsed.get("parse", {}).get("text", ""))
    except httpx.HTTPError as e:
        raise SourceError(f"No se pudo descargar «{title}» de {meta['name']} ({type(e).__name__}).") from e

    rev = (page.get("revisions") or [{}])[0]
    sections = parse_sections(clean_extract(extract), page["title"])
    return {
        "title": page["title"], "lang": meta["lang"], "url": page.get("fullurl", _page_url(site, page["title"])),
        "revid": rev.get("revid"), "timestamp": rev.get("timestamp"), "source_name": meta["name"],
        "license": "CC BY-SA 4.0", "sections": sections,
    }


# compatibilidad con la versión anterior
async def search_wikipedia(query: str, lang: str = "es", limit: int = 8) -> list[dict]:
    return await search_site(LANG_TO_SITE.get(lang, "wikipedia_es"), query, limit)


async def fetch_wikipedia(title: str, lang: str = "es") -> dict:
    return await fetch_wiki(title, LANG_TO_SITE.get(lang, "wikipedia_es"))


# --------------------------------------------------------------------------- #
# Páginas web (por URL)
# --------------------------------------------------------------------------- #
def _check_public_host(url: str) -> None:
    """Evita que el servidor se use para acceder a direcciones internas (SSRF)."""
    p = urlparse(url)
    if p.scheme not in ("http", "https") or not p.hostname:
        raise SourceError("La dirección tiene que empezar con http:// o https://")
    try:
        infos = socket.getaddrinfo(p.hostname, p.port or (443 if p.scheme == "https" else 80))
    except socket.gaierror as e:
        raise SourceError(f"No se encontró el sitio «{p.hostname}».") from e
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if not ip.is_global:
            raise SourceError("Esa dirección no es una página pública de internet.")


def _wiki_from_url(url: str) -> tuple[str, str] | None:
    p = urlparse(url)
    for key, meta in SITES.items():
        if (p.hostname or "").replace(".m.", ".") == meta["host"] and p.path.startswith("/wiki/"):
            return key, unquote(p.path[len("/wiki/"):]).replace("_", " ")
    return None


async def fetch_url(url: str) -> dict:
    url = url.strip()
    if not re.match(r"^https?://", url):
        url = "https://" + url
    wiki = _wiki_from_url(url)
    if wiki:
        return await fetch_wiki(wiki[1], wiki[0])

    current = url
    try:
        async with httpx.AsyncClient(headers={"User-Agent": USER_AGENT, "Accept": "text/html,*/*;q=0.5",
                                              "Accept-Language": "es,en;q=0.7"},
                                     timeout=TIMEOUT, follow_redirects=False) as cli:
            for _ in range(5):
                await asyncio.to_thread(_check_public_host, current)
                r = await cli.get(current)
                if r.is_redirect and r.headers.get("location"):
                    current = urljoin(current, r.headers["location"])
                    continue
                break
            if r.status_code == 403 or r.status_code == 429:
                raise SourceError("Ese sitio no permite la descarga automática de sus páginas. "
                                  "Copiá el texto y pegalo en la pestaña «Pegar mis apuntes».")
            r.raise_for_status()
            ctype = r.headers.get("content-type", "")
            if "html" not in ctype and "text/plain" not in ctype:
                raise SourceError("La dirección no es una página de texto (¿es un PDF o una imagen?). "
                                  "Copiá el texto y pegalo en «Pegar mis apuntes».")
            if len(r.content) > MAX_PAGE_BYTES:
                raise SourceError("La página es demasiado grande.")
            body = r.text
    except httpx.HTTPError as e:
        raise SourceError(f"No se pudo descargar la página ({type(e).__name__}).") from e

    if "text/plain" in ctype:
        title, text = urlparse(current).path.rsplit("/", 1)[-1] or current, clean_extract(body)
    else:
        title, text = html_to_text(body)
    try:
        sections = parse_sections(text, title or current, min_words=20)
    except SourceError as e:
        raise SourceError("No se encontró suficiente texto en esa página. Puede que se cargue con "
                          "JavaScript o que esté detrás de un inicio de sesión. Copiá el texto y "
                          "pegalo en «Pegar mis apuntes».") from e
    host = urlparse(current).hostname or ""
    return {
        "title": title or host, "lang": "es", "url": current, "revid": None, "timestamp": None,
        "source_name": host.removeprefix("www."), "license": None, "sections": sections,
    }


def from_user_notes(title: str, text: str) -> dict:
    """Permite estudiar los apuntes propios del usuario con las mismas técnicas."""
    text = unicodedata.normalize("NFC", text).replace("\r\n", "\n")
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
        "title": title or "Mis apuntes", "lang": "es", "url": None, "revid": None, "timestamp": None,
        "source_name": "Apuntes propios", "license": None, "sections": out,
    }
