"""Shared lexical helpers used by retrieval scoring and the offline answerer."""
from __future__ import annotations

import re
from typing import Iterable, Set

_WORD_RE = re.compile(r"[a-z0-9]+")

STOPWORDS = frozenset(
    {
        "a", "an", "and", "any", "are", "as", "at", "be", "been", "but", "by",
        "can", "did", "do", "does", "for", "from", "get", "had", "has", "have",
        "how", "i", "if", "in", "into", "is", "it", "its", "many", "may", "me",
        "much", "must", "my", "no", "not", "of", "on", "or", "our", "out",
        "per", "shall", "should", "so", "some", "such", "than", "that", "the",
        "their", "them", "then", "there", "these", "they", "this", "to", "us",
        "was", "we", "were", "what", "when", "where", "which", "who", "will",
        "with", "would", "you", "your",
    }
)


def stem(word: str) -> str:
    """Crude suffix stripper.

    Good enough to match apply/applied/applies or leave/leaves, which is what
    keyword-overlap scoring needs. Not a linguistic stemmer - the rules are
    ordered so the plural and past-tense forms of a word collapse onto the same
    stem rather than onto different ones.
    """
    if len(word) <= 3 or word.isdigit():
        return word

    # carries -> carry, carried -> carry
    if len(word) > 4 and (word.endswith("ies") or word.endswith("ied")):
        return word[:-3] + "y"
    # leaves -> leave, notes -> note
    if len(word) > 4 and word.endswith("es"):
        return word[:-1]
    # documents -> document, but never business -> busines
    if word.endswith("s") and not word.endswith("ss"):
        return word[:-1]
    # working -> work
    if len(word) > 5 and word.endswith("ing"):
        return word[:-3]
    # credited -> credit
    if len(word) > 4 and word.endswith("ed"):
        return word[:-2]
    # internationally -> international, but never apply -> app
    if word.endswith("ly") and len(word) - 2 >= 5:
        return word[:-2]
    return word


def tokenize(text: str) -> list[str]:
    """Lowercase word tokens."""
    return _WORD_RE.findall(text.lower())


def content_words(text: str, min_length: int = 3) -> Set[str]:
    """Stemmed, stopword-free vocabulary of a piece of text."""
    return {
        stem(word)
        for word in tokenize(text)
        if word not in STOPWORDS and len(word) >= min_length
    }


def overlap_ratio(question: str, text: str) -> float:
    """Fraction of the question's content words that appear in ``text``."""
    q_words = content_words(question)
    if not q_words:
        return 0.0
    t_words = {stem(word) for word in tokenize(text)}
    return len(q_words & t_words) / len(q_words)


def any_overlap(words: Iterable[str], text: str) -> bool:
    """True when any of ``words`` (already stemmed) appears in ``text``."""
    t_words = {stem(word) for word in tokenize(text)}
    return bool(set(words) & t_words)
