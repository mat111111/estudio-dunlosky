"""Persistencia en SQLite (un archivo en /data, montado como volumen de Docker)."""
from __future__ import annotations

import contextvars
import json
import os
import sqlite3
from contextlib import contextmanager

DB_PATH = os.environ.get("DB_PATH", "/data/estudio.db")

# En modo público cada visitante tiene su propio archivo de base de datos.
# El middleware de main.py fija la ruta para cada request con esta variable de contexto.
_current_path: contextvars.ContextVar[str | None] = contextvars.ContextVar("db_path", default=None)
_initialized: set[str] = set()


def use_path(path: str):
    return _current_path.set(path)


def reset_path(token) -> None:
    _current_path.reset(token)

SCHEMA = """
PRAGMA journal_mode=WAL;
CREATE TABLE IF NOT EXISTS topics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    lang TEXT DEFAULT 'es',
    hue INTEGER DEFAULT 220,
    keywords TEXT DEFAULT '{}',
    ai_status TEXT DEFAULT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS sources (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    topic_id INTEGER NOT NULL REFERENCES topics(id) ON DELETE CASCADE,
    name TEXT, title TEXT, url TEXT, revid INTEGER, revised_at TEXT, license TEXT,
    retrieved_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS sections (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    topic_id INTEGER NOT NULL REFERENCES topics(id) ON DELETE CASCADE,
    source_id INTEGER REFERENCES sources(id) ON DELETE CASCADE,
    ord INTEGER NOT NULL,
    title TEXT NOT NULL,
    text TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    topic_id INTEGER NOT NULL REFERENCES topics(id) ON DELETE CASCADE,
    section_id INTEGER REFERENCES sections(id) ON DELETE CASCADE,
    sentence_idx INTEGER,
    kind TEXT NOT NULL,
    prompt TEXT NOT NULL,
    answer TEXT NOT NULL,
    options TEXT,
    context TEXT,
    hint TEXT,
    term_kind TEXT,
    origin TEXT DEFAULT 'auto',
    level INTEGER DEFAULT 2,
    ease REAL DEFAULT 2.5,
    interval REAL DEFAULT 0,
    reps INTEGER DEFAULT 0,
    lapses INTEGER DEFAULT 0,
    due TEXT,
    seen INTEGER DEFAULT 0,
    correct INTEGER DEFAULT 0,
    last_verdict TEXT,
    last_answer TEXT,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_items_topic ON items(topic_id);
CREATE INDEX IF NOT EXISTS idx_items_due ON items(due);
CREATE TABLE IF NOT EXISTS attempts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    item_id INTEGER REFERENCES items(id) ON DELETE CASCADE,
    topic_id INTEGER REFERENCES topics(id) ON DELETE CASCADE,
    section_id INTEGER,
    technique TEXT,
    answer TEXT,
    verdict TEXT,
    score REAL,
    prev_state TEXT,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_attempts_date ON attempts(created_at);
CREATE TABLE IF NOT EXISTS notes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    topic_id INTEGER REFERENCES topics(id) ON DELETE CASCADE,
    section_id INTEGER,
    technique TEXT NOT NULL,
    ref TEXT,
    content TEXT,
    feedback TEXT,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT);
CREATE TABLE IF NOT EXISTS tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    notes TEXT,
    horizon TEXT NOT NULL DEFAULT 'dia',
    due_date TEXT NOT NULL,
    topic_id INTEGER REFERENCES topics(id) ON DELETE SET NULL,
    done INTEGER DEFAULT 0,
    done_at TEXT,
    pomodoros INTEGER DEFAULT 0,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS pomodoros (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id INTEGER REFERENCES tasks(id) ON DELETE SET NULL,
    minutes REAL NOT NULL,
    created_at TEXT NOT NULL
);
"""

MIGRATIONS = [
    # (tabla, columna, sentencia para agregarla, sentencia para completar datos existentes)
    ("items", "level", "ALTER TABLE items ADD COLUMN level INTEGER DEFAULT 2",
     "UPDATE items SET level = CASE kind WHEN 'tf' THEN 1 WHEN 'mc' THEN 1 WHEN 'why' THEN 3 "
     "WHEN 'relate' THEN 3 ELSE 2 END"),
]


def _migrate(con: sqlite3.Connection) -> None:
    """Actualiza bases de datos creadas con versiones anteriores de la app."""
    for table, column, add_sql, fill_sql in MIGRATIONS:
        cols = {r[1] for r in con.execute(f"PRAGMA table_info({table})")}
        if column not in cols:
            con.execute(add_sql)
            if fill_sql:
                con.execute(fill_sql)
            con.commit()


def connect() -> sqlite3.Connection:
    path = _current_path.get() or DB_PATH
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    con = sqlite3.connect(path, timeout=15)
    con.row_factory = sqlite3.Row
    if path not in _initialized:  # crea las tablas la primera vez que se usa el archivo
        con.executescript(SCHEMA)
        _migrate(con)
        _initialized.add(path)
    con.execute("PRAGMA foreign_keys=ON")
    return con


def init() -> None:
    connect().close()


@contextmanager
def tx():
    con = connect()
    try:
        yield con
        con.commit()
    finally:
        con.close()


def row(r: sqlite3.Row | None) -> dict | None:
    return dict(r) if r is not None else None


def rows(rs) -> list[dict]:
    return [dict(r) for r in rs]


def get_setting(con, key: str, default: str | None = None) -> str | None:
    r = con.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
    return r["value"] if r else default


def set_setting(con, key: str, value: str | None) -> None:
    if value is None:
        con.execute("DELETE FROM settings WHERE key=?", (key,))
    else:
        con.execute("INSERT INTO settings(key, value) VALUES(?, ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                    (key, value))


def item_dict(r) -> dict:
    d = dict(r)
    d["options"] = json.loads(d["options"]) if d.get("options") else None
    return d
