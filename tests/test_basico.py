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


if __name__ == "__main__":
    unittest.main()
