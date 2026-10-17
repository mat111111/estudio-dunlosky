"""Procesamiento de texto: oraciones, normalización, palabras clave y oraciones clave.

Todo es heurístico y sin dependencias pesadas para que la app funcione sin
conexión a servicios de IA. Está pensado para español, con soporte básico de inglés.
"""
from __future__ import annotations

import math
import re
import unicodedata
from collections import Counter

# --------------------------------------------------------------------------- #
# Stopwords
# --------------------------------------------------------------------------- #
STOP_ES = set("""
a al algo algunas algunos ante antes aquel aquella aquellas aquellos aqui asi aun aunque bajo bien cada casi
como con contra cual cuales cualquier cuando cuanto de del desde donde dos durante e el ella ellas ello ellos
en entre era eran eres es esa esas ese eso esos esta estaba estaban estado estan estar este esto estos fue fueron
fuera ha habia habian han hasta hay la las le les lo los mas me mi mientras mismo mucho muy nada ni no nos nosotros
o otra otras otro otros para pero poco por porque que quien quienes se sea segun ser si sido siempre sin sino sobre
son su sus tal tambien tan tanto te tiene tienen todo todos tras tu tus un una unas uno unos y ya yo puede pueden
dicho dicha hacia hacer hace hizo luego parte primer primera segundo tiempo vez veces asimismo ademas embargo
mayor menor gran grande grandes nuevo nueva nuevos nuevas ser seran sera siendo cuyo cuya cuyos cuyas donde
mediante sea sean haber habria podria debe deben otro misma mismos mismas aquellas esto estas ese tal pues
traves ocurre ocurren permite permiten produce producen necesita necesitan existe existen utiliza utilizan
tienen tenia tenian llamado llamada llamados llamadas denomina denominado denominada conocido conocida conocidos
conocidas puede pudo podia hacen hecho hecha incluye incluyen incluso considera considerado considerada
general manera forma formas tipo tipos ejemplo caso casos cierto cierta ciertos ciertas varios varias diversos
diversas distintos distintas diferentes principal principales importante importantes posible largo largos
encuentra encuentran realiza realizan lleva llevan llego queda quedan sigue siguen segun durante dentro fuera
""".split())

STOP_EN = set("""
a about above after again against all also am an and any are as at be because been before being below between both
but by can could did do does doing down during each few for from further had has have having he her here hers him his
how i if in into is it its itself just me more most my no nor not now of off on once only or other our out over own same
she should so some such than that the their them then there these they this those through to too under until up very
was we were what when where which while who whom why will with would you your yours however also many much new
""".split())

STOPWORDS = STOP_ES | STOP_EN

ABBREVIATIONS = [
    "etc.", "p. ej.", "p.ej.", "Sr.", "Sra.", "Dr.", "Dra.", "a. C.", "d. C.", "a.C.", "d.C.", "aprox.",
    "núm.", "vol.", "pág.", "págs.", "cap.", "EE. UU.", "EE.UU.", "S.A.", "Ud.", "Uds.", "e.g.", "i.e.",
    "Mr.", "Mrs.", "Dr.", "vs.", "St.", "No.", "fig.", "ca.", "art.", "inc.", "Inc.", "Ltd.", "Co.",
]

PRONOUN_START = re.compile(
    r"^(Esto|Este|Esta|Estos|Estas|Ello|Ella|Ellos|Él|Su|Sus|También|Además|Sin embargo|Asimismo|Así|"
    r"It|This|These|They|He|She|His|Her|Its|Also|However)\b"
)

_DOT = "․"  # marcador temporal para puntos de abreviaturas


def strip_accents(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")


def normalize(s: str) -> str:
    """minúsculas, sin acentos, solo alfanumérico y espacios."""
    s = strip_accents(s.lower())
    s = re.sub(r"[^a-z0-9ñ\s]", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def stem(word: str) -> str:
    """Stemming muy liviano (plurales y algunos sufijos) para comparar conceptos."""
    w = word
    for suf in ("aciones", "iciones", "imientos", "amientos"):
        if w.endswith(suf) and len(w) > len(suf) + 3:
            return w[: -len(suf)]
    for suf in ("acion", "icion", "imiento", "amiento", "mente", "idades", "idad", "ismos", "ismo"):
        if w.endswith(suf) and len(w) > len(suf) + 3:
            return w[: -len(suf)]
    if w.endswith("ces") and len(w) > 5:
        return w[:-3] + "z"
    if w.endswith("es") and len(w) > 5:
        w = w[:-2]
    elif w.endswith("s") and len(w) > 4:
        w = w[:-1]
    if len(w) > 5 and w[-1] in "aeo":
        w = w[:-1]
    return w


def content_tokens(text: str) -> list[str]:
    return [t for t in normalize(text).split() if t not in STOPWORDS and (len(t) > 2 or t.isdigit())]


def stems(text: str) -> set[str]:
    return {stem(t) for t in content_tokens(text)}


# --------------------------------------------------------------------------- #
# Oraciones
# --------------------------------------------------------------------------- #
def split_sentences(text: str) -> list[str]:
    t = " ".join(text.split())
    for ab in ABBREVIATIONS:
        t = t.replace(ab, ab.replace(".", _DOT))
    # iniciales tipo "J. R. R. Tolkien"
    t = re.sub(r"\b([A-ZÁÉÍÓÚÑ])\.(?=\s*[A-ZÁÉÍÓÚÑ])", lambda m: m.group(1) + _DOT, t)
    # números decimales 3.14
    t = re.sub(r"(\d)\.(\d)", lambda m: m.group(1) + _DOT + m.group(2), t)
    parts = re.split(r"(?<=[.!?…])\s+(?=[\"«“¿¡(\[]?[A-ZÁÉÍÓÚÑ0-9])", t)
    out = []
    for p in parts:
        p = p.replace(_DOT, ".").strip()
        if len(p) > 1:
            out.append(p)
    return out


def section_sentences(text: str) -> list[tuple[int, str]]:
    """Oraciones de una sección con el índice de párrafo al que pertenecen.

    El índice global de cada oración (posición en la lista) es el que usan las
    preguntas para anclarse a su fragmento de origen.
    """
    out = []
    paras = [p for p in text.split("\n") if p.strip()]
    for pi, para in enumerate(paras):
        for s in split_sentences(para):
            out.append((pi, s))
    return out


def word_count(s: str) -> int:
    return len(s.split())


# --------------------------------------------------------------------------- #
# Palabras clave
# --------------------------------------------------------------------------- #
CAP_WORD = r"[A-ZÁÉÍÓÚÑ][\wáéíóúñü\-]+"
CONNECT = r"(?:de|del|la|las|los|el|y|e|of|the|and)"
PROPER_RE = re.compile(rf"\b{CAP_WORD}(?:\s+(?:{CONNECT}\s+)?{CAP_WORD})*")
YEAR_RE = re.compile(r"\b(1[0-9]{3}|20[0-9]{2}|[1-9][0-9]{0,2})\b")
NUM_RE = re.compile(r"\b\d+(?:[.,]\d+)?\s?%?")


VERBISH = re.compile(r"(?:ar|er|ir|aron|ieron|aban|aba|ando|iendo|ados|adas)$")


def term_kind(term: str) -> str:
    if re.fullmatch(r"\d{3,4}", term):
        return "year"
    if re.fullmatch(r"[\d.,]+\s?%?", term):
        return "number"
    if term[:1].isupper():
        return "proper"
    return "concept"


def extract_keywords(sentences: list[str], title: str = "", limit: int = 80) -> dict[str, dict]:
    """Devuelve {termino: {"weight": float, "kind": str, "count": int}}.

    Combina nombres propios (secuencias de mayúsculas que no inician oración),
    años/números y conceptos frecuentes del documento.
    """
    proper = Counter()
    years = Counter()
    words = Counter()
    surface: dict[str, Counter] = {}
    sent_df = Counter()
    first_words = set()

    for s in sentences:
        first = s.split()[0].strip("¿¡\"«(") if s.split() else ""
        first_words.add(first)
        seen = set()
        for m in PROPER_RE.finditer(s):
            term = m.group(0).strip()
            # descartar la primera palabra de la oración si es palabra común
            if m.start() <= s.find(first) + 1 and " " not in term and normalize(term) in STOPWORDS:
                continue
            if normalize(term) in STOPWORDS:
                continue
            if len(term) < 3:
                continue
            proper[term] += 1
        for m in re.finditer(r"\b(1[0-9]{3}|20[0-9]{2})\b", s):
            years[m.group(0)] += 1
        for raw in re.findall(r"[\wáéíóúñü]+", s):
            tok = normalize(raw)
            if len(tok) >= 5 and tok not in STOPWORDS and not tok.isdigit():
                surface.setdefault(tok, Counter())[raw.lower()] += 1
        for tok in content_tokens(s):
            if len(tok) >= 5 and not tok.isdigit():
                words[tok] += 1
                if tok not in seen:
                    sent_df[tok] += 1
                    seen.add(tok)

    n = max(len(sentences), 1)
    title_stems = stems(title)
    result: dict[str, dict] = {}

    # nombres propios: ignorar los que solo aparecen como primera palabra
    for term, c in proper.items():
        if " " not in term and term in first_words and c < 2:
            continue
        w = 1.5 + math.log1p(c) + (0.5 if " " in term else 0)
        result[term] = {"weight": w, "kind": "proper", "count": c}

    for y, c in years.items():
        result[y] = {"weight": 1.6 + math.log1p(c) * 0.5, "kind": "year", "count": c}

    # conceptos: frecuencia con penalización por estar en demasiadas oraciones
    proper_single = {normalize(t) for t in result if result[t]["kind"] == "proper"}
    proper_words = {w for t in proper_single for w in t.split()}
    for tok, c in words.items():
        if c < 2 or tok in proper_words:
            continue
        df = sent_df[tok]
        idf = math.log(1 + n / df)
        w = math.log1p(c) * idf * 0.9
        if stem(tok) in title_stems:
            w *= 0.6  # el título aparece en todos lados, no es buena respuesta
        if VERBISH.search(tok):
            w *= 0.55  # preferimos sustantivos como respuesta
        form = surface.get(tok, Counter({tok: 1})).most_common(1)[0][0]
        result.setdefault(form, {"weight": w, "kind": "concept", "count": c})

    ranked = dict(sorted(result.items(), key=lambda kv: -kv[1]["weight"])[:limit])
    # palabra que precede a cada término ("fase luminosa" / "fase oscura"): sirve para encontrar
    # conceptos "hermanos" que se pueden intercambiar para armar afirmaciones falsas creíbles
    norm_sents = [strip_accents(x.lower()) for x in sentences]
    for term, info in ranked.items():
        if info["kind"] != "concept":
            continue
        prev = Counter()
        pat = re.compile(rf"([a-zñ]+)\s+{re.escape(strip_accents(term.lower()))}\b")
        for ns in norm_sents:
            for m in pat.finditer(ns):
                if m.group(1) not in ("el", "la", "los", "las", "un", "una", "de", "del", "y", "e", "o", "en", "a", "al", "que", "su", "sus"):
                    prev[m.group(1)] += 1
        info["prev"] = [w for w, _ in prev.most_common(3)]
    return ranked


def find_terms_in_sentence(sentence: str, keywords: dict[str, dict]) -> list[tuple[str, dict]]:
    """Términos de `keywords` presentes en la oración, con la forma exacta encontrada."""
    found = []
    for term, info in keywords.items():
        if info["kind"] == "concept":
            m = re.search(rf"\b({re.escape(strip_accents(term))})\b", strip_accents(sentence.lower()))
            if m:
                # recuperar la forma original con acentos
                original = sentence[m.start(1): m.end(1)]
                found.append((original, info))
        else:
            if re.search(rf"(?<![\w]){re.escape(term)}(?![\w])", sentence):
                found.append((term, info))
    # eliminar términos contenidos en otros más largos y duplicados
    found.sort(key=lambda t: -len(t[0]))
    final = []
    seen = set()
    for term, info in found:
        n = normalize(term)
        if n in seen or any(n in normalize(f) for f, _ in final):
            continue
        seen.add(n)
        final.append((term, info))
    return final


def score_sentences(sentences: list[str], keywords: dict[str, dict]) -> list[float]:
    """Puntaje de importancia por oración (para subrayado y resumen)."""
    scores = []
    for i, s in enumerate(sentences):
        wc = word_count(s)
        if wc < 5:
            scores.append(0.0)
            continue
        terms = find_terms_in_sentence(s, keywords)
        sc = sum(info["weight"] for _, info in terms) / math.sqrt(wc)
        if i == 0:
            sc *= 1.6
        if re.search(r"\b(es|son|se define|consiste|significa|se denomina|se llama|refers|is a|are)\b", s):
            sc *= 1.15
        scores.append(sc)
    return scores


def key_sentence_indices(sentences: list[str], keywords: dict[str, dict], ratio: float = 0.3) -> list[int]:
    scores = score_sentences(sentences, keywords)
    k = max(1, round(len(sentences) * ratio))
    ranked = sorted(range(len(sentences)), key=lambda i: -scores[i])
    return sorted(i for i in ranked[:k] if scores[i] > 0)


def key_terms(text: str, keywords: dict[str, dict], top: int = 10) -> list[str]:
    sents = split_sentences(text)
    counter: dict[str, float] = {}
    for s in sents:
        for term, info in find_terms_in_sentence(s, keywords):
            counter[term] = counter.get(term, 0) + info["weight"]
    # deduplicar por forma normalizada
    seen = set()
    out = []
    for term, _ in sorted(counter.items(), key=lambda kv: -kv[1]):
        n = normalize(term)
        if n in seen:
            continue
        seen.add(n)
        out.append(term)
        if len(out) >= top:
            break
    return out


def detect_language(text: str) -> str:
    toks = normalize(text[:3000]).split()
    es = sum(1 for t in toks if t in STOP_ES)
    en = sum(1 for t in toks if t in STOP_EN)
    return "en" if en > es * 1.3 else "es"
