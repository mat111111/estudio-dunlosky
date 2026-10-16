"""Corrección de respuestas comparándolas con la información verificada de la fuente."""
from __future__ import annotations

import re

from rapidfuzz import fuzz

from . import textproc as tp


def _same(a: str, b: str) -> bool:
    return tp.normalize(a) == tp.normalize(b)


def _stem_match(user_stems: set[str], target: str) -> bool:
    if target in user_stems:
        return True
    if len(target) < 4:
        return False
    return any(len(u) >= 4 and fuzz.ratio(u, target) >= 85 for u in user_stems)


def _key_stems(reference: str, exclude_text: str = "", limit: int = 10) -> list[tuple[str, str]]:
    """Conceptos de la respuesta de referencia: [(stem, palabra_original)]."""
    excluded = tp.stems(exclude_text)
    seen = set()
    out = []
    for raw in re.findall(r"[\wáéíóúñü]+", reference):
        n = tp.normalize(raw)
        if not n or n in tp.STOPWORDS or (len(n) < 3 and not n.isdigit()):
            continue
        st = tp.stem(n)
        if st in seen or st in excluded:
            continue
        seen.add(st)
        out.append((st, raw))
    if not out:  # todo estaba en la pregunta: usamos la referencia completa
        for raw in re.findall(r"[\wáéíóúñü]+", reference):
            n = tp.normalize(raw)
            if n and n not in tp.STOPWORDS and len(n) >= 3:
                st = tp.stem(n)
                if st not in seen:
                    seen.add(st)
                    out.append((st, raw))
    # priorizamos palabras largas / números / nombres propios
    out.sort(key=lambda sr: -(len(sr[1]) + (6 if sr[1][:1].isupper() or sr[1].isdigit() else 0)))
    return out[:limit]


def grade_choice(item: dict, answer: str) -> dict:
    ok = _same(answer, item["answer"])
    return {
        "verdict": "correct" if ok else "incorrect",
        "score": 1.0 if ok else 0.0,
        "feedback": "¡Correcto!" if ok else f"La respuesta correcta es «{item['answer']}».",
        "missing": [], "matched": [],
    }


def grade_cloze(item: dict, answer: str) -> dict:
    expected = item["answer"]
    a, e = tp.normalize(answer), tp.normalize(expected)
    res = {"missing": [], "matched": []}
    if not a:
        return {**res, "verdict": "incorrect", "score": 0.0, "feedback": "No respondiste. La respuesta era «%s»." % expected}

    if re.fullmatch(r"[\d.,% ]+", expected.strip()):
        ok = re.sub(r"\D", "", a) == re.sub(r"\D", "", e)
        return {**res, "verdict": "correct" if ok else "incorrect", "score": float(ok),
                "feedback": "¡Correcto!" if ok else f"El dato correcto es {expected}."}

    if a == e or tp.stem(a) == tp.stem(e):
        return {**res, "verdict": "correct", "score": 1.0, "feedback": "¡Correcto!"}

    ratio = fuzz.ratio(a, e)
    if ratio >= 85:
        return {**res, "verdict": "correct", "score": 0.95,
                "feedback": f"Correcto, aunque revisá la escritura: «{expected}»."}

    a_tok, e_tok = set(a.split()) - tp.STOPWORDS, set(e.split()) - tp.STOPWORDS
    if a_tok and e_tok and a_tok <= e_tok:
        return {**res, "verdict": "partial", "score": 0.6,
                "feedback": f"Vas bien, pero está incompleto. La respuesta completa es «{expected}»."}
    if e_tok and e_tok <= a_tok and len(a_tok) <= len(e_tok) + 2:
        return {**res, "verdict": "correct", "score": 0.9, "feedback": "¡Correcto!"}
    if ratio >= 70 or fuzz.partial_ratio(a, e) >= 90:
        return {**res, "verdict": "partial", "score": 0.5,
                "feedback": f"Muy cerca. La respuesta exacta es «{expected}»."}
    return {**res, "verdict": "incorrect", "score": 0.0, "feedback": f"No es correcto. La respuesta es «{expected}»."}


def grade_open(item: dict, answer: str) -> dict:
    reference = item["answer"]
    keys = _key_stems(reference, exclude_text=item.get("prompt", ""))
    user_stems = tp.stems(answer)
    if not tp.content_tokens(answer):
        return {"verdict": "incorrect", "score": 0.0, "matched": [], "missing": [w for _, w in keys],
                "feedback": "No escribiste una respuesta. Intentá recuperar la idea aunque sea con pocas palabras."}
    matched, missing = [], []
    for st, word in keys:
        (matched if _stem_match(user_stems, st) else missing).append(word)
    cov = len(matched) / max(len(keys), 1)
    if item.get("origin") == "elab":
        # Pregunta de elaboración libre: la referencia es el contexto de la fuente,
        # no una única respuesta. Se corrige con más tolerancia y se invita a autoevaluarse.
        if cov >= 0.25 or (cov >= 0.1 and tp.word_count(answer) >= 15):
            verdict, fb = "correct", "Buena elaboración: conectaste la idea con lo que dice la fuente."
        elif cov > 0 or tp.word_count(answer) >= 12:
            verdict, fb = "partial", "Compará tu explicación con el contexto de la fuente: ¿te faltó alguna relación?"
        else:
            verdict, fb = "incorrect", "Tu explicación no se relaciona con lo que dice la fuente alrededor de esa idea."
        return {"verdict": verdict, "score": round(cov, 2), "matched": matched, "missing": missing, "feedback": fb}
    if cov >= 0.5:
        verdict, fb = "correct", "¡Bien! Tu respuesta cubre las ideas centrales de la fuente."
    elif cov >= 0.25:
        verdict, fb = "partial", "Respuesta parcial: tenés parte de la idea, pero faltan conceptos clave."
    else:
        verdict, fb = "incorrect", "Tu respuesta no coincide con lo que dice la fuente."
    return {"verdict": verdict, "score": round(cov, 2), "matched": matched, "missing": missing, "feedback": fb}


def grade(item: dict, answer: str) -> dict:
    kind = item["kind"]
    if kind in ("mc", "tf"):
        return grade_choice(item, answer)
    if kind == "cloze":
        return grade_cloze(item, answer)
    return grade_open(item, answer)


# --------------------------------------------------------------------------- #
# Resumen, autoexplicación y subrayado
# --------------------------------------------------------------------------- #
def grade_summary(section_text: str, summary: str, keywords: dict) -> dict:
    concepts = tp.key_terms(section_text, keywords, top=10)
    user_stems = tp.stems(summary)
    user_norm = " " + tp.normalize(summary) + " "
    covered, missing = [], []
    for c in concepts:
        cs = [tp.stem(t) for t in tp.content_tokens(c)] or [tp.normalize(c)]
        ok = all(_stem_match(user_stems, s) for s in cs) or f" {tp.normalize(c)} " in user_norm
        (covered if ok else missing).append(c)
    src_words = tp.word_count(section_text)
    sum_words = tp.word_count(summary)
    cov = len(covered) / max(len(concepts), 1)
    notes = []
    if sum_words < 20:
        notes.append("Es muy corto: un buen resumen reconstruye las ideas con tus palabras.")
    if sum_words > src_words * 0.6:
        notes.append("Es casi tan largo como el original: intentá quedarte solo con lo esencial.")
    # copiar y pegar no es resumir
    overlap = fuzz.partial_ratio(tp.normalize(summary)[:400], tp.normalize(section_text))
    if sum_words > 15 and overlap > 92:
        notes.append("Parece copiado del texto. Resumir con tus palabras es lo que genera aprendizaje.")
    return {"coverage": round(cov, 2), "covered": covered, "missing": missing,
            "words": sum_words, "source_words": src_words, "notes": notes}


def grade_self_explanation(sentence: str, previous: str, explanation: str, keywords: dict) -> dict:
    terms = [t for t, _ in tp.find_terms_in_sentence(sentence, keywords)] or \
            [w for _, w in _key_stems(sentence, limit=5)]
    user_stems = tp.stems(explanation)
    used = [t for t in terms if all(_stem_match(user_stems, s) for s in [tp.stem(x) for x in tp.content_tokens(t)] or [t])]
    prev_terms = [w for _, w in _key_stems(previous, limit=8)] if previous else []
    connects = [t for t in prev_terms if _stem_match(user_stems, tp.stem(tp.normalize(t)))]
    words = tp.word_count(explanation)
    tips = []
    if words < 10:
        tips.append("Desarrollá un poco más: explicá el porqué, no solo el qué.")
    if previous and not connects:
        tips.append("Intentá conectarlo con la oración anterior: ¿qué agrega o cómo se relaciona?")
    if not re.search(r"\b(porque|ya que|entonces|por eso|significa|o sea|es decir|como|por lo que|implica|"
                     r"because|so|means)\b", explanation.lower()):
        tips.append("Usá conectores explicativos (porque, entonces, o sea, esto implica...).")
    quality = min(1.0, 0.4 * (len(used) / max(len(terms), 1)) + 0.3 * bool(connects or not previous)
                  + 0.3 * min(words / 20, 1))
    return {"quality": round(quality, 2), "terms": terms, "used": used, "connections": connects, "tips": tips}


def grade_highlights(selected: list[int], key_idx: list[int], total: int) -> dict:
    sel, key = set(selected), set(key_idx)
    hit = sel & key
    precision = len(hit) / len(sel) if sel else 0.0
    recall = len(hit) / len(key) if key else 0.0
    ratio = len(sel) / max(total, 1)
    notes = []
    if ratio > 0.5:
        notes.append("Subrayaste más de la mitad del texto: subrayar todo equivale a no subrayar nada.")
    if sel and precision < 0.4:
        notes.append("Muchas de tus marcas son detalles secundarios. Buscá definiciones, causas y datos centrales.")
    if recall < 0.5:
        notes.append("Te quedaron afuera varias ideas clave (marcadas en amarillo punteado).")
    return {"precision": round(precision, 2), "recall": round(recall, 2), "ratio": round(ratio, 2),
            "hits": sorted(hit), "missed": sorted(key - sel), "extra": sorted(sel - key), "notes": notes}
