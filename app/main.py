"""Estudio Dunlosky — API y servidor web.

Ejecutar: uvicorn app.main:app --host 0.0.0.0 --port 8000
"""
from __future__ import annotations

import json
import os
import random
import re
import uuid
import zlib
from collections import Counter, defaultdict
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from fastapi import BackgroundTasks, FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from rapidfuzz import fuzz

from . import ai, db, generator, grader, sources, srs
from . import textproc as tp

APP_DIR = Path(__file__).parent
STATIC = APP_DIR / "static"
try:
    LOCAL_TZ = ZoneInfo(os.environ.get("TZ") or "America/Argentina/Buenos_Aires")
except Exception:  # noqa: BLE001
    LOCAL_TZ = timezone.utc

# Modo público (para publicarla en internet, por ejemplo en Render):
#  - cada visitante recibe una cookie con un id aleatorio y su propia base de datos,
#    así nadie ve los temas ni el progreso de otro;
#  - nadie puede cargar ni cambiar la clave de IA desde la interfaz.
PUBLIC_MODE = os.environ.get("PUBLIC_MODE", "").strip().lower() in ("1", "true", "si", "sí", "yes")
VISITOR_COOKIE = "ed_visitante"
VISITORS_DIR = os.path.join(os.path.dirname(db.DB_PATH) or ".", "visitantes")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    if not PUBLIC_MODE:
        db.init()
    yield


app = FastAPI(title="Estudio Dunlosky", version="1.0.0", lifespan=lifespan)


@app.middleware("http")
async def visitor_scope(request: Request, call_next):
    path = request.url.path
    if not PUBLIC_MODE or path.startswith("/static") or path == "/api/health":
        return await call_next(request)
    vid = request.cookies.get(VISITOR_COOKIE, "")
    is_new = not re.fullmatch(r"[0-9a-f]{32}", vid)
    if is_new:
        vid = uuid.uuid4().hex
    token = db.use_path(os.path.join(VISITORS_DIR, f"{vid}.db"))
    try:
        response = await call_next(request)
    finally:
        db.reset_path(token)
    if is_new:
        https = request.headers.get("x-forwarded-proto", request.url.scheme) == "https"
        response.set_cookie(VISITOR_COOKIE, vid, max_age=60 * 60 * 24 * 365, httponly=True,
                            samesite="lax", secure=https)
    return response


# --------------------------------------------------------------------------- #
# Utilidades
# --------------------------------------------------------------------------- #
def now_iso() -> str:
    return srs.iso(srs.now())


def ai_config(con) -> ai.AIConfig:
    if PUBLIC_MODE:  # solo la configura el dueño del servidor, con variables de entorno
        return ai.AIConfig(os.environ.get("ANTHROPIC_API_KEY"), os.environ.get("CLAUDE_MODEL"))
    key = db.get_setting(con, "anthropic_key") or os.environ.get("ANTHROPIC_API_KEY")
    model = db.get_setting(con, "claude_model") or os.environ.get("CLAUDE_MODEL")
    return ai.AIConfig(key, model)


def topic_keywords(con, topic_id: int) -> dict:
    r = con.execute("SELECT keywords FROM topics WHERE id=?", (topic_id,)).fetchone()
    if not r:
        raise HTTPException(404, "Tema no encontrado")
    return json.loads(r["keywords"] or "{}")


def get_section(con, section_id: int) -> dict:
    r = db.row(con.execute("SELECT * FROM sections WHERE id=?", (section_id,)).fetchone())
    if not r:
        raise HTTPException(404, "Sección no encontrada")
    return r


def section_sentence_list(text: str) -> list[str]:
    return [s for _, s in tp.section_sentences(text)]


def local_day(iso: str) -> str:
    return datetime.fromisoformat(iso).astimezone(LOCAL_TZ).date().isoformat()


def end_of_today_utc() -> str:
    local_now = datetime.now(LOCAL_TZ)
    end = local_now.replace(hour=23, minute=59, second=59, microsecond=0)
    return srs.iso(end)


def insert_items(con, topic_id: int, section_id: int, items: list[dict]) -> list[int]:
    ids = []
    ts = now_iso()
    for it in items:
        cur = con.execute(
            "INSERT INTO items(topic_id, section_id, sentence_idx, kind, prompt, answer, options, context, hint,"
            " term_kind, origin, level, created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (topic_id, section_id, it.get("sentence_idx"), it["kind"], it["prompt"], it["answer"],
             json.dumps(it["options"], ensure_ascii=False) if it.get("options") else None,
             it.get("context"), it.get("hint"), it.get("term_kind"), it.get("origin", "auto"),
             it.get("level") or generator.level_for(it), ts),
        )
        ids.append(cur.lastrowid)
    return ids


def public_item(it: dict, meta: dict) -> dict:
    t = meta["topics"].get(it["topic_id"], {})
    s = meta["sections"].get(it["section_id"], {})
    return {
        "id": it["id"], "kind": it["kind"], "prompt": it["prompt"], "options": it["options"],
        "hint": it["hint"], "origin": it["origin"], "topic_id": it["topic_id"],
        "topic_title": t.get("title"), "hue": t.get("hue", 220), "section_id": it["section_id"],
        "section_title": s.get("title"), "seen": it["seen"], "last_verdict": it["last_verdict"],
        "term": it.get("_term"),
        "level": it.get("level") or 2,
    }


def meta_for(con, items: list[dict]) -> dict:
    tids = {i["topic_id"] for i in items}
    sids = {i["section_id"] for i in items if i["section_id"]}
    topics = {r["id"]: dict(r) for r in con.execute(
        f"SELECT id, title, hue FROM topics WHERE id IN ({','.join('?' * len(tids)) or 'NULL'})", tuple(tids))}
    secs = {r["id"]: dict(r) for r in con.execute(
        f"SELECT id, title, source_id FROM sections WHERE id IN ({','.join('?' * len(sids)) or 'NULL'})", tuple(sids))}
    return {"topics": topics, "sections": secs}


# --------------------------------------------------------------------------- #
# Estado y ajustes
# --------------------------------------------------------------------------- #
@app.get("/api/status")
def status():
    with db.tx() as con:
        cfg = ai_config(con)
        return {"ok": True, "public": PUBLIC_MODE, "ai_enabled": cfg.enabled, "model": cfg.model if cfg.enabled else None,
                "key_from": "ajustes" if db.get_setting(con, "anthropic_key") else (
                    "entorno" if os.environ.get("ANTHROPIC_API_KEY") else None)}


class SettingsIn(BaseModel):
    anthropic_key: str | None = None
    claude_model: str | None = None
    clear_key: bool = False


@app.post("/api/settings")
def save_settings(body: SettingsIn):
    if PUBLIC_MODE:
        raise HTTPException(403, "En la versión pública los ajustes de IA no se pueden cambiar.")
    with db.tx() as con:
        if body.clear_key:
            db.set_setting(con, "anthropic_key", None)
        elif body.anthropic_key:
            db.set_setting(con, "anthropic_key", body.anthropic_key.strip())
        if body.claude_model is not None:
            db.set_setting(con, "claude_model", body.claude_model.strip() or None)
    return status()


@app.post("/api/settings/test-ai")
async def test_ai():
    if PUBLIC_MODE:
        raise HTTPException(403, "En la versión pública los ajustes de IA no se pueden cambiar.")
    with db.tx() as con:
        cfg = ai_config(con)
    if not cfg.enabled:
        return {"ok": False, "message": "No hay ninguna clave configurada."}
    ok, msg = await ai.test_connection(cfg)
    return {"ok": ok, "message": msg if not ok else f"Conectado con {cfg.model}."}


# --------------------------------------------------------------------------- #
# Búsqueda de fuentes y creación de temas
# --------------------------------------------------------------------------- #
@app.get("/api/sources")
def list_sources():
    return [{"site": k, "name": v["name"], "about": v["about"], "lang": v["lang"],
             "default": k in sources.DEFAULT_SEARCH} for k, v in sources.SITES.items()]


@app.get("/api/search")
async def search(q: str, sites: str = "", lang: str | None = None):
    q = q.strip()
    if len(q) < 2:
        raise HTTPException(400, "Escribí al menos 2 letras.")
    chosen = [x for x in sites.split(",") if x] or (
        [sources.LANG_TO_SITE.get(lang, "wikipedia_es")] if lang else sources.DEFAULT_SEARCH)
    try:
        res = await sources.search_many(q, chosen)
        # si en español no hubo nada, probamos en inglés
        if not any(g["results"] for g in res["groups"]) and "wikipedia_en" not in chosen:
            extra = await sources.search_many(q, ["wikipedia_en"])
            res["groups"] += extra["groups"]
            res["fallback_en"] = any(g["results"] for g in extra["groups"])
    except sources.SourceError as e:
        raise HTTPException(502, str(e)) from e
    return res


class SourceRef(BaseModel):
    title: str = ""
    lang: str = "es"
    site: str | None = None
    url: str | None = None


class NotesIn(BaseModel):
    title: str = ""
    text: str


class TopicIn(BaseModel):
    title: str | None = None
    sources: list[SourceRef] = Field(default_factory=list)
    notes: NotesIn | None = None


async def _collect_sources(body: TopicIn) -> list[dict]:
    collected = []
    try:
        for s in body.sources[:4]:
            if s.url:
                collected.append(await sources.fetch_url(s.url))
            else:
                site = s.site if s.site in sources.SITES else sources.LANG_TO_SITE.get(s.lang, "wikipedia_es")
                collected.append(await sources.fetch_wiki(s.title, site))
        if body.notes and body.notes.text.strip():
            collected.append(sources.from_user_notes(body.notes.title or body.title or "", body.notes.text))
    except sources.SourceError as e:
        raise HTTPException(400, str(e)) from e
    if not collected:
        raise HTTPException(400, "Elegí al menos una fuente o pegá tus apuntes.")
    return collected


def _store_sources(con, topic_id: int, title: str, collected: list[dict]) -> list[int]:
    """Guarda fuentes y secciones, recalcula palabras clave y genera preguntas."""
    new_sections = []
    ord_base = con.execute("SELECT COALESCE(MAX(ord), -1) + 1 FROM sections WHERE topic_id=?", (topic_id,)).fetchone()[0]
    for src in collected:
        cur = con.execute(
            "INSERT INTO sources(topic_id, name, title, url, revid, revised_at, license, retrieved_at)"
            " VALUES(?,?,?,?,?,?,?,?)",
            (topic_id, src["source_name"], src["title"], src["url"], src["revid"], src["timestamp"],
             src["license"], now_iso()))
        source_id = cur.lastrowid
        multi = len(collected) > 1
        for sec in src["sections"]:
            sec_title = sec["title"]
            if multi and sec_title in ("Introducción", "Apuntes"):
                sec_title = f"{src['title']}: {sec_title.lower()}"
            cur = con.execute("INSERT INTO sections(topic_id, source_id, ord, title, text) VALUES(?,?,?,?,?)",
                              (topic_id, source_id, ord_base, sec_title, sec["text"]))
            new_sections.append({"id": cur.lastrowid, "title": sec_title, "text": sec["text"]})
            ord_base += 1

    all_secs = db.rows(con.execute("SELECT id, title, text FROM sections WHERE topic_id=? ORDER BY ord", (topic_id,)))
    all_sentences = [s for sec in all_secs for _, s in tp.section_sentences(sec["text"])]
    keywords = tp.extract_keywords(all_sentences, title)
    con.execute("UPDATE topics SET keywords=? WHERE id=?", (json.dumps(keywords, ensure_ascii=False), topic_id))

    rng = random.Random(zlib.crc32(f"{topic_id}{title}".encode()))
    cap = max(10, min(36, 420 // max(len(all_secs), 1)))
    for sec in new_sections:
        items = generator.generate_for_section(sec["text"], keywords, title, rng, cap)
        insert_items(con, topic_id, sec["id"], items)
    return [s["id"] for s in new_sections]


async def _ai_enrich(topic_id: int, section_ids: list[int]) -> None:
    with db.tx() as con:
        cfg = ai_config(con)
        t = db.row(con.execute("SELECT title FROM topics WHERE id=?", (topic_id,)).fetchone())
        secs = db.rows(con.execute(
            f"SELECT id, title, text FROM sections WHERE id IN ({','.join('?' * len(section_ids))})", tuple(section_ids)))
        con.execute("UPDATE topics SET ai_status='generando' WHERE id=?", (topic_id,))
    if not cfg.enabled or not t:
        return
    added = 0
    secs.sort(key=lambda s: -len(s["text"]))
    for sec in secs[:6]:
        qs = await ai.generate_questions(cfg, t["title"], sec["title"], sec["text"], 5)
        sents = section_sentence_list(sec["text"])
        for q in qs:
            nq = tp.normalize(q["context"])
            best = max(range(len(sents)), key=lambda i: fuzz.partial_ratio(nq, tp.normalize(sents[i])), default=None)
            q["sentence_idx"] = best
        with db.tx() as con:
            if con.execute("SELECT 1 FROM topics WHERE id=?", (topic_id,)).fetchone():
                insert_items(con, topic_id, sec["id"], qs)
                added += len(qs)
    with db.tx() as con:
        con.execute("UPDATE topics SET ai_status=? WHERE id=?", ("listo" if added else "sin_resultados", topic_id))


@app.post("/api/topics")
async def create_topic(body: TopicIn, bg: BackgroundTasks):
    collected = await _collect_sources(body)
    title = (body.title or "").strip() or collected[0]["title"]
    with db.tx() as con:
        hue = random.Random(title).choice([12, 38, 150, 175, 200, 232, 262, 300, 330])
        cur = con.execute("INSERT INTO topics(title, lang, hue, created_at) VALUES(?,?,?,?)",
                          (title, collected[0]["lang"], hue, now_iso()))
        topic_id = cur.lastrowid
        new_ids = _store_sources(con, topic_id, title, collected)
        cfg = ai_config(con)
    if cfg.enabled:
        bg.add_task(_ai_enrich, topic_id, new_ids)
    return {"id": topic_id, "title": title}


@app.post("/api/topics/{topic_id}/sources")
async def add_sources(topic_id: int, body: TopicIn, bg: BackgroundTasks):
    collected = await _collect_sources(body)
    with db.tx() as con:
        t = db.row(con.execute("SELECT title FROM topics WHERE id=?", (topic_id,)).fetchone())
        if not t:
            raise HTTPException(404, "Tema no encontrado")
        new_ids = _store_sources(con, topic_id, t["title"], collected)
        cfg = ai_config(con)
    if cfg.enabled:
        bg.add_task(_ai_enrich, topic_id, new_ids)
    return {"id": topic_id, "added_sections": len(new_ids)}


@app.delete("/api/topics/{topic_id}")
def delete_topic(topic_id: int):
    with db.tx() as con:
        con.execute("DELETE FROM topics WHERE id=?", (topic_id,))
    return {"ok": True}


def _topic_stats(con, topic_id: int | None = None) -> dict:
    where = "WHERE topic_id=?" if topic_id else ""
    args = (topic_id,) if topic_id else ()
    rs = db.rows(con.execute(
        f"SELECT topic_id, section_id, seen, correct, reps, due, last_verdict FROM items {where}", args))
    eot = end_of_today_utc()
    out: dict = defaultdict(lambda: {"items": 0, "seen": 0, "correct": 0, "mastered": 0, "due": 0, "errors": 0})
    for r in rs:
        for key in (("t", r["topic_id"]), ("s", r["section_id"])):
            st = out[key]
            st["items"] += 1
            st["seen"] += r["seen"] > 0
            st["correct"] += r["last_verdict"] == "correct"
            st["mastered"] += r["reps"] >= 3
            st["due"] += bool(r["due"] and r["due"] <= eot)
            st["errors"] += r["last_verdict"] in ("incorrect", "partial")
    for st in out.values():
        st["accuracy"] = round(st["correct"] / st["seen"], 2) if st["seen"] else None
        st["progress"] = round(st["mastered"] / st["items"], 2) if st["items"] else 0
    return out


@app.get("/api/topics")
def list_topics():
    with db.tx() as con:
        ts = db.rows(con.execute("SELECT id, title, lang, hue, ai_status, created_at FROM topics ORDER BY created_at DESC"))
        stats = _topic_stats(con)
        srcs = defaultdict(list)
        for r in con.execute("SELECT topic_id, name, title FROM sources"):
            srcs[r["topic_id"]].append({"name": r["name"], "title": r["title"]})
    for t in ts:
        t["stats"] = stats.get(("t", t["id"]), {"items": 0, "seen": 0, "accuracy": None, "due": 0, "errors": 0,
                                                "progress": 0, "mastered": 0, "correct": 0})
        t["sources"] = srcs[t["id"]]
    return ts


@app.get("/api/topics/{topic_id}")
def get_topic(topic_id: int):
    with db.tx() as con:
        t = db.row(con.execute("SELECT id, title, lang, hue, ai_status, created_at FROM topics WHERE id=?",
                               (topic_id,)).fetchone())
        if not t:
            raise HTTPException(404, "Tema no encontrado")
        t["sources"] = db.rows(con.execute("SELECT * FROM sources WHERE topic_id=?", (topic_id,)))
        secs = db.rows(con.execute("SELECT id, source_id, ord, title, text FROM sections WHERE topic_id=? ORDER BY ord",
                                   (topic_id,)))
        stats = _topic_stats(con, topic_id)
        kinds = Counter(r["kind"] for r in con.execute("SELECT kind FROM items WHERE topic_id=?", (topic_id,)))
        today = datetime.now(LOCAL_TZ).date()
        upcoming = Counter()
        for r in con.execute("SELECT due FROM items WHERE topic_id=? AND due IS NOT NULL", (topic_id,)):
            d = local_day(r["due"])
            upcoming[max(d, today.isoformat())] += 1
        t["upcoming"] = [{"day": (today + timedelta(days=i)).isoformat(),
                          "count": upcoming.get((today + timedelta(days=i)).isoformat(), 0)} for i in range(8)]
    for s in secs:
        paras: list[list[dict]] = []
        for i, (pi, sent) in enumerate(tp.section_sentences(s["text"])):
            while len(paras) <= pi:
                paras.append([])
            paras[pi].append({"i": i, "text": sent})
        s["paragraphs"] = [p for p in paras if p]
        s["words"] = tp.word_count(s["text"])
        s["stats"] = stats.get(("s", s["id"]), {"items": 0, "seen": 0, "accuracy": None, "due": 0, "errors": 0,
                                                "progress": 0})
        del s["text"]
    t["sections"] = secs
    t["stats"] = stats.get(("t", topic_id), {})
    t["kinds"] = kinds
    return t


# --------------------------------------------------------------------------- #
# Sesiones de práctica
# --------------------------------------------------------------------------- #
class SessionIn(BaseModel):
    mode: str = "practice"  # practice | review | interleaved | errors | elaborative | section | items | terms
    topic_ids: list[int] = Field(default_factory=list)
    section_id: int | None = None
    item_ids: list[int] = Field(default_factory=list)
    terms: list[str] = Field(default_factory=list)
    n: int = 12
    level: str = "mixto"  # basico | intermedio | avanzado | mixto


LEVEL_ORDER = {"basico": [1, 2, 3], "intermedio": [2, 1, 3], "avanzado": [3, 2, 1]}


def _by_level(cands: list[dict], level: str, n: int) -> list[dict]:
    """Prioriza el nivel pedido; si no alcanzan las preguntas, completa con el nivel más cercano."""
    order = LEVEL_ORDER.get(level)
    if not order:
        return cands
    out: list[dict] = []
    for lv in order:
        out += [c for c in cands if (c.get("level") or 2) == lv]
        if len({(c["section_id"], c["sentence_idx"]) for c in out}) >= n:
            break
    return out


def _priority(it: dict, now: str) -> tuple:
    due = it["due"] is not None and it["due"] <= now
    unseen = it["seen"] == 0
    acc = it["correct"] / it["seen"] if it["seen"] else 1
    return (0 if due else (1 if unseen else 2), acc, random.random())


def _pick_varied(cands: list[dict], n: int, one_per_sentence: bool = True) -> list[dict]:
    """Elige n ítems variando el tipo de pregunta y sin repetir la misma oración."""
    by_kind: dict[str, list[dict]] = defaultdict(list)
    for c in cands:
        by_kind[c["kind"]].append(c)
    order = ["mc", "cloze", "open", "tf", "why"]
    kinds = [k for k in order if k in by_kind] + [k for k in by_kind if k not in order]
    used_sent = set()
    picked = []
    while len(picked) < n and any(by_kind.values()):
        progress = False
        for k in kinds:
            lst = by_kind[k]
            while lst:
                c = lst.pop(0)
                key = (c["section_id"], c["sentence_idx"])
                if one_per_sentence and c["sentence_idx"] is not None and key in used_sent:
                    continue
                used_sent.add(key)
                picked.append(c)
                progress = True
                break
            if len(picked) >= n:
                break
        if not progress:
            break
    return picked


def _interleave(groups: list[list[dict]]) -> list[dict]:
    out = []
    groups = [g[:] for g in groups if g]
    while groups:
        for g in groups:
            out.append(g.pop(0))
        groups = [g for g in groups if g]
    return out


def _siblings(con, it: dict, exclude: set[int], k: int = 1) -> list[dict]:
    """Preguntas sobre la misma oración (o vecinas) que la que se respondió mal."""
    if it["sentence_idx"] is None:
        return []
    rs = [db.item_dict(r) for r in con.execute(
        "SELECT * FROM items WHERE section_id=? AND sentence_idx BETWEEN ? AND ? AND id<>?",
        (it["section_id"], it["sentence_idx"] - 1, it["sentence_idx"] + 1, it["id"]))]
    rs = [r for r in rs if r["id"] not in exclude]
    rs.sort(key=lambda r: (r["sentence_idx"] != it["sentence_idx"], r["kind"] == it["kind"], random.random()))
    return rs[:k]


def _ensure_elaborative(con, topic_ids: list[int], need: int) -> None:
    """Si faltan preguntas de '¿por qué?', las crea a partir de las oraciones clave."""
    for tid in topic_ids:
        have = con.execute("SELECT COUNT(*) FROM items WHERE topic_id=? AND kind='why'", (tid,)).fetchone()[0]
        if have >= need:
            continue
        kw = topic_keywords(con, tid)
        existing = {(r["section_id"], r["sentence_idx"]) for r in con.execute(
            "SELECT section_id, sentence_idx FROM items WHERE topic_id=? AND kind='why'", (tid,))}
        new = []
        for sec in db.rows(con.execute("SELECT id, text FROM sections WHERE topic_id=? ORDER BY ord", (tid,))):
            sents = section_sentence_list(sec["text"])
            for i in tp.key_sentence_indices(sents, kw, 0.25):
                if (sec["id"], i) in existing or tp.word_count(sents[i]) < 8:
                    continue
                around = " ".join(x for x in (sents[i - 1] if i > 0 else "", sents[i + 1] if i + 1 < len(sents) else "") if x)
                if tp.word_count(around) < 8:
                    continue
                new.append((sec["id"], {"kind": "why", "prompt": generator.generic_why_prompt(sents[i]),
                                        "answer": around, "context": sents[i], "sentence_idx": i,
                                        "hint": None, "options": None, "origin": "elab", "level": 3}))
        random.shuffle(new)
        for sid, item in new[: max(0, need - have)]:
            insert_items(con, tid, sid, [item])


@app.post("/api/session")
def build_session(body: SessionIn):
    n = max(1, min(body.n, 40))
    now = now_iso()
    eot = end_of_today_utc()
    with db.tx() as con:
        def load(sql, args=()):
            return [db.item_dict(r) for r in con.execute(sql, args)]

        tids = body.topic_ids or [r["id"] for r in con.execute("SELECT id FROM topics")]
        ph = ",".join("?" * len(tids)) or "NULL"
        picked: list[dict] = []
        intro = None

        if body.mode == "items":
            ids = body.item_ids[:60]
            by_id = {i["id"]: i for i in load(f"SELECT * FROM items WHERE id IN ({','.join('?' * len(ids)) or 'NULL'})",
                                              tuple(ids))}
            picked = [by_id[i] for i in ids if i in by_id]

        elif body.mode == "section":
            if not body.section_id:
                raise HTTPException(400, "Falta la sección")
            cands = load("SELECT * FROM items WHERE section_id=?", (body.section_id,))
            if body.level != "avanzado":
                cands = [c for c in cands if c["kind"] != "why"]
            cands.sort(key=lambda it: _priority(it, now))
            picked = _pick_varied(_by_level(cands, body.level, n), n)

        elif body.mode == "review":
            cands = load(f"SELECT * FROM items WHERE topic_id IN ({ph}) AND due IS NOT NULL AND due<=? ORDER BY due",
                         (*tids, eot))
            groups = defaultdict(list)
            for c in cands:
                groups[c["topic_id"]].append(c)
            picked = _interleave(list(groups.values()))[:n]
            intro = "Repaso espaciado: estas preguntas tocan hoy según tu historial."

        elif body.mode == "errors":
            if body.item_ids:  # errores concretos de una sesión recién terminada
                ids = body.item_ids[:30]
                errs = load(f"SELECT * FROM items WHERE id IN ({','.join('?' * len(ids))})", tuple(ids))
            else:
                errs = load(f"SELECT * FROM items WHERE topic_id IN ({ph}) AND last_verdict IN ('incorrect','partial')"
                            " ORDER BY lapses DESC, due", tuple(tids))
            used = {e["id"] for e in errs}
            first, second = [], []
            for e in errs[: (len(errs) if body.item_ids else max(1, n // 2))]:
                first.append(e)
                for s in _siblings(con, e, used):
                    used.add(s["id"])
                    second.append(s)
            # primero el ítem fallado; las preguntas hermanas aparecen después, mezcladas
            random.shuffle(second)
            picked = first + second
            intro = "Práctica focalizada: cada error vuelve con preguntas sobre ese mismo fragmento."

        elif body.mode == "elaborative":
            _ensure_elaborative(con, tids, max(6, n))
            cands = load(f"SELECT * FROM items WHERE topic_id IN ({ph}) AND kind IN ('why','relate')", tuple(tids))
            cands.sort(key=lambda it: _priority(it, now))
            picked = cands[:n]

        elif body.mode == "terms":
            kw_cache = {}
            for term in body.terms[:20]:
                nt = tp.normalize(term)
                cands = [c for c in load(f"SELECT * FROM items WHERE topic_id IN ({ph}) AND kind IN ('cloze','mc')",
                                         tuple(tids)) if tp.normalize(c["answer"]) == nt]
                if cands:
                    best_item = min(cands, key=lambda it: _priority(it, now))
                    best_item["_term"] = term
                    picked.append(best_item)
                    continue
                # crear una pregunta de huecos con la oración que mejor define el término
                for tid in tids:
                    kw = kw_cache.setdefault(tid, topic_keywords(con, tid))
                    best = _definition_sentence(con, tid, term, kw)
                    if best:
                        sec_id, idx, sent = best
                        prompt = generator._blank(sent, term)
                        if generator.BLANK in prompt:
                            item = {"kind": "cloze", "prompt": prompt, "answer": term, "context": sent,
                                    "sentence_idx": idx, "hint": generator._hint(term, tp.term_kind(term)),
                                    "options": None, "origin": "mnemo", "level": 2}
                            new_id = insert_items(con, tid, sec_id, [item])[0]
                            new_item = db.item_dict(con.execute("SELECT * FROM items WHERE id=?", (new_id,)).fetchone())
                            new_item["_term"] = term
                            picked.append(new_item)
                        break

        else:  # practice / interleaved
            groups = []
            for tid in tids:
                sql = "SELECT * FROM items WHERE topic_id=?" + ("" if body.level == "avanzado" else " AND kind<>'why'")
                cands = load(sql, (tid,))
                cands.sort(key=lambda it: _priority(it, now))
                per = n if len(tids) == 1 else max(2, -(-n // len(tids)))
                groups.append(_pick_varied(_by_level(cands, body.level, per), per))
            picked = _interleave(groups)[:n]
            if body.mode == "interleaved":
                intro = "Práctica intercalada: los temas se mezclan para que aprendas a distinguir cuándo aplica cada cosa."

        meta = meta_for(con, picked) if picked else {"topics": {}, "sections": {}}
    items = [public_item(it, meta) for it in picked]
    for it in items:
        if it["kind"] == "mc" and it["options"]:
            random.shuffle(it["options"])
    return {"mode": body.mode, "intro": intro, "items": items, "level": body.level}


def _definition_sentence(con, topic_id: int, term: str, kw: dict):
    best = None
    best_score = -1.0
    for sec in db.rows(con.execute("SELECT id, text FROM sections WHERE topic_id=?", (topic_id,))):
        sents = section_sentence_list(sec["text"])
        scores = tp.score_sentences(sents, kw)
        for i, s in enumerate(sents):
            if tp.normalize(term) in tp.normalize(s):
                sc = scores[i] + (1.5 if tp.normalize(s).startswith(tp.normalize(term)) else 0)
                if 6 <= tp.word_count(s) <= 50 and sc > best_score:
                    best, best_score = (sec["id"], i, s), sc
    return best


# --------------------------------------------------------------------------- #
# Respuestas y corrección
# --------------------------------------------------------------------------- #
class AnswerIn(BaseModel):
    item_id: int
    answer: str = ""
    technique: str = "practice"
    used_hint: bool = False


def _source_for(con, section_id: int | None) -> dict | None:
    if not section_id:
        return None
    r = con.execute("SELECT so.name, so.title, so.url, so.revid, se.title AS section_title FROM sections se "
                    "LEFT JOIN sources so ON so.id = se.source_id WHERE se.id=?", (section_id,)).fetchone()
    if not r:
        return None
    d = dict(r)
    if d.get("url") and d.get("revid"):
        d["permalink"] = f"{d['url'].split('/wiki/')[0]}/w/index.php?oldid={d['revid']}"
    return d


def _apply(con, item: dict, verdict: str, used_hint: bool) -> dict:
    q = srs.quality_from(verdict, used_hint)
    new = srs.schedule(item["ease"], item["interval"], item["reps"], item["lapses"], q)
    con.execute("UPDATE items SET ease=?, interval=?, reps=?, lapses=?, due=?, last_verdict=? WHERE id=?",
                (new["ease"], new["interval"], new["reps"], new["lapses"], new["due"], verdict, item["id"]))
    return new


@app.post("/api/answer")
async def answer(body: AnswerIn):
    with db.tx() as con:
        r = con.execute("SELECT * FROM items WHERE id=?", (body.item_id,)).fetchone()
        if not r:
            raise HTTPException(404, "Pregunta no encontrada")
        item = db.item_dict(r)
        cfg = ai_config(con)

    result = grader.grade(item, body.answer)
    result["by"] = "heuristica"
    if item["kind"] in ("open", "why", "relate") and cfg.enabled and body.answer.strip():
        ai_res = await ai.grade_open(cfg, item["prompt"], item["answer"], item.get("context") or "", body.answer)
        if ai_res:
            result = ai_res

    with db.tx() as con:
        prev = {k: item[k] for k in ("ease", "interval", "reps", "lapses", "due", "last_verdict")}
        new = _apply(con, item, result["verdict"], body.used_hint)
        con.execute("UPDATE items SET seen=seen+1, correct=correct+?, last_answer=? WHERE id=?",
                    (1 if result["verdict"] == "correct" else 0, body.answer[:2000], item["id"]))
        cur = con.execute(
            "INSERT INTO attempts(item_id, topic_id, section_id, technique, answer, verdict, score, prev_state, created_at)"
            " VALUES(?,?,?,?,?,?,?,?,?)",
            (item["id"], item["topic_id"], item["section_id"], body.technique, body.answer[:2000], result["verdict"],
             result["score"], json.dumps(prev), now_iso()))
        attempt_id = cur.lastrowid
        siblings = len(_siblings(con, item, set(), 3)) if result["verdict"] != "correct" else 0
        src = _source_for(con, item["section_id"])

    return {
        **result,
        "attempt_id": attempt_id,
        "item_id": item["id"],
        "kind": item["kind"],
        "correct_answer": item["answer"],
        "context": item["context"],
        "source": src,
        "next_due": new["due"],
        "interval_days": new["interval"],
        "siblings": siblings,
        "self_check": item["kind"] in ("open", "why", "relate"),
    }


class OverrideIn(BaseModel):
    verdict: str


@app.post("/api/attempts/{attempt_id}/override")
def override(attempt_id: int, body: OverrideIn):
    if body.verdict not in ("correct", "partial", "incorrect"):
        raise HTTPException(400, "Veredicto inválido")
    with db.tx() as con:
        a = db.row(con.execute("SELECT * FROM attempts WHERE id=?", (attempt_id,)).fetchone())
        if not a:
            raise HTTPException(404, "Intento no encontrado")
        prev = json.loads(a["prev_state"])
        item = db.item_dict(con.execute("SELECT * FROM items WHERE id=?", (a["item_id"],)).fetchone())
        base = {**item, **prev}
        new = _apply(con, base, body.verdict, False)
        delta = (body.verdict == "correct") - (a["verdict"] == "correct")
        con.execute("UPDATE items SET correct=MAX(0, correct+?) WHERE id=?", (delta, item["id"]))
        con.execute("UPDATE attempts SET verdict=?, score=? WHERE id=?",
                    (body.verdict, {"correct": 1.0, "partial": 0.5, "incorrect": 0.0}[body.verdict], attempt_id))
    return {"ok": True, "next_due": new["due"], "interval_days": new["interval"]}


# --------------------------------------------------------------------------- #
# Técnicas basadas en texto: resumen, subrayado, autoexplicación, notas
# --------------------------------------------------------------------------- #
def _note(con, topic_id, section_id, technique, ref, content, feedback=None):
    con.execute("INSERT INTO notes(topic_id, section_id, technique, ref, content, feedback, created_at)"
                " VALUES(?,?,?,?,?,?,?)",
                (topic_id, section_id, technique, ref, content,
                 json.dumps(feedback, ensure_ascii=False) if feedback is not None else None, now_iso()))


class SummaryIn(BaseModel):
    section_id: int
    text: str


@app.post("/api/summary")
def summary(body: SummaryIn):
    with db.tx() as con:
        sec = get_section(con, body.section_id)
        kw = topic_keywords(con, sec["topic_id"])
        fb = grader.grade_summary(sec["text"], body.text, kw)
        items = [db.item_dict(r) for r in con.execute(
            "SELECT * FROM items WHERE section_id=? AND kind IN ('cloze','mc','open','why')", (sec["id"],))]
        practice = []
        for concept in fb["missing"]:
            nc = tp.normalize(concept)
            match = [i for i in items if tp.normalize(i["answer"]) == nc] or \
                    [i for i in items if nc in tp.normalize(i.get("context") or "")]
            match.sort(key=lambda i: (i["kind"] not in ("cloze", "mc"), i["id"]))
            for m in match[:1]:
                if m["id"] not in practice:
                    practice.append(m["id"])
        evidence = {}
        for concept in fb["missing"]:
            for s in section_sentence_list(sec["text"]):
                if tp.normalize(concept) in tp.normalize(s):
                    evidence[concept] = s
                    break
        fb["evidence"] = evidence
        fb["practice_ids"] = practice
        _note(con, sec["topic_id"], sec["id"], "summary", None, body.text, fb)
    return fb


class HighlightIn(BaseModel):
    section_id: int
    selected: list[int]


@app.post("/api/highlight")
def highlight(body: HighlightIn):
    with db.tx() as con:
        sec = get_section(con, body.section_id)
        kw = topic_keywords(con, sec["topic_id"])
        sents = section_sentence_list(sec["text"])
        key = tp.key_sentence_indices(sents, kw, 0.3)
        fb = grader.grade_highlights(body.selected, key, len(sents))
        fb["key"] = key
        sel = set(body.selected)
        ids = [r["id"] for r in con.execute(
            "SELECT id, sentence_idx FROM items WHERE section_id=? AND kind IN ('cloze','mc','tf','open','why')",
            (sec["id"],)) if r["sentence_idx"] in sel]
        fb["practice_ids"] = ids[:20]
        _note(con, sec["topic_id"], sec["id"], "highlight", json.dumps(sorted(sel)), None, fb)
    return fb


class SelfExplainIn(BaseModel):
    section_id: int
    idx: int
    explanation: str


@app.post("/api/self-explain")
def self_explain(body: SelfExplainIn):
    with db.tx() as con:
        sec = get_section(con, body.section_id)
        kw = topic_keywords(con, sec["topic_id"])
        sents = section_sentence_list(sec["text"])
        if not 0 <= body.idx < len(sents):
            raise HTTPException(400, "Índice de oración inválido")
        prev = sents[body.idx - 1] if body.idx > 0 else ""
        fb = grader.grade_self_explanation(sents[body.idx], prev, body.explanation, kw)
        _note(con, sec["topic_id"], sec["id"], "self_explanation", str(body.idx), body.explanation, fb)
    return fb


class NoteIn(BaseModel):
    topic_id: int
    section_id: int | None = None
    technique: str
    ref: str | None = None
    content: str = ""


@app.post("/api/notes")
def add_note(body: NoteIn):
    if body.technique not in ("imagery", "mnemonic", "reread"):
        raise HTTPException(400, "Técnica inválida")
    with db.tx() as con:
        _note(con, body.topic_id, body.section_id, body.technique, body.ref, body.content)
    return {"ok": True}


@app.get("/api/topics/{topic_id}/notes")
def get_notes(topic_id: int, technique: str | None = None):
    with db.tx() as con:
        sql = "SELECT * FROM notes WHERE topic_id=?"
        args: tuple = (topic_id,)
        if technique:
            sql += " AND technique=?"
            args += (technique,)
        rs = db.rows(con.execute(sql + " ORDER BY created_at DESC LIMIT 200", args))
    for r in rs:
        r["feedback"] = json.loads(r["feedback"]) if r["feedback"] else None
    return rs


@app.get("/api/topics/{topic_id}/terms")
def topic_terms(topic_id: int):
    """Términos clave con la oración que los define (para la técnica de palabra clave)."""
    with db.tx() as con:
        kw = topic_keywords(con, topic_id)
        text = "\n".join(r["text"] for r in con.execute("SELECT text FROM sections WHERE topic_id=? ORDER BY ord", (topic_id,)))
        terms = [t for t in tp.key_terms(text, kw, top=30) if tp.term_kind(t) not in ("year", "number")][:14]
        mn = {}
        for r in con.execute("SELECT ref, content FROM notes WHERE topic_id=? AND technique='mnemonic' ORDER BY created_at",
                             (topic_id,)):
            mn[r["ref"]] = r["content"]
        out = []
        for t in terms:
            best = _definition_sentence(con, topic_id, t, kw)
            out.append({"term": t, "sentence": best[2] if best else None, "mnemonic": mn.get(t)})
    return out


@app.get("/api/topics/{topic_id}/errors")
def topic_errors(topic_id: int):
    with db.tx() as con:
        rs = [db.item_dict(r) for r in con.execute(
            "SELECT * FROM items WHERE topic_id=? AND last_verdict IN ('incorrect','partial') ORDER BY lapses DESC",
            (topic_id,))]
        meta = meta_for(con, rs) if rs else {"sections": {}}
    return [{"id": r["id"], "kind": r["kind"], "prompt": r["prompt"], "answer": r["answer"],
             "last_answer": r["last_answer"], "context": r["context"], "lapses": r["lapses"],
             "section_title": meta["sections"].get(r["section_id"], {}).get("title")} for r in rs]


# --------------------------------------------------------------------------- #
# Panel
# --------------------------------------------------------------------------- #
@app.get("/api/dashboard")
def dashboard():
    with db.tx() as con:
        eot = end_of_today_utc()
        totals = dict(con.execute(
            "SELECT COUNT(*) AS items, SUM(seen>0) AS seen, SUM(reps>=3) AS mastered,"
            " SUM(due IS NOT NULL AND due<=?) AS due, SUM(last_verdict IN ('incorrect','partial')) AS errors"
            " FROM items", (eot,)).fetchone())
        totals = {k: v or 0 for k, v in totals.items()}
        totals["topics"] = con.execute("SELECT COUNT(*) FROM topics").fetchone()[0]

        since = srs.iso(srs.now() - timedelta(days=30))
        atts = db.rows(con.execute("SELECT verdict, technique, created_at, section_id FROM attempts WHERE created_at>=?",
                                   (since,)))
        notes = db.rows(con.execute("SELECT technique, created_at FROM notes WHERE created_at>=?", (since,)))

        today = datetime.now(LOCAL_TZ).date()
        days = [(today - timedelta(days=i)).isoformat() for i in range(13, -1, -1)]
        per_day = Counter(local_day(a["created_at"]) for a in atts)
        correct_day = Counter(local_day(a["created_at"]) for a in atts if a["verdict"] == "correct")
        active = set(per_day) | {local_day(n["created_at"]) for n in notes}
        streak = 0
        d = today if today.isoformat() in active else today - timedelta(days=1)
        while d.isoformat() in active:
            streak += 1
            d -= timedelta(days=1)

        week = [a for a in atts if local_day(a["created_at"]) >= (today - timedelta(days=6)).isoformat()]
        score = sum({"correct": 1, "partial": 0.5}.get(a["verdict"], 0) for a in week)
        accuracy = round(score / len(week), 2) if week else None

        techniques = Counter(a["technique"] for a in atts) + Counter(n["technique"] for n in notes)

        sec_stats = defaultdict(lambda: [0, 0.0])
        for a in atts:
            if a["section_id"]:
                sec_stats[a["section_id"]][0] += 1
                sec_stats[a["section_id"]][1] += {"correct": 1, "partial": 0.5}.get(a["verdict"], 0)
        weak = []
        for sid, (cnt, sc) in sec_stats.items():
            if cnt >= 3 and sc / cnt < 0.75:
                weak.append((sid, round(sc / cnt, 2), cnt))
        weak.sort(key=lambda w: w[1])
        weak_out = []
        for sid, acc, cnt in weak[:5]:
            r = con.execute("SELECT se.id, se.title, t.title AS topic, t.id AS topic_id, t.hue FROM sections se"
                            " JOIN topics t ON t.id=se.topic_id WHERE se.id=?", (sid,)).fetchone()
            if r:
                weak_out.append({**dict(r), "accuracy": acc, "attempts": cnt})

        pomo = _pomodoro_stats(con)
        limit_day = (today + timedelta(days=7)).isoformat()
        urgent = [_task_out(r) for r in db.rows(con.execute(
            "SELECT * FROM tasks WHERE done=0 AND due_date<=? ORDER BY due_date LIMIT 6", (limit_day,)))]

    return {
        "totals": totals, "streak": streak, "accuracy_7d": accuracy,
        "activity": [{"day": d, "count": per_day.get(d, 0), "correct": correct_day.get(d, 0)} for d in days],
        "techniques": techniques, "weak_sections": weak_out,
        "pomodoros": pomo, "urgent_tasks": urgent,
    }


# --------------------------------------------------------------------------- #
# Exportar a PDF
# --------------------------------------------------------------------------- #
@app.get("/api/topics/{topic_id}/export.pdf")
def export_topic_pdf(topic_id: int, level: str = "mixto", layout: str = "examen", max_per_section: int = 12):
    from . import export_pdf  # importación diferida: reportlab solo se carga al exportar

    layout = layout if layout in ("examen", "estudio") else "examen"
    with db.tx() as con:
        t = db.row(con.execute("SELECT id, title FROM topics WHERE id=?", (topic_id,)).fetchone())
        if not t:
            raise HTTPException(404, "Tema no encontrado")
        srcs = db.rows(con.execute("SELECT name, title, url, license FROM sources WHERE topic_id=?", (topic_id,)))
        secs = db.rows(con.execute("SELECT id, title FROM sections WHERE topic_id=? ORDER BY ord", (topic_id,)))
        items = [db.item_dict(r) for r in con.execute(
            "SELECT * FROM items WHERE topic_id=? ORDER BY section_id, sentence_idx, id", (topic_id,))]
    wanted = {"basico": {1}, "intermedio": {2}, "avanzado": {3}}.get(level)
    per_section: dict[int, list[dict]] = defaultdict(list)
    for sec in secs:
        cands = [i for i in items if i["section_id"] == sec["id"] and (not wanted or (i.get("level") or 2) in wanted)]
        # una pregunta por oración (para no repetir) y variando el tipo de pregunta
        by_sent: dict = defaultdict(list)
        for it in cands:
            by_sent[it["sentence_idx"] if it["sentence_idx"] is not None else f"x{it['id']}"].append(it)
        used = Counter()
        for group in by_sent.values():
            choice = min(group, key=lambda i: (used[i["kind"]], i["id"]))
            used[choice["kind"]] += 1
            per_section[sec["id"]].append(choice)
            if len(per_section[sec["id"]]) >= max(1, min(max_per_section, 40)):
                break
    label = {"basico": "Nivel básico", "intermedio": "Nivel intermedio", "avanzado": "Nivel avanzado"}.get(
        level, "Todos los niveles")
    pdf = export_pdf.build_pdf(t, srcs, secs, per_section, layout, label)
    safe = re.sub(r"[^A-Za-z0-9_-]+", "_", tp.strip_accents(t["title"])).strip("_") or "tema"
    return Response(pdf, media_type="application/pdf",
                    headers={"Content-Disposition": f'attachment; filename="{safe}_preguntas.pdf"'})


# --------------------------------------------------------------------------- #
# Tareas (día, mes, año) y pomodoros
# --------------------------------------------------------------------------- #
class TaskIn(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    notes: str | None = None
    horizon: str = "dia"  # dia | mes | anio
    due_date: str  # AAAA-MM-DD
    topic_id: int | None = None


class TaskPatch(BaseModel):
    title: str | None = None
    notes: str | None = None
    horizon: str | None = None
    due_date: str | None = None
    done: bool | None = None
    topic_id: int | None = None


def _valid_date(d: str) -> str:
    try:
        return datetime.strptime(d, "%Y-%m-%d").date().isoformat()
    except ValueError as e:
        raise HTTPException(400, "La fecha tiene que tener el formato AAAA-MM-DD.") from e


def _task_out(r: dict) -> dict:
    today = datetime.now(LOCAL_TZ).date()
    due = datetime.strptime(r["due_date"], "%Y-%m-%d").date()
    created = datetime.fromisoformat(r["created_at"]).astimezone(LOCAL_TZ).date()
    r["days_left"] = (due - today).days
    r["days_total"] = max(1, (due - created).days)
    r["done"] = bool(r["done"])
    return r


@app.get("/api/tasks")
def list_tasks(horizon: str | None = None):
    with db.tx() as con:
        sql = ("SELECT tk.*, t.title AS topic_title, t.hue AS topic_hue FROM tasks tk "
               "LEFT JOIN topics t ON t.id = tk.topic_id")
        args: tuple = ()
        if horizon in ("dia", "mes", "anio"):
            sql += " WHERE tk.horizon=?"
            args = (horizon,)
        rs = db.rows(con.execute(sql + " ORDER BY tk.done, tk.due_date, tk.id", args))
    return [_task_out(r) for r in rs]


@app.post("/api/tasks")
def create_task(body: TaskIn):
    if body.horizon not in ("dia", "mes", "anio"):
        raise HTTPException(400, "Periodo inválido")
    with db.tx() as con:
        cur = con.execute("INSERT INTO tasks(title, notes, horizon, due_date, topic_id, created_at) VALUES(?,?,?,?,?,?)",
                          (body.title.strip(), body.notes, body.horizon, _valid_date(body.due_date),
                           body.topic_id, now_iso()))
        r = db.row(con.execute("SELECT * FROM tasks WHERE id=?", (cur.lastrowid,)).fetchone())
    return _task_out(r)


@app.patch("/api/tasks/{task_id}")
def update_task(task_id: int, body: TaskPatch):
    fields, args = [], []
    data = body.model_dump(exclude_unset=True)
    for k, v in data.items():
        if k == "due_date":
            v = _valid_date(v)
        if k == "horizon" and v not in ("dia", "mes", "anio"):
            raise HTTPException(400, "Periodo inválido")
        if k == "done":
            fields.append("done_at=?")
            args.append(now_iso() if v else None)
            v = 1 if v else 0
        fields.append(f"{k}=?")
        args.append(v)
    with db.tx() as con:
        if fields:
            con.execute(f"UPDATE tasks SET {', '.join(fields)} WHERE id=?", (*args, task_id))
        r = db.row(con.execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone())
    if not r:
        raise HTTPException(404, "Tarea no encontrada")
    return _task_out(r)


@app.delete("/api/tasks/{task_id}")
def delete_task(task_id: int):
    with db.tx() as con:
        con.execute("DELETE FROM tasks WHERE id=?", (task_id,))
    return {"ok": True}


class PomodoroIn(BaseModel):
    minutes: float = Field(gt=0, le=180)
    task_id: int | None = None


def _pomodoro_stats(con) -> dict:
    today = datetime.now(LOCAL_TZ).date().isoformat()
    since = srs.iso(srs.now() - timedelta(days=8))
    rs = db.rows(con.execute("SELECT minutes, created_at FROM pomodoros WHERE created_at>=?", (since,)))
    todays = [r for r in rs if local_day(r["created_at"]) == today]
    return {"today": len(todays), "minutes_today": round(sum(r["minutes"] for r in todays)),
            "week": len(rs)}


@app.post("/api/pomodoros")
def add_pomodoro(body: PomodoroIn):
    with db.tx() as con:
        con.execute("INSERT INTO pomodoros(task_id, minutes, created_at) VALUES(?,?,?)",
                    (body.task_id, body.minutes, now_iso()))
        if body.task_id:
            con.execute("UPDATE tasks SET pomodoros=pomodoros+1 WHERE id=?", (body.task_id,))
        return _pomodoro_stats(con)


@app.get("/api/pomodoros/stats")
def pomodoro_stats():
    with db.tx() as con:
        return _pomodoro_stats(con)


# --------------------------------------------------------------------------- #
# Frontend
# --------------------------------------------------------------------------- #
app.mount("/static", StaticFiles(directory=STATIC), name="static")


@app.get("/")
def index():
    return FileResponse(STATIC / "index.html", headers={"Cache-Control": "no-cache"})


@app.get("/api/health")
def health():
    return {"ok": True}
