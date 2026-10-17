"""Pruebas de los buscadores con respuestas simuladas (no necesitan internet).

Las respuestas imitan el formato documentado de cada API.
"""
import asyncio
import json
import unittest

import httpx

from app import search_providers as sp
from app import sources

ABSTRACT = ("La fotosíntesis es el proceso por el cual las plantas transforman la energía de la luz en energía "
            "química. Este trabajo analiza cómo la temperatura y la disponibilidad de agua modifican la eficiencia "
            "del proceso en cultivos de maíz de la región pampeana.")


def inverted(text):
    inv = {}
    for i, w in enumerate(text.split()):
        inv.setdefault(w, []).append(i)
    return inv


ARXIV_XML = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry>
    <id>http://arxiv.org/abs/2401.01234v2</id>
    <published>2024-01-03T10:00:00Z</published>
    <title>Round Robin Scheduling
      Revisited</title>
    <summary>  We study the round robin CPU scheduling algorithm and show how the time quantum affects
      response time and throughput in modern operating systems with many interactive processes.  </summary>
    <author><name>Ada Lovelace</name></author>
    <author><name>Alan Turing</name></author>
  </entry>
</feed>"""


def handler(request: httpx.Request) -> httpx.Response:
    url = str(request.url)
    host = request.url.host
    if host == "api.openalex.org":
        if "/works/W1" in url:
            return httpx.Response(200, json={"id": "https://openalex.org/W1", "display_name": "Fotosíntesis en maíz",
                                             "publication_year": 2021, "abstract_inverted_index": inverted(ABSTRACT),
                                             "authorships": [{"author": {"display_name": "Ana Pérez"}}],
                                             "open_access": {"oa_url": None}, "doi": "https://doi.org/10.1/abc"})
        return httpx.Response(200, json={"results": [{"id": "https://openalex.org/W1", "display_name": "Fotosíntesis en maíz",
                                                      "publication_year": 2021, "abstract_inverted_index": inverted(ABSTRACT),
                                                      "primary_location": {"source": {"display_name": "Revista Agro"}},
                                                      "cited_by_count": 12, "language": "es"}]})
    if host == "export.arxiv.org":
        return httpx.Response(200, text=ARXIV_XML)
    if host == "arxiv.org":
        return httpx.Response(404, text="no html")
    if host == "www.ebi.ac.uk":
        return httpx.Response(200, json={"resultList": {"result": [{"id": "123", "source": "MED", "title": "Sueño y memoria",
                                                                      "abstractText": "<h4>Objetivo</h4>" + ABSTRACT, "pubYear": "2020",
                                                                      "journalInfo": {"journal": {"title": "Neuro"}}}]}})
    if host == "api.stackexchange.com":
        if "/answers" in url:
            return httpx.Response(200, json={"items": [{"is_accepted": True, "score": 40, "body":
                "<p>Un puntero guarda la dirección de memoria de otra variable. Para acceder al valor se usa el operador asterisco, "
                "lo que se llama desreferenciar el puntero.</p><pre><code>int x = 5;\nint *p = &amp;x;\n</code></pre>"}]})
        if "/questions/77" in url:
            return httpx.Response(200, json={"items": [{"title": "¿Qué es un puntero en C++?", "link": "https://es.stackoverflow.com/q/77",
                                                        "body": "<p>No entiendo qué es un puntero en C++ ni para qué sirve en la práctica cuando programo arreglos dinámicos.</p>"}]})
        return httpx.Response(200, json={"items": [{"question_id": 77, "title": "¿Qué es un puntero en C++?", "link": "https://es.stackoverflow.com/q/77",
                                                    "score": 15, "answer_count": 3, "is_answered": True,
                                                    "body": "<p>No entiendo qué es un puntero en C++.</p>"}]})
    if host == "api.tavily.com":
        assert request.headers["Authorization"] == "Bearer tvly-test"
        body = json.loads(request.content)
        assert body["query"]
        return httpx.Response(200, json={"results": [{"title": "Punteros en C++", "url": "https://ejemplo.edu/punteros",
                                                      "content": "Un puntero es una variable que guarda una dirección."}]})
    if host == "api.search.brave.com":
        assert request.headers["X-Subscription-Token"] == "brave-test"
        return httpx.Response(200, json={"web": {"results": [{"title": "<strong>Punteros</strong> - Apunte",
                                                               "url": "https://ejemplo.edu/apunte",
                                                               "description": "Qué es un <strong>puntero</strong>."}]}})
    if host == "api.anthropic.com":
        return httpx.Response(200, json={"content": [
            {"type": "server_tool_use", "id": "srv1", "name": "web_search", "input": {"query": "punteros"}},
            {"type": "web_search_tool_result", "tool_use_id": "srv1", "content": [
                {"type": "web_search_result", "url": "https://ejemplo.edu/c", "title": "Punteros", "encrypted_content": "x", "page_age": "2025"}]},
            {"type": "text", "text": "Encontré apuntes."}]})
    return httpx.Response(404)


class FakeClients(unittest.TestCase):
    def setUp(self):
        self._orig_client = sp._client
        self._orig_async = httpx.AsyncClient

        def fake_client(**headers):
            return self._orig_async(transport=httpx.MockTransport(handler), headers=headers)

        class PatchedAsync(self._orig_async):
            def __init__(inner, *a, **kw):
                kw["transport"] = httpx.MockTransport(handler)
                super().__init__(*a, **kw)

        sp._client = fake_client
        httpx.AsyncClient = PatchedAsync
        sp.httpx.AsyncClient = PatchedAsync

    def tearDown(self):
        sp._client = self._orig_client
        httpx.AsyncClient = self._orig_async
        sp.httpx.AsyncClient = self._orig_async

    def run_(self, coro):
        return asyncio.run(coro)

    def test_openalex(self):
        res = self.run_(sp.search("openalex", "fotosíntesis", {}))
        self.assertEqual(res[0]["ref"], "W1")
        self.assertTrue(res[0]["snippet"].startswith("La fotosíntesis"))
        src = self.run_(sp.fetch("openalex", "W1", None, {}))
        self.assertEqual(src["sections"][0]["title"], "Resumen")
        self.assertIn("Ana Pérez", src["source_name"])

    def test_arxiv(self):
        res = self.run_(sp.search("arxiv", "round robin", {}))
        self.assertEqual(res[0]["ref"], "2401.01234v2")
        self.assertEqual(res[0]["title"], "Round Robin Scheduling Revisited")
        src = self.run_(sp.fetch("arxiv", "2401.01234v2", None, {}))
        self.assertIn("round robin", src["sections"][0]["text"])

    def test_europepmc(self):
        res = self.run_(sp.search("europepmc", "sueño", {}))
        self.assertEqual(res[0]["ref"], "MED:123")
        self.assertNotIn("<h4>", res[0]["snippet"])
        src = self.run_(sp.fetch("europepmc", "MED:123", None, {}))
        self.assertTrue(src["sections"])

    def test_stackoverflow(self):
        res = self.run_(sp.search("so_es", "puntero", {}))
        self.assertEqual(res[0]["ref"], "77")
        src = self.run_(sp.fetch("so_es", "77", None, {}))
        titles = [s["title"] for s in src["sections"]]
        self.assertIn("La pregunta", titles)
        self.assertTrue(any("aceptada" in t for t in titles))

    def test_tavily_brave_claude(self):
        t = self.run_(sp.search("tavily", "punteros", {"tavily": "tvly-test"}))
        self.assertEqual(t[0]["url"], "https://ejemplo.edu/punteros")
        b = self.run_(sp.search("brave", "punteros", {"brave": "brave-test"}))
        self.assertEqual(b[0]["title"], "Punteros - Apunte")
        c = self.run_(sp.search("claude_web", "punteros", {"anthropic": "sk-x"}))
        self.assertEqual(c[0]["url"], "https://ejemplo.edu/c")


if __name__ == "__main__":
    unittest.main()
