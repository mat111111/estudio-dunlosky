"""Generación automática de preguntas a partir del texto de la fuente.

Cada pregunta queda anclada a la oración exacta de la que salió (``context``),
así la corrección puede mostrar la evidencia y la práctica de errores puede
volver sobre ese mismo fragmento con preguntas "hermanas".
"""
from __future__ import annotations

import random
import re

from . import textproc as tp

BLANK = "_____"

DEF_RE = re.compile(
    r"^(?:(?P<art>El|La|Los|Las|Un|Una|The|An|A)\s+)?(?P<subj>[^,;:()]{2,70}?)\s+"
    r"(?P<verb>es|son|fue|fueron|era|eran|consiste en|se define como|se denomina|se llama|is|are|was|were)\s+"
    r"(?P<pred>(?:el|la|los|las|un|una|unos|unas|aquel|aquella|uno|cualquier|todo|toda|a|an|the|any)\s.{15,})$"
)

CAUSE_AFTER = re.compile(
    r"^(?P<claim>.{20,}?),?\s+(?P<mk>porque|ya que|debido a que|debido a|puesto que|dado que|gracias a|"
    r"a causa de|because|due to|since|as a result of)\s+(?P<rest>.{12,})$",
    re.IGNORECASE,
)
EFFECT_AFTER = re.compile(
    r"^(?P<cause>.{20,}?),?\s+(?P<mk>por lo que|por lo tanto|por eso|por ello|lo que provocó|lo que permitió|"
    r"lo que llevó a|lo que generó|de modo que|de manera que|así que|lo cual permite|lo que permite|"
    r"therefore|which led to|which allowed|as a result|so that)\s+(?P<rest>.{12,})$",
    re.IGNORECASE,
)

QUESTION_VERB = {
    "es": "es", "son": "son", "fue": "fue", "fueron": "fueron", "era": "era", "eran": "eran",
    "consiste en": "es", "se define como": "es", "se denomina": "es", "se llama": "es",
    "is": "is", "are": "are", "was": "was", "were": "were",
}


def _blank(sentence: str, term: str) -> str:
    pattern = rf"(?<![\wáéíóúñü]){re.escape(term)}(?![\wáéíóúñü])"
    out, n = re.subn(pattern, BLANK, sentence)
    if n == 0:
        out, n = re.subn(re.escape(term), BLANK, sentence, flags=re.IGNORECASE)
    return out


def _hint(term: str, kind: str) -> str:
    if kind == "year":
        return f"Es un año del siglo {_century(int(term))}."
    if kind == "number":
        return "Es un número."
    words = term.split()
    if len(words) > 1:
        return f"Son {len(words)} palabras; la primera empieza con «{term[0]}»."
    return f"Empieza con «{term[0]}» y tiene {len(term)} letras."


def _century(year: int) -> str:
    c = (year - 1) // 100 + 1
    vals = [(10, "X"), (9, "IX"), (5, "V"), (4, "IV"), (1, "I")]
    r = ""
    for v, s in vals:
        while c >= v:
            r += s
            c -= v
    return r


class Distractors:
    def __init__(self, keywords: dict[str, dict], rng: random.Random):
        self.rng = rng
        self.by_kind: dict[str, list[str]] = {}
        for term, info in keywords.items():
            self.by_kind.setdefault(info["kind"], []).append(term)

    def pick(self, term: str, kind: str, sentence: str, k: int = 3) -> list[str]:
        nt = tp.normalize(term)
        sent_norm = tp.normalize(sentence)
        pool = []
        for cand in self.by_kind.get(kind, []):
            nc = tp.normalize(cand)
            if not nc or nc == nt or nc in nt or nt in nc:
                continue
            if f" {nc} " in f" {sent_norm} ":
                continue
            if tp.stem(nc) == tp.stem(nt):
                continue
            # no ofrecer verbos como alternativa de un sustantivo (rompe la gramática)
            if kind == "concept" and tp.VERBISH.search(nc) and not tp.VERBISH.search(nt):
                continue
            pool.append(cand)
        if kind == "year":
            y = int(term)
            while len(pool) < k + 2:
                cand = str(y + self.rng.choice([-1, 1]) * self.rng.randint(2, 40))
                if cand != term and cand not in pool:
                    pool.append(cand)
        if kind == "concept":
            # misma concordancia de número (singular / plural) para no romper la oración
            same_num = [c for c in pool if c.endswith("s") == term.endswith("s")]
            if len(same_num) >= k:
                pool = same_num
            # preferir palabras de largo y terminación parecida (concordancia)
            pool.sort(key=lambda c: (c[-1:] != term[-1:], abs(len(c) - len(term))))
            pool = pool[: k + 4]
        elif kind == "proper":
            same = [c for c in pool if len(c.split()) == len(term.split())]
            other = [c for c in pool if c not in same]
            self.rng.shuffle(same)
            self.rng.shuffle(other)
            pool = (same + other)[: max(k, len(same))]
        if kind != "proper":
            self.rng.shuffle(pool)
        out = []
        seen = {nt}
        for c in pool:
            n = tp.normalize(c)
            if n in seen:
                continue
            seen.add(n)
            out.append(c)
            if len(out) == k:
                break
        return out


def _relate_pair(sentence: str, strong: list[str], used: set) -> tuple[str, str] | None:
    """Dos conceptos de la oración que no formen una sola expresión (p. ej. «ciclo de Calvin»)."""
    low = sentence.lower()
    for i, a in enumerate(strong):
        for b in strong[i + 1:]:
            if frozenset((tp.normalize(a), tp.normalize(b))) in used:
                continue
            pa, pb = low.find(a.lower()), low.find(b.lower())
            if pa < 0 or pb < 0:
                continue
            first, second = (a, b) if pa < pb else (b, a)
            gap = low[min(pa, pb) + len(first): max(pa, pb)]
            if len(gap.split()) <= 2:  # demasiado juntas: es una misma expresión
                continue
            return a, b
    return None


def _falsify(sentence: str, keywords: dict, title: str, dis: "Distractors") -> str | None:
    """Cambia un dato de la oración por otro creíble del mismo tema para obtener una afirmación falsa.

    Solo se usan cambios verosímiles: años, nombres propios por otros del mismo tipo y conceptos
    "hermanos" (que aparecen después de la misma palabra, como «fase luminosa» / «fase oscura»).
    """
    terms = [(t, i) for t, i in tp.find_terms_in_sentence(sentence, keywords)
             if tp.normalize(t) not in tp.normalize(title)]
    terms.sort(key=lambda ti: ({"year": 0, "proper": 1, "concept": 2}.get(ti[1]["kind"], 3), -ti[1]["weight"]))
    low = tp.strip_accents(sentence.lower())
    for term, info in terms:
        kind = info["kind"]
        alts: list[str] = []
        if kind in ("year", "proper"):
            alts = dis.pick(term, kind, sentence, 3)
            if kind == "proper":
                # personas por personas (nombres de 2+ palabras) o siglas por siglas
                alts = [a for a in alts if len(a.split()) == len(term.split())
                        and (len(term.split()) >= 2 or (term.isupper() and a.isupper()))]
        elif kind == "concept":
            m = re.search(rf"([a-zñ]+)\s+{re.escape(tp.strip_accents(term.lower()))}\b", low)
            before = m.group(1) if m else None
            if not before:
                continue
            for cand, ci in keywords.items():
                if (ci["kind"] == "concept" and tp.normalize(cand) != tp.normalize(term)
                        and before in ci.get("prev", []) and cand[-1:] == term[-1:]
                        and tp.normalize(cand) not in tp.normalize(sentence)):
                    alts.append(cand)
        for alt in alts:
            out = re.sub(rf"(?<![\wáéíóúñü]){re.escape(term)}(?![\wáéíóúñü])", alt, sentence, count=1)
            if out != sentence:
                return out
    return None


def _statement_mcs(sentences: list[str], keywords: dict, title: str, dis: "Distractors",
                   rng: random.Random) -> list[dict]:
    """Opción múltiple conceptual: elegir la afirmación correcta (o la incorrecta) entre cuatro.

    En vez de completar una palabra, obliga a validar ideas completas del texto: las opciones
    falsas son oraciones reales del tema con un concepto cambiado.
    """
    pool = [i for i, s in enumerate(sentences)
            if _eligible(s) and 7 <= tp.word_count(s) <= 32 and not tp.PRONOUN_START.match(s)
            and tp.find_terms_in_sentence(s, keywords)]
    if len(pool) < 4:
        return []
    out = []
    count = max(1, len(pool) // 4)
    rng.shuffle(pool)
    falsified = {i: _falsify(sentences[i], keywords, title, dis) for i in pool}
    can_lie = [i for i in pool if falsified[i]]
    used: set[int] = set()
    for k in range(count):
        if k % 2 == 0:
            # una correcta y tres falsas (las falsas son otras oraciones del texto, alteradas)
            liars = [i for i in can_lie if i not in used][:3]
            target = next((i for i in pool if i not in used and i not in liars), None)
            if len(liars) < 3 or target is None:
                continue
            opts = [falsified[i] for i in liars] + [sentences[target]]
            rng.shuffle(opts)
            out.append({"kind": "mc", "prompt": "Según el texto, ¿cuál de estas afirmaciones es correcta?",
                        "answer": sentences[target], "options": opts, "context": sentences[target],
                        "sentence_idx": target, "hint": None, "term_kind": "statement", "level": 2})
            used.update(liars + [target])
        else:
            # tres correctas y una falsa
            target = next((i for i in can_lie if i not in used), None)
            trues = [i for i in pool if i != target and i not in used][:3]
            if target is None or len(trues) < 3:
                continue
            opts = [sentences[i] for i in trues] + [falsified[target]]
            rng.shuffle(opts)
            out.append({"kind": "mc", "prompt": "Según el texto, ¿cuál de estas afirmaciones es INCORRECTA?",
                        "answer": falsified[target], "options": opts, "context": sentences[target],
                        "sentence_idx": target, "hint": None, "term_kind": "statement", "level": 2})
            used.update(trues + [target])
    return out


def cause_mcs(items: list[dict], rng: random.Random) -> list[dict]:
    """Opción múltiple sobre causas: «¿Por qué…?» con causas reales de otras partes del tema como distractores."""
    whys = [i for i in items if i["kind"] == "why" and i.get("origin", "auto") == "auto"
            and i["prompt"].startswith("¿Por qué")]
    if len(whys) < 4:
        return []
    out = []
    for it in whys:
        others = [w["answer"] for w in whys if w is not it and tp.normalize(w["answer"]) != tp.normalize(it["answer"])]
        if len(others) < 3:
            continue
        opts = rng.sample(others, 3) + [it["answer"]]
        rng.shuffle(opts)
        out.append({**{k: it.get(k) for k in ("prompt", "context", "sentence_idx", "section_id")},
                    "kind": "mc", "answer": it["answer"], "options": opts, "hint": None,
                    "term_kind": "cause", "level": 2, "origin": "auto"})
    return out


def _eligible(sentence: str) -> bool:
    wc = tp.word_count(sentence)
    if wc < 6 or wc > 50:
        return False
    if sentence.count("(") != sentence.count(")"):
        return False
    letters = sum(ch.isalpha() for ch in sentence)
    return letters / max(len(sentence), 1) > 0.6


def _match_case(text: str) -> str:
    text = text.strip().rstrip(".")
    return text[:1].upper() + text[1:] if text else text


def generate_for_section(section_text: str, keywords: dict[str, dict], title: str,
                         rng: random.Random, max_items: int = 36) -> list[dict]:
    sentences = [x for _, x in tp.section_sentences(section_text)]
    dis = Distractors(keywords, rng)
    items: list[dict] = []
    used_pairs: set = set()

    for idx, s in enumerate(sentences):
        if not _eligible(s):
            continue
        context_ok = not tp.PRONOUN_START.match(s)

        # --- definición -------------------------------------------------------
        m = DEF_RE.match(s.rstrip("."))
        if m and idx <= 2 and tp.word_count(m.group("subj")) <= 8:
            subj = m.group("subj").strip()
            if m.group("art") and m.group("art").lower() in ("el", "la", "los", "las", "the"):
                subj = m.group("art").lower() + " " + subj
            verb = QUESTION_VERB.get(m.group("verb").lower(), "es")
            if not tp.PRONOUN_START.match(subj):
                prompt = (f"What {verb} {subj}?" if verb in ("is", "are", "was", "were")
                          else f"¿Qué {verb} {subj}?")
                items.append({
                    "kind": "open", "prompt": prompt, "answer": _match_case(m.group("pred")),
                    "context": s, "sentence_idx": idx, "hint": None, "options": None,
                })

        # --- interrogación elaborativa (por qué / qué consecuencia) -----------
        mc = CAUSE_AFTER.match(s.rstrip("."))
        if mc:
            claim = mc.group("claim").strip().rstrip(",")
            items.append({
                "kind": "why",
                "prompt": f"¿Por qué {claim[0].lower() + claim[1:]}?",
                "answer": _match_case(mc.group("mk") + " " + mc.group("rest")),
                "context": s, "sentence_idx": idx, "hint": None, "options": None,
            })
        else:
            me = EFFECT_AFTER.match(s.rstrip("."))
            if me:
                cause = me.group("cause").strip().rstrip(",")
                items.append({
                    "kind": "why",
                    "prompt": f"¿Qué consecuencia tiene que {cause[0].lower() + cause[1:]}?",
                    "answer": _match_case(me.group("rest")),
                    "context": s, "sentence_idx": idx, "hint": None, "options": None,
                })

        # --- huecos, opción múltiple y verdadero/falso ----------------------
        terms = tp.find_terms_in_sentence(s, keywords)
        terms = [(t, i) for t, i in terms if tp.normalize(t) not in tp.normalize(title) or i["kind"] == "year"]
        terms.sort(key=lambda ti: -ti[1]["weight"])
        if not terms:
            continue
        weight_cut = 0.9 if context_ok else 1.4

        # --- relación entre conceptos (nivel avanzado) ------------------------
        strong = [t for t, i in terms if i["weight"] >= 1.2 and i["kind"] != "year"
                  and not (i["kind"] == "concept" and tp.VERBISH.search(tp.normalize(t)))]
        pair = _relate_pair(s, strong, used_pairs) if context_ok and tp.word_count(s) >= 10 else None
        if pair and rng.random() < 0.5:
            a, b = pair
            used_pairs.add(frozenset((tp.normalize(a), tp.normalize(b))))
            items.append({
                "kind": "relate", "prompt": f"Según el texto, ¿qué relación hay entre «{a}» y «{b}»?",
                "answer": s, "context": s, "sentence_idx": idx, "hint": None, "options": None,
            })

        terms = [ti for ti in terms if ti[1]["weight"] >= weight_cut][:2]

        for n, (term, info) in enumerate(terms):
            prompt = _blank(s, term)
            if BLANK not in prompt or prompt.strip() == BLANK:
                continue
            kind = info["kind"]
            items.append({
                "kind": "cloze", "prompt": prompt, "answer": term, "context": s,
                "sentence_idx": idx, "hint": _hint(term, kind), "options": None, "term_kind": kind,
            })
            if n == 0:
                ds = dis.pick(term, kind, s, 3)
                if len(ds) == 3:
                    opts = ds + [term]
                    rng.shuffle(opts)
                    items.append({
                        "kind": "mc", "prompt": prompt, "answer": term, "options": opts,
                        "context": s, "sentence_idx": idx, "hint": None, "term_kind": kind,
                    })
                # verdadero / falso: aproximadamente una de cada tres oraciones
                if rng.random() < 0.38:
                    alt = dis.pick(term, kind, s, 4)
                    if kind == "concept":  # concordancia de género y número
                        alt = [a for a in alt if a[-1:] == term[-1:]]
                    if alt and rng.random() < 0.5:
                        false_s = re.sub(rf"(?<![\wáéíóúñü]){re.escape(term)}(?![\wáéíóúñü])",
                                         alt[0], s, count=1)
                        if false_s != s:
                            items.append({
                                "kind": "tf", "prompt": false_s, "answer": "Falso",
                                "options": ["Verdadero", "Falso"], "context": s, "sentence_idx": idx,
                                "hint": None, "swap": [term, alt[0]],
                            })
                    else:
                        items.append({
                            "kind": "tf", "prompt": s, "answer": "Verdadero",
                            "options": ["Verdadero", "Falso"], "context": s, "sentence_idx": idx,
                            "hint": None,
                        })

    items.extend(_statement_mcs(sentences, keywords, title, dis, rng))

    for it in items:
        it.setdefault("level", level_for(it))

    # limitar manteniendo variedad: priorizamos las de desarrollo y repartimos el resto
    if len(items) > max_items:
        special = [i for i in items if i["kind"] in ("open", "why", "relate")]
        rest = [i for i in items if i["kind"] not in ("open", "why", "relate")]
        step = len(rest) / max(max_items - len(special), 1)
        picked = [rest[int(j * step)] for j in range(max(max_items - len(special), 0)) if int(j * step) < len(rest)]
        items = sorted(special + picked, key=lambda i: i["sentence_idx"])
    return items


def generate_topic_items(sections: list[dict], title: str, seed: int) -> tuple[dict, list[list[dict]]]:
    """Genera preguntas para todas las secciones de un tema.

    Devuelve (keywords, items_por_seccion).
    """
    rng = random.Random(seed)
    all_sentences = []
    for s in sections:
        all_sentences.extend(x for _, x in tp.section_sentences(s["text"]))
    keywords = tp.extract_keywords(all_sentences, title)
    per_section = []
    budget = 420
    for s in sections:
        cap = max(8, min(36, budget // max(len(sections), 1)))
        per_section.append(generate_for_section(s["text"], keywords, title, rng, cap))
    return keywords, per_section


LEVELS = {1: "Básico", 2: "Intermedio", 3: "Avanzado"}


def level_for(item: dict) -> int:
    """Nivel de complejidad de una pregunta.

    1 Básico: reconocer (verdadero/falso, opción múltiple).
    2 Intermedio: recordar sin opciones (completar, definir).
    3 Avanzado: explicar causas y relacionar conceptos.
    """
    kind = item.get("kind")
    if kind == "mc" and item.get("term_kind") in ("statement", "cause"):
        return 2
    if kind in ("tf", "mc"):
        return 1
    if kind in ("why", "relate"):
        return 3
    return 2


def generic_why_prompt(sentence: str) -> str:
    return f"Explicá con tus palabras por qué esto es cierto o cómo se relaciona con lo que ya sabés: «{sentence}»"
