"""Shared text utilities for memory/retrieval scoring.

Single source of truth for stopwords + lexical overlap. Both validate.py
(dream-cycle promotion gate) and context_budget.py (retrieval) depend on it,
so drift here would quietly make the two layers see different words.
"""
import re

STOPWORDS = frozenset({
    "the", "a", "an", "and", "or", "but", "is", "are", "was", "were", "be",
    "been", "being", "have", "has", "had", "do", "does", "did", "will",
    "would", "should", "could", "may", "might", "must", "can", "this",
    "that", "these", "those", "of", "in", "on", "at", "to", "for", "with",
    "by", "from", "as", "if", "then", "when", "where", "how", "why", "what",
    "it", "its", "their", "our", "we", "you", "i", "not", "no",
})


def word_set(text):
    """Lowercase content words (3+ chars, stopwords removed)."""
    return {t.lower() for t in re.findall(r"[a-zA-Z][a-zA-Z0-9_-]{2,}", text or "")
            if t.lower() not in STOPWORDS}


def jaccard(a, b):
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)
