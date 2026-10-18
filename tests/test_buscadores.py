"""Pruebas de los buscadores con respuestas simuladas (no necesitan internet).

Las respuestas imitan el formato documentado de cada API.
"""
import asyncio
import json
import unittest

import httpx

from app import search_providers as sp
from app import sources
from app import videos

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
    if host == "buscador":
        params = dict(request.url.params)
        assert params["format"] == "json"
        if params["categories"] == "videos":
            return httpx.Response(200, json={"results": [
                {"url": "https://www.youtube.com/watch?v=sxsxsxsxsx1", "title": "Modelo OSI explicado", "author": "Redes 101",
                 "length": "0:15:20", "thumbnail": "https://i.ytimg.com/vi/sxsxsxsxsx1/hqdefault.jpg", "content": "Las 7 capas"},
                {"url": "https://www.youtube.com/watch?v=sxsxsxsxsx2", "title": "Corto", "length": 60},
                {"url": "https://www.dailymotion.com/video/x1", "title": "Otro sitio"}]})
        return httpx.Response(200, json={"results": [
            {"url": "https://ejemplo.edu/osi", "title": "El modelo OSI", "content": "Siete capas...", "engines": ["google", "bing", "duckduckgo"]},
            {"url": "https://ejemplo.edu/osi", "title": "Duplicado", "content": "", "engines": ["brave"]},
            {"url": "javascript:alert(1)", "title": "Malicioso", "content": ""}]})
    if host == "api.marginalia.nu":
        assert "/public/search/" in url
        return httpx.Response(200, json={"query": "x", "results": [{"url": "https://blog.ej/rr", "title": "Round robin notes", "description": "My notes"}]})
    if host == "hn.algolia.com":
        return httpx.Response(200, json={"hits": [{"title": "How TCP works", "url": "https://ej.com/tcp", "points": 300, "num_comments": 80, "created_at": "2021-01-01T00:00:00Z"},
                                                  {"title": "Ask HN", "url": None}]})
    if host == "api.exa.ai":
        assert request.headers["x-api-key"] == "exa-test"
        return httpx.Response(200, json={"results": [{"title": "Guía de punteros", "url": "https://ej.com/p", "text": "Un puntero...", "publishedDate": "2023-02-01T00:00:00Z"}]})
    if host == "developer.mozilla.org":
        return httpx.Response(200, json={"documents": [{"mdn_url": "/es/docs/Web/JavaScript/Closures", "title": "Closures", "summary": "Una clausura es...", "locale": "es"}]})
    if host == "api.semanticscholar.org":
        paper = {"paperId": "abc123", "title": "Sleep and memory", "abstract": ABSTRACT, "year": 2020, "venue": "Neuro",
                 "citationCount": 50, "url": "https://www.semanticscholar.org/paper/abc123", "authors": [{"name": "J. Doe"}]}
        if "/paper/search" in url:
            return httpx.Response(200, json={"data": [paper, {**paper, "paperId": "noabs", "abstract": None}]})
        return httpx.Response(200, json=paper)
    if host == "api.crossref.org":
        item = {"DOI": "10.1/xyz", "title": ["Fotosíntesis en maíz"], "abstract": "<jats:title>Resumen</jats:title><jats:p>" + ABSTRACT + "</jats:p>",
                "container-title": ["Revista Agro"], "issued": {"date-parts": [[2019, 5]]}, "URL": "https://doi.org/10.1/xyz",
                "author": [{"given": "Ana", "family": "Pérez"}]}
        if "/works/10.1/xyz" in url:
            return httpx.Response(200, json={"message": item})
        return httpx.Response(200, json={"message": {"items": [item]}})
    if host == "doaj.org":
        art = {"id": "d1", "bibjson": {"title": "Aprendizaje espaciado", "abstract": ABSTRACT, "year": "2022",
                                       "journal": {"title": "Revista Educación"}, "link": [{"type": "fulltext", "url": "https://revista.edu/a.pdf"}],
                                       "author": [{"name": "Luis Gómez"}]}}
        if "/api/articles/d1" in url:
            return httpx.Response(200, json=art)
        return httpx.Response(200, json={"results": [art]})
    if host == "openlibrary.org":
        if url.endswith("/works/OL123W.json"):
            return httpx.Response(200, json={"title": "Estructuras de datos", "description": {"type": "/type/text", "value": ABSTRACT + " " + ABSTRACT},
                                             "subjects": ["Algoritmos", "Programación"]})
        return httpx.Response(200, json={"docs": [{"key": "/works/OL123W", "title": "Estructuras de datos", "author_name": ["N. Wirth"],
                                                   "first_publish_year": 1976, "subject": ["Algoritmos"]}]})
    if host == "google.serper.dev":
        assert request.headers["X-API-KEY"] == "serper-test"
        body = json.loads(request.content)
        if request.url.path == "/scholar":
            return httpx.Response(200, json={"organic": [{"title": "Planificación de procesos", "link": "https://repo.edu/tesis",
                                                          "publicationInfo": "J Gómez - 2019 - repo.edu", "year": 2019,
                                                          "citedBy": 8, "snippet": "Se comparan algoritmos de planificación."}]})
        if request.url.path == "/videos":
            return httpx.Response(200, json={"videos": [
                {"title": "Round Robin explicado", "link": "https://www.youtube.com/watch?v=abcdefghijk", "channel": "Profe X",
                 "duration": "12:05", "date": "hace 2 años", "snippet": "Explicación con ejemplos"},
                {"title": "Short", "link": "https://www.youtube.com/shorts/zzzzzzzzzzz", "duration": "0:40"},
                {"title": "Muy corto", "link": "https://www.youtube.com/watch?v=shortvideo1", "duration": "1:10"}]})
        assert body["hl"] == "es"
        return httpx.Response(200, json={"organic": [{"title": "Round Robin - Apunte", "link": "https://ejemplo.edu/rr",
                                                      "snippet": "El algoritmo Round Robin asigna un quantum."}]})
    if host == "serpapi.com":
        params = dict(request.url.params)
        assert params["api_key"] == "serpapi-test"
        if params["engine"] == "youtube":
            return httpx.Response(200, json={"video_results": [
                {"title": "Punteros en C++ desde cero", "link": "https://www.youtube.com/watch?v=pppppppppp1",
                 "channel": {"name": "Canal C"}, "length": "1:02:03", "views": 120345, "published_date": "hace 1 año",
                 "thumbnail": {"static": "https://i.ytimg.com/vi/pppppppppp1/hq720.jpg"}, "description": "Clase completa"}]})
        if params["engine"] == "google_scholar":
            return httpx.Response(200, json={"organic_results": [{"title": "Memoria virtual", "link": "https://repo.edu/mv",
                                                                  "snippet": "Paginación por demanda.",
                                                                  "publication_info": {"summary": "A Ruiz - 2018"},
                                                                  "inline_links": {"cited_by": {"total": 30}}}]})
        if params["q"] == "sin resultados":
            return httpx.Response(200, json={"error": "Google hasn't returned any results for this query."})
        return httpx.Response(200, json={"organic_results": [{"title": "Memoria virtual - UTN", "link": "https://utn.edu/mv",
                                                              "snippet": "La memoria virtual permite..."}]})
    if host == "www.googleapis.com" and request.url.path.startswith("/books/v1/volumes/"):
        return httpx.Response(200, json={"volumeInfo": {"title": "Sistemas operativos", "authors": ["A. Silberschatz"],
                                                        "publishedDate": "2006", "language": "es",
                                                        "infoLink": "https://books.google.com/books?id=B1",
                                                        "description": "<p>" + ABSTRACT + " " + ABSTRACT + "</p>",
                                                        "categories": ["Computers"]}})
    if host == "www.googleapis.com" and request.url.path == "/books/v1/volumes":
        return httpx.Response(200, json={"items": [
            {"id": "B1", "volumeInfo": {"title": "Sistemas operativos", "subtitle": "Conceptos", "authors": ["A. Silberschatz"],
                                        "publishedDate": "2006", "infoLink": "https://books.google.com/books?id=B1",
                                        "description": ABSTRACT}},
            {"id": "B2", "volumeInfo": {"title": "Sin descripción"}}]})
    if host == "www.googleapis.com" and request.url.path == "/youtube/v3/search":
        if request.url.params["key"] == "mala":
            return httpx.Response(403, json={"error": {"errors": [{"reason": "quotaExceeded"}]}})
        return httpx.Response(200, json={"items": [
            {"id": {"videoId": "yt000000001"}, "snippet": {"title": "Fotos&iacute;ntesis &quot;f&aacute;cil&quot;", "channelTitle": "Bio",
                                                          "publishedAt": "2022-05-01T00:00:00Z", "description": "Clase"}},
            {"id": {"videoId": "yt000000002"}, "snippet": {"title": "Short", "channelTitle": "X"}}]})
    if host == "www.googleapis.com" and request.url.path == "/youtube/v3/videos":
        return httpx.Response(200, json={"items": [
            {"id": "yt000000001", "contentDetails": {"duration": "PT14M2S"}, "statistics": {"viewCount": "15300"}},
            {"id": "yt000000002", "contentDetails": {"duration": "PT45S"}, "statistics": {"viewCount": "9"}}]})
    if host == "api.tavily.com":
        assert request.headers["Authorization"] == "Bearer tvly-test"
        body = json.loads(request.content)
        assert body["query"]
        if body.get("include_domains") == ["youtube.com"]:
            return httpx.Response(200, json={"results": [{"title": "Clase de redes - YouTube",
                                                          "url": "https://www.youtube.com/watch?v=tttttttttt1", "content": "Modelo OSI"}]})
        return httpx.Response(200, json={"results": [{"title": "Punteros en C++", "url": "https://ejemplo.edu/punteros",
                                                      "content": "Un puntero es una variable que guarda una dirección."}]})
    if host == "api.search.brave.com":
        assert request.headers["X-Subscription-Token"] == "brave-test"
        if request.url.path.endswith("/videos/search"):
            return httpx.Response(200, json={"results": [{"title": "TCP vs UDP", "url": "https://www.youtube.com/watch?v=bbbbbbbbbb1",
                                                          "video": {"duration": "08:30", "creator": "Redes Fácil"},
                                                          "thumbnail": {"src": "https://img/x.jpg"}},
                                                         {"title": "Otro sitio", "url": "https://vimeo.com/1"}]})
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

    def test_google_serper_serpapi_libros(self):
        g = self.run_(sp.search("serper", "round robin", {"serper": "serper-test"}, hint="sistemas operativos"))
        self.assertEqual(g[0]["url"], "https://ejemplo.edu/rr")
        self.assertEqual(g[0]["kind"], "provider")
        sch = self.run_(sp.search("serper_scholar", "planificación", {"serper": "serper-test"}))
        self.assertIn("8 citas", sch[0]["meta"])
        sa = self.run_(sp.search("serpapi", "memoria virtual", {"serpapi": "serpapi-test"}))
        self.assertEqual(sa[0]["url"], "https://utn.edu/mv")
        self.assertEqual(self.run_(sp.search("serpapi", "sin resultados", {"serpapi": "serpapi-test"})), [])
        sas = self.run_(sp.search("serpapi_scholar", "memoria", {"serpapi": "serpapi-test"}))
        self.assertIn("30 citas", sas[0]["meta"])
        books = self.run_(sp.search("google_books", "sistemas operativos", {}))
        self.assertEqual([b["ref"] for b in books], ["B1"])  # el libro sin descripción se descarta
        self.assertEqual(books[0]["title"], "Sistemas operativos: Conceptos")
        src = self.run_(sp.fetch("google_books", "B1", None, {}))
        self.assertIn("Silberschatz", src["source_name"])
        self.assertEqual(sp.key_name("serper_scholar"), "serper")

    def test_videos_proveedores(self):
        yt = self.run_(videos.find("fotosíntesis", {"google": "AIza-test"}))
        self.assertEqual(yt["via"], "YouTube")
        self.assertEqual([v["id"] for v in yt["videos"]], ["yt000000001"])  # el de 45 s se descarta
        self.assertEqual(yt["videos"][0]["title"], 'Fotosíntesis "fácil"')
        self.assertEqual(yt["videos"][0]["duration"], "14:02")
        # si YouTube falla (cuota), se pasa al siguiente proveedor configurado
        fb = self.run_(videos.find("round robin", {"google": "mala", "serper": "serper-test"}))
        self.assertEqual(fb["via"], "Serper")
        self.assertEqual([v["id"] for v in fb["videos"]], ["abcdefghijk"])  # sin Shorts ni videos cortos
        self.assertTrue(any("cuota" in e for e in fb["errors"]))
        sa = self.run_(videos.find("punteros", {"serpapi": "serpapi-test"}))
        self.assertEqual(sa["videos"][0]["duration"], "1:02:03")
        self.assertEqual(sa["videos"][0]["channel"], "Canal C")
        br = self.run_(videos.find("tcp", {"brave": "brave-test"}))
        self.assertEqual([v["id"] for v in br["videos"]], ["bbbbbbbbbb1"])
        tv = self.run_(videos.find("redes", {"tavily": "tvly-test"}))
        self.assertEqual(tv["videos"][0]["title"], "Clase de redes")
        none = self.run_(videos.find("x", {}))
        self.assertEqual(none["videos"], [])
        self.assertIsNone(videos.video_id("https://www.youtube.com/shorts/abcdefghijk"))
        self.assertEqual(videos.parse_iso_duration("PT1H2M3S"), 3723)

    def test_toda_la_web_y_academicos(self):
        sx = self.run_(sp.search("searxng", "modelo osi", {"searxng": "http://buscador:8080"}, hint="redes"))
        self.assertEqual([r["url"] for r in sx], ["https://ejemplo.edu/osi"])  # sin duplicados ni javascript:
        self.assertIn("google", sx[0]["meta"])
        self.assertEqual(self.run_(sp.search("searxng_it", "osi", {"searxng": "http://buscador:8080"}))[0]["site"], "searxng_it")
        self.assertEqual(self.run_(sp.search("marginalia", "round robin", {}))[0]["url"], "https://blog.ej/rr")
        hn = self.run_(sp.search("hackernews", "tcp", {}))
        self.assertEqual(len(hn), 1)
        self.assertEqual(self.run_(sp.search("exa", "punteros", {"exa": "exa-test"}))[0]["meta"], "2023-02-01")
        self.assertEqual(self.run_(sp.search("mdn", "closures", {}))[0]["url"],
                         "https://developer.mozilla.org/es/docs/Web/JavaScript/Closures")
        s2 = self.run_(sp.search("semanticscholar", "sleep", {}))
        self.assertEqual([r["ref"] for r in s2], ["abc123"])
        self.assertIn("J. Doe", self.run_(sp.fetch("semanticscholar", "abc123", None, {}))["source_name"])
        cr = self.run_(sp.search("crossref", "fotosíntesis", {}))
        self.assertNotIn("<jats", cr[0]["snippet"])
        self.assertNotIn("Resumen", cr[0]["snippet"][:10])
        self.assertIn("Ana Pérez", self.run_(sp.fetch("crossref", "10.1/xyz", None, {}))["source_name"])
        dj = self.run_(sp.search("doaj", "espaciado", {}))
        self.assertEqual(dj[0]["ref"], "d1")
        self.assertEqual(self.run_(sp.fetch("doaj", "d1", None, {}))["sections"][0]["title"], "Resumen")
        ol = self.run_(sp.search("openlibrary", "estructuras", {}))
        self.assertEqual(ol[0]["ref"], "/works/OL123W")
        self.assertEqual(len(self.run_(sp.fetch("openlibrary", "/works/OL123W", None, {}))["sections"]), 2)
        with self.assertRaises(sources.SourceError):
            self.run_(sp.fetch("openlibrary", "/../../etc", None, {}))

    def test_videos_searxng_sin_clave(self):
        v = self.run_(videos.find("modelo osi", {"searxng": "http://buscador:8080"}))
        self.assertEqual(v["via"], "SearXNG")
        self.assertEqual([x["id"] for x in v["videos"]], ["sxsxsxsxsx1"])
        self.assertEqual(v["videos"][0]["duration"], "15:20")


if __name__ == "__main__":
    unittest.main()
