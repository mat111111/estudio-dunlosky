"""Pruebas básicas: generación de preguntas, corrección y flujo completo de la API.

Ejecutar desde la carpeta del proyecto:  python -m unittest discover tests
(no necesita internet: usa un texto de ejemplo en lugar de Wikipedia)
"""
import os
import tempfile
import unittest
from pathlib import Path

os.environ["DB_PATH"] = os.path.join(tempfile.mkdtemp(), "test.db")

from fastapi.testclient import TestClient  # noqa: E402

from app import generator, grader, sources, srs  # noqa: E402
from app import textproc as tp  # noqa: E402
from app.main import app  # noqa: E402

MUESTRA = (Path(__file__).parent / "muestra_fotosintesis.txt").read_text(encoding="utf-8")


class TestTexto(unittest.TestCase):
    def test_oraciones_respetan_abreviaturas(self):
        s = tp.split_sentences("Nació en el 50 a. C. en Roma. Luego viajó a Grecia, etc. y volvió.")
        self.assertEqual(len(s), 2)

    def test_secciones_descartan_referencias(self):
        secs = sources.parse_sections(sources.clean_extract(MUESTRA), "Fotosíntesis")
        titulos = [s["title"] for s in secs]
        self.assertIn("Fases de la fotosíntesis", titulos)
        self.assertNotIn("Referencias", titulos)


class TestGenerador(unittest.TestCase):
    def setUp(self):
        self.secs = sources.parse_sections(sources.clean_extract(MUESTRA), "Fotosíntesis")
        self.kw, self.items = generator.generate_topic_items(self.secs, "Fotosíntesis", 1)

    def test_hay_varios_tipos(self):
        kinds = {i["kind"] for sec in self.items for i in sec}
        self.assertTrue({"cloze", "mc", "tf", "why"} <= kinds)

    def test_cada_pregunta_esta_anclada_a_la_fuente(self):
        texto = tp.normalize(MUESTRA)
        for sec in self.items:
            for it in sec:
                self.assertIn(tp.normalize(it["context"]), texto)

    def test_opcion_multiple_incluye_la_correcta(self):
        for sec in self.items:
            for it in sec:
                if it["kind"] == "mc":
                    self.assertIn(it["answer"], it["options"])
                    self.assertEqual(len(set(it["options"])), 4)


class TestCorreccion(unittest.TestCase):
    def test_huecos_tolera_acentos_y_errores_menores(self):
        it = {"kind": "cloze", "answer": "oxígeno"}
        self.assertEqual(grader.grade(it, "oxigeno")["verdict"], "correct")
        self.assertEqual(grader.grade(it, "oxijeno")["verdict"], "correct")
        self.assertEqual(grader.grade(it, "carbono")["verdict"], "incorrect")

    def test_anios_exactos(self):
        it = {"kind": "cloze", "answer": "1779"}
        self.assertEqual(grader.grade(it, "1779")["verdict"], "correct")
        self.assertEqual(grader.grade(it, "1780")["verdict"], "incorrect")

    def test_respuesta_abierta_por_conceptos(self):
        it = {"kind": "why", "prompt": "¿Por qué la fotosíntesis es fundamental?",
              "answer": "Porque produce el oxígeno que respiran la mayoría de los seres vivos"}
        self.assertEqual(grader.grade(it, "produce oxígeno para que respiren los seres vivos")["verdict"], "correct")
        self.assertEqual(grader.grade(it, "porque es verde")["verdict"], "incorrect")

    def test_repeticion_espaciada(self):
        s = srs.schedule(2.5, 0, 0, 0, 5)
        self.assertEqual(s["interval"], 1.0)
        s = srs.schedule(s["ease"], s["interval"], s["reps"], s["lapses"], 5)
        self.assertEqual(s["interval"], 3.0)
        mal = srs.schedule(s["ease"], s["interval"], s["reps"], s["lapses"], 1)
        self.assertEqual(mal["reps"], 0)
        self.assertEqual(mal["lapses"], 1)


class TestApi(unittest.TestCase):
    def test_flujo_completo(self):
        with TestClient(app) as c:
            r = c.post("/api/topics", json={"title": "Fotosíntesis", "notes": {"title": "Fotosíntesis", "text": MUESTRA}})
            self.assertEqual(r.status_code, 200, r.text)
            tid = r.json()["id"]
            ses = c.post("/api/session", json={"mode": "practice", "topic_ids": [tid], "n": 6}).json()
            self.assertEqual(len(ses["items"]), 6)
            self.assertNotIn("answer", ses["items"][0])  # la respuesta nunca viaja antes de responder
            item = ses["items"][0]
            res = c.post("/api/answer", json={"item_id": item["id"], "answer": "respuesta equivocada"}).json()
            self.assertIn(res["verdict"], ("incorrect", "partial"))
            self.assertTrue(res["context"])
            err = c.post("/api/session", json={"mode": "errors", "topic_ids": [tid]}).json()
            self.assertEqual(err["items"][0]["id"], item["id"])
            review = c.post("/api/session", json={"mode": "review"}).json()
            self.assertTrue(any(i["id"] == item["id"] for i in review["items"]))
            d = c.get("/api/dashboard").json()
            self.assertEqual(d["totals"]["errors"], 1)


class TestNuevasFunciones(unittest.TestCase):
    def test_niveles_de_complejidad(self):
        with TestClient(app) as c:
            tid = c.post("/api/topics", json={"title": "Niveles", "notes": {"title": "N", "text": MUESTRA}}).json()["id"]
            for nivel, esperado in (("basico", 1), ("intermedio", 2), ("avanzado", 3)):
                its = c.post("/api/session", json={"mode": "practice", "topic_ids": [tid], "n": 4, "level": nivel}).json()["items"]
                self.assertTrue(its)
                self.assertTrue(all(i["level"] == esperado for i in its), nivel)

    def test_exportar_pdf(self):
        with TestClient(app) as c:
            tid = c.post("/api/topics", json={"title": "PDF", "notes": {"title": "P", "text": MUESTRA}}).json()["id"]
            for layout in ("examen", "estudio"):
                r = c.get(f"/api/topics/{tid}/export.pdf?layout={layout}")
                self.assertEqual(r.status_code, 200)
                self.assertTrue(r.content.startswith(b"%PDF"))

    def test_tareas_y_pomodoros(self):
        with TestClient(app) as c:
            t = c.post("/api/tasks", json={"title": "Parcial", "horizon": "mes", "due_date": "2099-01-10"}).json()
            self.assertFalse(t["done"])
            c.post("/api/pomodoros", json={"minutes": 25, "task_id": t["id"]})
            tareas = c.get("/api/tasks?horizon=mes").json()
            self.assertEqual(tareas[0]["pomodoros"], 1)
            self.assertTrue(c.patch(f"/api/tasks/{t['id']}", json={"done": True}).json()["done"])
            self.assertEqual(c.post("/api/tasks", json={"title": "x", "due_date": "10/10/2026"}).status_code, 400)

    def test_extraer_texto_de_pagina_web(self):
        html = ("<html><head><title>Punteros - Cátedra</title></head><body><nav><p>Menú del sitio con muchos enlaces</p></nav>"
                "<article><h1>Punteros</h1><p>" + "Un puntero almacena la dirección de memoria de otra variable. " * 4 +
                "</p><h2>Aritmética</h2><p>" + "Sumar uno a un puntero avanza según el tamaño del tipo apuntado. " * 4 +
                "</p></article></body></html>")
        titulo, texto = sources.html_to_text(html)
        self.assertEqual(titulo, "Punteros")
        self.assertNotIn("Menú", texto)
        secs = sources.parse_sections(texto, titulo, 20)
        self.assertEqual([s["title"] for s in secs], ["Introducción", "Aritmética"])

    def test_no_descarga_direcciones_internas(self):
        with self.assertRaises(sources.SourceError):
            sources._check_public_host("http://127.0.0.1:8000/")


if __name__ == "__main__":
    unittest.main()
