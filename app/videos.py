"""Videos de YouTube recomendados para entender un tema.

Se prueba, en este orden, con lo que esté configurado:
  1. YouTube Data API v3 (clave de Google Cloud; 100 búsquedas gratis por día)
  2. SearXNG (el metabuscador que levanta docker-compose; sin clave)
  3. SerpApi (motor "youtube")
  3. Serper (búsqueda de videos de Google)
  4. Brave Search (búsqueda de videos)
  5. Tavily (limitado a youtube.com)
Sin ninguna clave se ofrecen enlaces de búsqueda en YouTube (no necesitan API).

Se descartan los Shorts y los videos de menos de 2 minutos y medio: para comprender un tema
sirven más las explicaciones completas.
"""
from __future__ import annotations

import html
import re
from urllib.parse import quote_plus

import httpx

from .sources import SourceError, USER_AGENT

TIMEOUT = httpx.Timeout(20.0, connect=10.0)
MIN_SECONDS = 150
MAX_SECONDS = 3 * 3600
YT_ID = re.compile(r"(?:[?&]v=|youtu\.be/|/embed/|/live/)([A-Za-z0-9_-]{11})")


def search_url(q: str) -> str:
    return "https://www.youtube.com/results?search_query=" + quote_plus(q)


def video_id(url: str) -> str | None:
    if not url or "/shorts/" in url or ("youtube.com" not in url and "youtu.be" not in url):
        return None
    m = YT_ID.search(url)
    return m.group(1) if m else None


def parse_clock(text: str | None) -> int | None:
    """'12:34' o '1:02:03' a segundos."""
    if not text or not re.fullmatch(r"\d{1,2}(:\d{2}){1,2}", text.strip()):
        return None
    secs = 0
    for part in text.strip().split(":"):
        secs = secs * 60 + int(part)
    return secs


def parse_iso_duration(text: str | None) -> int | None:
    """'PT1H2M3S' a segundos."""
    m = re.fullmatch(r"P(?:(\d+)D)?T?(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", text or "")
    if not m:
        return None
    d, h, mi, s = (int(x or 0) for x in m.groups())
    return d * 86400 + h * 3600 + mi * 60 + s


def fmt_clock(secs: int | None) -> str:
    if secs is None:
        return ""
    h, rest = divmod(secs, 3600)
    m, s = divmod(rest, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


def _video(vid: str, title: str, channel: str = "", seconds: int | None = None, published: str = "",
           views: str = "", description: str = "", thumb: str | None = None) -> dict:
    return {"id": vid, "url": f"https://www.youtube.com/watch?v={vid}", "title": html.unescape(title or "").strip(),
            "channel": html.unescape(channel or "").strip(), "seconds": seconds, "duration": fmt_clock(seconds),
            "published": published or "", "views": views or "", "description": html.unescape(description or "").strip()[:220],
            "thumb": thumb or f"https://i.ytimg.com/vi/{vid}/mqdefault.jpg"}


def _keep(videos: list[dict], limit: int = 8) -> list[dict]:
    out, seen = [], set()
    for v in videos:
        if v["id"] in seen or not v["title"]:
            continue
        if v["seconds"] is not None and not (MIN_SECONDS <= v["seconds"] <= MAX_SECONDS):
            continue
        seen.add(v["id"])
        out.append(v)
    return out[:limit]


def _client(**headers) -> httpx.AsyncClient:
    return httpx.AsyncClient(headers={"User-Agent": USER_AGENT, **headers}, timeout=TIMEOUT, follow_redirects=True)


# --------------------------------------------------------------------------- #
# Proveedores
# --------------------------------------------------------------------------- #
def _youtube_error(r: httpx.Response) -> None:
    if r.status_code < 400:
        return
    try:
        reason = (r.json().get("error", {}).get("errors") or [{}])[0].get("reason", "")
    except ValueError:
        reason = ""
    if reason in ("quotaExceeded", "dailyLimitExceeded", "rateLimitExceeded"):
        raise SourceError("Se terminó la cuota diaria de la YouTube Data API (se renueva cada día).")
    if reason in ("accessNotConfigured", "SERVICE_DISABLED") or "has not been used" in r.text or "disabled" in r.text:
        raise SourceError("Tu clave de Google no tiene habilitada la «YouTube Data API v3». Activala en Google Cloud.")
    if r.status_code in (400, 403):
        raise SourceError("La clave de Google no es válida para YouTube (revisá las restricciones de la clave).")
    r.raise_for_status()


async def from_youtube_api(q: str, key: str, lang: str = "es") -> list[dict]:
    async with _client() as cli:
        r = await cli.get("https://www.googleapis.com/youtube/v3/search", params={
            "part": "snippet", "q": q, "type": "video", "maxResults": 15, "relevanceLanguage": lang,
            "safeSearch": "strict", "videoDuration": "any", "key": key})
        _youtube_error(r)
        items = r.json().get("items", [])
        ids = [it["id"]["videoId"] for it in items if (it.get("id") or {}).get("videoId")]
        details = {}
        if ids:
            d = await cli.get("https://www.googleapis.com/youtube/v3/videos", params={
                "part": "contentDetails,statistics", "id": ",".join(ids), "key": key})
            if d.status_code < 400:
                details = {x["id"]: x for x in d.json().get("items", [])}
    out = []
    for it in items:
        vid = (it.get("id") or {}).get("videoId")
        if not vid:
            continue
        sn = it.get("snippet") or {}
        det = details.get(vid, {})
        secs = parse_iso_duration((det.get("contentDetails") or {}).get("duration"))
        views = (det.get("statistics") or {}).get("viewCount")
        thumb = ((sn.get("thumbnails") or {}).get("medium") or {}).get("url")
        out.append(_video(vid, sn.get("title", ""), sn.get("channelTitle", ""), secs, (sn.get("publishedAt") or "")[:10],
                          f"{int(views):,}".replace(",", ".") + " vistas" if views else "", sn.get("description", ""), thumb))
    return out


async def from_serpapi(q: str, key: str) -> list[dict]:
    async with _client() as cli:
        r = await cli.get("https://serpapi.com/search.json",
                          params={"engine": "youtube", "search_query": q, "hl": "es", "gl": "ar", "api_key": key})
    data = r.json() if r.headers.get("content-type", "").startswith("application/json") else {}
    if data.get("error") and "results" not in data.get("error", "").lower():
        raise SourceError(f"SerpApi: {data['error']}")
    if r.status_code >= 400 and not data:
        r.raise_for_status()
    out = []
    for it in data.get("video_results", []):
        vid = video_id(it.get("link", ""))
        if not vid:
            continue
        ch = it.get("channel") or {}
        thumb = it.get("thumbnail")
        thumb = thumb.get("static") if isinstance(thumb, dict) else thumb
        out.append(_video(vid, it.get("title", ""), ch.get("name", "") if isinstance(ch, dict) else str(ch),
                          parse_clock(it.get("length")), it.get("published_date") or it.get("publishedDate") or "",
                          f"{it['views']:,}".replace(",", ".") + " vistas" if isinstance(it.get("views"), int) else "",
                          it.get("description", ""), thumb))
    return out


async def from_serper(q: str, key: str) -> list[dict]:
    async with _client(**{"X-API-KEY": key, "Content-Type": "application/json"}) as cli:
        r = await cli.post("https://google.serper.dev/videos", json={"q": q, "gl": "ar", "hl": "es", "num": 15})
    if r.status_code in (401, 403):
        raise SourceError("La clave de Serper no es válida.")
    r.raise_for_status()
    out = []
    for it in r.json().get("videos", []):
        vid = video_id(it.get("link", ""))
        if vid:
            out.append(_video(vid, it.get("title", ""), it.get("channel") or "", parse_clock(it.get("duration")),
                              it.get("date") or "", "", it.get("snippet", ""), it.get("imageUrl")))
    return out


async def from_brave(q: str, key: str) -> list[dict]:
    async with _client(**{"X-Subscription-Token": key, "Accept": "application/json"}) as cli:
        r = await cli.get("https://api.search.brave.com/res/v1/videos/search",
                          params={"q": f"{q} youtube", "count": 20, "search_lang": "es", "safesearch": "strict"})
    if r.status_code in (401, 403, 422):
        raise SourceError("La clave de Brave Search no permite buscar videos.")
    r.raise_for_status()
    out = []
    for it in r.json().get("results", []):
        vid = video_id(it.get("url", ""))
        if not vid:
            continue
        v = it.get("video") or {}
        out.append(_video(vid, it.get("title", ""), v.get("creator") or v.get("publisher") or "",
                          parse_clock(v.get("duration")), it.get("age") or "", "", it.get("description", ""),
                          (it.get("thumbnail") or {}).get("src")))
    return out


def _length(value) -> int | None:
    if isinstance(value, (int, float)):
        return int(value)
    return parse_clock(str(value)) if value else None


async def from_searxng(q: str, base: str) -> list[dict]:
    async with _client(Accept="application/json") as cli:
        r = await cli.get(base.rstrip("/") + "/search",
                          params={"q": q, "format": "json", "categories": "videos", "language": "es", "safesearch": 1})
    if r.status_code == 403:
        raise SourceError("SearXNG no tiene habilitado el formato JSON.")
    r.raise_for_status()
    out = []
    for it in r.json().get("results", []):
        vid = video_id(it.get("url", ""))
        if vid:
            out.append(_video(vid, it.get("title", ""), it.get("author") or "", _length(it.get("length")),
                              (it.get("publishedDate") or "")[:10], "", it.get("content", ""), it.get("thumbnail")))
    return out


async def from_tavily(q: str, key: str) -> list[dict]:
    async with _client(Authorization=f"Bearer {key}") as cli:
        r = await cli.post("https://api.tavily.com/search", json={
            "query": q, "max_results": 12, "include_domains": ["youtube.com"], "search_depth": "basic"})
    if r.status_code in (401, 403):
        raise SourceError("La clave de Tavily no es válida.")
    r.raise_for_status()
    out = []
    for it in r.json().get("results", []):
        vid = video_id(it.get("url", ""))
        if vid:
            title = re.sub(r"\s*-\s*YouTube\s*$", "", it.get("title", ""))
            out.append(_video(vid, title, "", None, "", "", it.get("content", "")))
    return out


PROVIDERS = [
    ("google", "YouTube", from_youtube_api),
    ("searxng", "SearXNG", from_searxng),
    ("serpapi", "SerpApi", from_serpapi),
    ("serper", "Serper", from_serper),
    ("brave", "Brave Search", from_brave),
    ("tavily", "Tavily", from_tavily),
]


def available(keys: dict) -> list[str]:
    return [label for name, label, _ in PROVIDERS if keys.get(name)]


async def find(topic: str, keys: dict, extra: str = "explicación") -> dict:
    """Busca videos para un tema con el primer proveedor configurado que devuelva resultados."""
    q = f"{topic} {extra}".strip()
    errors = []
    for name, label, fn in PROVIDERS:
        key = keys.get(name)
        if not key:
            continue
        try:
            vids = _keep(await fn(q, key))
            if len(vids) < 3 and extra:  # muy pocos: se prueba solo con el tema
                vids = _keep(vids + await fn(topic, key))
        except SourceError as e:
            errors.append(f"{label}: {e}")
            continue
        except Exception as e:  # noqa: BLE001
            errors.append(f"{label}: no respondió ({type(e).__name__})")
            continue
        if vids:
            return {"videos": vids, "via": label, "query": q, "errors": errors}
    return {"videos": [], "via": None, "query": q, "errors": errors}
