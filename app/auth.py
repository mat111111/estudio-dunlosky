"""Cuentas de usuario y sesiones.

Seguridad:
  - Todas las consultas usan parámetros (?) de sqlite3: el texto que escribe el usuario nunca
    se concatena dentro del SQL, así que no hay inyección SQL posible.
  - Las contraseñas se guardan con scrypt (función lenta y con sal aleatoria por usuario),
    nunca en texto plano.
  - La sesión es un token aleatorio de 256 bits en una cookie HttpOnly (JavaScript no la puede
    leer) y SameSite=Lax (otros sitios no pueden usarla). En la base solo se guarda su hash.
  - Límite de intentos fallidos por usuario e IP para frenar ataques de fuerza bruta.
  - Cada usuario tiene su propia base de datos: nadie puede ver los temas de otro.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import os
import re
import secrets
import sqlite3
import threading
import time
from datetime import datetime, timedelta, timezone

from . import db

DATA_DIR = os.path.dirname(db.DB_PATH) or "."
AUTH_DB = os.path.join(DATA_DIR, "auth.db")
USERS_DIR = os.path.join(DATA_DIR, "usuarios")
SESSION_COOKIE = "ed_sesion"
SESSION_DAYS = 30
USERNAME_RE = re.compile(r"^[A-Za-z0-9._-]{3,32}$")
MIN_PASSWORD = 8

SCHEMA = """
PRAGMA journal_mode=WAL;
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE COLLATE NOCASE,
    pw_hash TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS sessions (
    token_hash TEXT PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created_at TEXT NOT NULL,
    expires_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_sessions_user ON sessions(user_id);
"""

_init_lock = threading.Lock()
_initialized = False


class AuthError(Exception):
    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.status = status


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.isoformat(timespec="seconds")


def connect() -> sqlite3.Connection:
    global _initialized
    os.makedirs(DATA_DIR, exist_ok=True)
    con = sqlite3.connect(AUTH_DB, timeout=15)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys=ON")
    if not _initialized:
        with _init_lock:
            con.executescript(SCHEMA)
            _initialized = True
    return con


# --------------------------------------------------------------------------- #
# Contraseñas
# --------------------------------------------------------------------------- #
SCRYPT_N, SCRYPT_R, SCRYPT_P = 2 ** 14, 8, 1


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    dk = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=SCRYPT_N, r=SCRYPT_R, p=SCRYPT_P, dklen=32)
    return "scrypt${}${}${}${}${}".format(SCRYPT_N, SCRYPT_R, SCRYPT_P,
                                          base64.b64encode(salt).decode(), base64.b64encode(dk).decode())


def verify_password(password: str, stored: str) -> bool:
    try:
        _, n, r, p, salt_b64, hash_b64 = stored.split("$")
        dk = hashlib.scrypt(password.encode("utf-8"), salt=base64.b64decode(salt_b64),
                            n=int(n), r=int(r), p=int(p), dklen=32)
        return hmac.compare_digest(dk, base64.b64decode(hash_b64))
    except (ValueError, TypeError):
        return False


# Hash de referencia para comparar aunque el usuario no exista (mismo tiempo de respuesta)
_DUMMY_HASH = hash_password(secrets.token_hex(8))


def validate_credentials(username: str, password: str) -> None:
    if not USERNAME_RE.fullmatch(username or ""):
        raise AuthError("El usuario tiene que tener entre 3 y 32 caracteres: letras sin tilde, números, punto, guion o guion bajo.")
    if len(password or "") < MIN_PASSWORD:
        raise AuthError(f"La contraseña tiene que tener al menos {MIN_PASSWORD} caracteres.")
    if len(password) > 256:
        raise AuthError("La contraseña es demasiado larga.")
    if password.lower() == username.lower():
        raise AuthError("La contraseña no puede ser igual al usuario.")


# --------------------------------------------------------------------------- #
# Límite de intentos
# --------------------------------------------------------------------------- #
_fails: dict[str, list[float]] = {}
_fails_lock = threading.Lock()
MAX_FAILS = 5
WINDOW = 15 * 60


def _check_rate(key: str, max_fails: int = MAX_FAILS) -> None:
    with _fails_lock:
        recent = [t for t in _fails.get(key, []) if time.time() - t < WINDOW]
        _fails[key] = recent
        if len(recent) >= max_fails:
            wait = int(WINDOW - (time.time() - recent[0])) // 60 + 1
            raise AuthError(f"Demasiados intentos fallidos. Probá de nuevo en {wait} minutos.", 429)


def _register_fail(key: str) -> None:
    with _fails_lock:
        _fails.setdefault(key, []).append(time.time())


def _clear_fails(key: str) -> None:
    with _fails_lock:
        _fails.pop(key, None)


# --------------------------------------------------------------------------- #
# Usuarios y sesiones
# --------------------------------------------------------------------------- #
def user_db_path(user_id: int) -> str:
    return os.path.join(USERS_DIR, f"{int(user_id)}.db")


def users_count() -> int:
    con = connect()
    try:
        return con.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    finally:
        con.close()


def _adopt_legacy_data(user_id: int) -> None:
    """El primer usuario hereda los temas y el progreso que había antes de existir el login."""
    legacy = db.DB_PATH
    target = user_db_path(user_id)
    if not os.path.exists(legacy) or os.path.exists(target):
        return
    os.makedirs(USERS_DIR, exist_ok=True)
    src = sqlite3.connect(legacy)
    dst = sqlite3.connect(target)
    try:
        src.backup(dst)  # copia consistente aunque la base esté en modo WAL
    finally:
        dst.close()
        src.close()


def register(username: str, password: str) -> int:
    username = (username or "").strip()
    validate_credentials(username, password)
    con = connect()
    try:
        first = con.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 0
        try:
            cur = con.execute("INSERT INTO users(username, pw_hash, created_at) VALUES(?,?,?)",
                              (username, hash_password(password), _iso(_now())))
        except sqlite3.IntegrityError as e:
            raise AuthError("Ese nombre de usuario ya existe.", 409) from e
        con.commit()
        user_id = cur.lastrowid
    finally:
        con.close()
    if first:
        _adopt_legacy_data(user_id)
    return user_id


def authenticate(username: str, password: str, ip: str) -> int:
    username = (username or "").strip()
    key = f"{ip}|{username.lower()}"
    _check_rate(key)
    _check_rate(f"{ip}|*", MAX_FAILS * 4)  # límite más amplio por IP (varias cuentas)
    con = connect()
    try:
        row = con.execute("SELECT id, pw_hash FROM users WHERE username = ?", (username,)).fetchone()
    finally:
        con.close()
    ok = verify_password(password or "", row["pw_hash"] if row else _DUMMY_HASH)
    if not row or not ok:
        _register_fail(key)
        _register_fail(f"{ip}|*")
        raise AuthError("Usuario o contraseña incorrectos.", 401)
    _clear_fails(key)
    return row["id"]


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def create_session(user_id: int) -> str:
    token = secrets.token_urlsafe(32)
    con = connect()
    try:
        con.execute("DELETE FROM sessions WHERE expires_at < ?", (_iso(_now()),))
        con.execute("INSERT INTO sessions(token_hash, user_id, created_at, expires_at) VALUES(?,?,?,?)",
                    (_token_hash(token), user_id, _iso(_now()), _iso(_now() + timedelta(days=SESSION_DAYS))))
        con.commit()
    finally:
        con.close()
    return token


def user_from_token(token: str | None) -> dict | None:
    if not token or len(token) > 200:
        return None
    con = connect()
    try:
        row = con.execute(
            "SELECT u.id, u.username FROM sessions s JOIN users u ON u.id = s.user_id "
            "WHERE s.token_hash = ? AND s.expires_at > ?", (_token_hash(token), _iso(_now()))).fetchone()
    finally:
        con.close()
    return dict(row) if row else None


def delete_session(token: str | None) -> None:
    if not token:
        return
    con = connect()
    try:
        con.execute("DELETE FROM sessions WHERE token_hash = ?", (_token_hash(token),))
        con.commit()
    finally:
        con.close()


def change_password(user_id: int, current: str, new: str) -> None:
    con = connect()
    try:
        row = con.execute("SELECT username, pw_hash FROM users WHERE id = ?", (user_id,)).fetchone()
        if not row or not verify_password(current or "", row["pw_hash"]):
            raise AuthError("La contraseña actual no es correcta.", 401)
        validate_credentials(row["username"], new)
        con.execute("UPDATE users SET pw_hash = ? WHERE id = ?", (hash_password(new), user_id))
        con.execute("DELETE FROM sessions WHERE user_id = ?", (user_id,))  # cierra las otras sesiones
        con.commit()
    finally:
        con.close()


def reset_password(username: str, new: str) -> None:
    """Uso administrativo (desde la terminal del servidor): cambia la contraseña sin pedir la anterior."""
    username = (username or "").strip()
    con = connect()
    try:
        row = con.execute("SELECT id, username FROM users WHERE username = ?", (username,)).fetchone()
        if not row:
            raise AuthError("No existe ese usuario.", 404)
        validate_credentials(row["username"], new)
        con.execute("UPDATE users SET pw_hash = ? WHERE id = ?", (hash_password(new), row["id"]))
        con.execute("DELETE FROM sessions WHERE user_id = ?", (row["id"],))
        con.commit()
    finally:
        con.close()


def _cli(argv: list[str]) -> int:
    """python -m app.auth usuarios | python -m app.auth reset <usuario>"""
    import getpass
    if argv[:1] == ["usuarios"]:
        con = connect()
        try:
            for r in con.execute("SELECT username, created_at FROM users ORDER BY id"):
                print(f"{r['username']}\t(creado {r['created_at']})")
        finally:
            con.close()
        return 0
    if len(argv) == 2 and argv[0] == "reset":
        new = getpass.getpass("Nueva contraseña: ")
        if new != getpass.getpass("Repetila: "):
            print("No coinciden.")
            return 1
        try:
            reset_password(argv[1], new)
        except AuthError as e:
            print(e)
            return 1
        print("Listo. Ya podés entrar con la nueva contraseña.")
        return 0
    print("Uso:\n  python -m app.auth usuarios          lista las cuentas\n"
          "  python -m app.auth reset USUARIO     cambia la contraseña de USUARIO")
    return 2


if __name__ == "__main__":
    import sys
    raise SystemExit(_cli(sys.argv[1:]))
