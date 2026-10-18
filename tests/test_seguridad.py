"""Pruebas de seguridad del login: inyección SQL, sesiones, aislamiento y fuerza bruta."""
import os
import tempfile
import unittest

os.environ.setdefault("DB_PATH", os.path.join(tempfile.mkdtemp(), "test.db"))
os.environ.setdefault("AUTH", "0")

from fastapi.testclient import TestClient  # noqa: E402

from app import auth, main  # noqa: E402
from app.main import app  # noqa: E402

INYECCIONES = ["admin' OR '1'='1", "' OR 1=1 --", "x'; DROP TABLE users; --", "\" OR \"\"=\"", "admin'--"]


class TestLogin(unittest.TestCase):
    def setUp(self):
        self.prev = main.AUTH_ENABLED
        main.AUTH_ENABLED = True
        auth._fails.clear()

    def tearDown(self):
        main.AUTH_ENABLED = self.prev

    def nuevo(self, c, user, pw="clave-segura-123"):
        r = c.post("/api/auth/register", json={"username": user, "password": pw})
        self.assertEqual(r.status_code, 200, r.text)
        return r

    def test_requiere_sesion(self):
        with TestClient(app) as c:
            self.assertEqual(c.get("/api/topics").status_code, 401)
            self.assertEqual(c.get("/api/health").status_code, 200)

    def test_registro_login_y_cookie_segura(self):
        with TestClient(app) as c:
            r = self.nuevo(c, "ana_1")
            cookie = r.headers["set-cookie"].lower()
            self.assertIn("httponly", cookie)
            self.assertIn("samesite=lax", cookie)
            self.assertEqual(c.get("/api/topics").status_code, 200)
            c.post("/api/auth/logout")
            self.assertEqual(c.get("/api/topics").status_code, 401)
            self.assertEqual(c.post("/api/auth/login", json={"username": "ana_1", "password": "clave-segura-123"}).status_code, 200)

    def test_inyeccion_sql_en_login(self):
        with TestClient(app) as c:
            self.nuevo(c, "victima")
            c.cookies.clear()
            for payload in INYECCIONES:
                auth._fails.clear()
                for user, pw in ((payload, "loquesea123"), ("victima", payload), (payload, payload)):
                    r = c.post("/api/auth/login", json={"username": user, "password": pw})
                    self.assertIn(r.status_code, (401, 429), (user, pw, r.text))
            # la tabla de usuarios sigue intacta
            self.assertGreaterEqual(auth.users_count(), 1)
            r = c.post("/api/auth/register", json={"username": "x'; DROP TABLE users; --", "password": "clave-segura-123"})
            self.assertEqual(r.status_code, 400)  # nombre inválido: ni siquiera llega a la base

    def test_inyeccion_en_datos_se_guarda_como_texto(self):
        with TestClient(app) as c:
            self.nuevo(c, "carlos")
            titulo = "Tema'); DROP TABLE topics; --"
            texto = " ".join(["La fotosíntesis convierte la energía de la luz en energía química."] * 8)
            r = c.post("/api/topics", json={"title": titulo, "notes": {"title": titulo, "text": texto}})
            self.assertEqual(r.status_code, 200, r.text)
            temas = c.get("/api/topics").json()
            self.assertEqual(temas[0]["title"], titulo)
            r = c.post("/api/tasks", json={"title": "' OR 1=1 --", "horizon": "dia", "due_date": "2099-01-01"})
            self.assertEqual(r.status_code, 200)
            self.assertEqual(r.json()["title"], "' OR 1=1 --")

    def test_aislamiento_entre_usuarios(self):
        with TestClient(app) as a, TestClient(app) as b:
            self.nuevo(a, "usuario_a")
            self.nuevo(b, "usuario_b")
            texto = " ".join(["Los punteros guardan direcciones de memoria de otras variables en C++."] * 8)
            tid = a.post("/api/topics", json={"title": "Privado", "notes": {"title": "P", "text": texto}}).json()["id"]
            self.assertEqual([t["title"] for t in b.get("/api/topics").json()], [])
            self.assertEqual(b.get(f"/api/topics/{tid}").status_code, 404)
            nid = a.post("/api/notebook", json={"title": "Secreto", "content": "solo mío"}).json()["id"]
            self.assertEqual(b.get("/api/notebook").json(), [])
            self.assertEqual(b.get(f"/api/notebook/{nid}").status_code, 404)
            self.assertEqual(b.delete(f"/api/notebook/{nid}").status_code, 404)
            self.assertEqual(a.get(f"/api/notebook/{nid}").json()["content"], "solo mío")
            mid = a.post("/api/maps", json={"title": "Mapa privado", "data": {"nodes": [], "edges": []}}).json()["id"]
            self.assertEqual(b.get("/api/maps").json(), [])
            self.assertEqual(b.get(f"/api/maps/{mid}").status_code, 404)
            self.assertEqual(b.get(f"/api/game/questions?topic_ids={tid}").json()["questions"], [])

    def test_fuerza_bruta(self):
        with TestClient(app) as c:
            self.nuevo(c, "beto")
            c.cookies.clear()
            codes = [c.post("/api/auth/login", json={"username": "beto", "password": f"mala-{i}-xxxx"}).status_code
                     for i in range(7)]
            self.assertEqual(codes[:5], [401] * 5)
            self.assertEqual(codes[-1], 429)
            # aun con la contraseña correcta queda bloqueado por un rato
            r = c.post("/api/auth/login", json={"username": "beto", "password": "clave-segura-123"})
            self.assertEqual(r.status_code, 429)

    def test_contrasenas_debiles_y_hash(self):
        with TestClient(app) as c:
            self.assertEqual(c.post("/api/auth/register", json={"username": "dani", "password": "corta"}).status_code, 400)
        h = auth.hash_password("clave-segura-123")
        self.assertTrue(h.startswith("scrypt$"))
        self.assertNotIn("clave-segura-123", h)
        self.assertTrue(auth.verify_password("clave-segura-123", h))
        self.assertFalse(auth.verify_password("otra-clave-123", h))


if __name__ == "__main__":
    unittest.main()
