"""Posting language detection without extra dependencies (stopword voting)."""

from __future__ import annotations

import re

_STOPWORDS_TEXT = {
    "en": """the and of to in for with you are will our your we is as on be this that from have
             at or an by""",
    "es": """el la los las de del y en para con por una un que se es su sus al nuestro nuestra
             experiencia trabajo equipo como más""",
    "pt": """o a os as de do da e em para com por uma um que se é seu sua ao nosso nossa
             experiência trabalho equipe""",
    "fr": """le la les de du des et en pour avec par une un que est votre vos au notre nos
             expérience travail équipe""",
    "de": """der die das und in für mit von zu den ist sie ihre wir unser unsere erfahrung
             arbeit team ein eine""",
}
_STOPWORDS = {lang: frozenset(text.split()) for lang, text in _STOPWORDS_TEXT.items()}
_WORD_RE = re.compile(r"[a-záéíóúñüàâçèêëîïôûäöß]+", re.I)


def detect_language(text: str, default: str = "en") -> str:
    """Most likely language among en/es/pt/fr/de; ambiguous or too-short text → ``default``."""
    words = [w.lower() for w in _WORD_RE.findall(text[:6000])]
    if len(words) < 20:
        return default
    scores = {lang: sum(w in sw for w in words) for lang, sw in _STOPWORDS.items()}
    best, second = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)[:2]
    if best[1] < 5 or best[1] < second[1] * 1.25:
        return default
    return best[0]
