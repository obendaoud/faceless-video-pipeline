"""Web research module — DuckDuckGo search to ground LLM scripts in facts."""

from duckduckgo_search import DDGS


def _extract_keywords(topic: str) -> str:
    """Extract meaningful search keywords from a conversational topic."""
    import re
    stop_words = {
        "le", "la", "les", "un", "une", "des", "du", "de", "en", "et",
        "est", "son", "sa", "ses", "ton", "ta", "tes", "peut", "qui",
        "que", "dans", "sur", "par", "pour", "avec", "sans", "ce", "cette",
        "the", "a", "an", "is", "can", "your", "in", "on", "to", "and",
    }
    words = re.findall(r'[a-zà-ÿ0-9]+', topic.lower())
    keywords = [w for w in words if w not in stop_words and len(w) > 1]
    return " ".join(keywords)


def _is_relevant(result: dict, topic: str) -> bool:
    """Check if a search result is topically relevant to the query."""
    import re
    topic_words = set(re.findall(r'[a-zà-ÿ]{3,}', topic.lower()))
    text = f"{result.get('title', '')} {result.get('snippet', '')}".lower()
    matches = sum(1 for w in topic_words if w in text)
    return matches >= 1


def search_topic(topic: str, max_results: int = 8) -> list[dict]:
    query = _extract_keywords(topic)
    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=max_results * 2))
    except Exception:
        return []

    all_results = [
        {
            "title": r.get("title", ""),
            "snippet": r.get("body", "")[:300],
            "source": r.get("href", ""),
        }
        for r in results
    ]
    relevant = [r for r in all_results if _is_relevant(r, topic)]
    return relevant[:max_results] if relevant else all_results[:max_results]


_RESEARCH_HEADERS = {
    "fr": (
        "Contexte factuel (sources web) — ne pas inventer de faits :",
        "FIN RECHERCHE — Utilise UNIQUEMENT les faits ci-dessus. "
        "Ne fabrique pas de noms, chiffres ou citations.",
    ),
    "en": (
        "Factual context (web sources) — do not fabricate facts:",
        "END RESEARCH — Use ONLY the facts above. "
        "Do not fabricate names, numbers, or quotes.",
    ),
    "es": (
        "Contexto factual (fuentes web) — no inventes hechos:",
        "FIN INVESTIGACIÓN — Usa SOLO los hechos anteriores. "
        "No inventes nombres, cifras o citas.",
    ),
    "ar": (
        "سياق واقعي (مصادر ويب) — لا تختلق حقائق:",
        "نهاية البحث — استخدم فقط الحقائق أعلاه. "
        "لا تختلق أسماء أو أرقام أو اقتباسات.",
    ),
}


def format_research_context(results: list[dict], language: str = "fr") -> str:
    if not results:
        return ""

    header, footer = _RESEARCH_HEADERS.get(language, _RESEARCH_HEADERS["fr"])

    lines = [f"=== {header} ===", ""]
    for i, r in enumerate(results, 1):
        lines.append(f"[{i}] {r['title']}")
        lines.append(f"    {r['snippet']}")
        lines.append(f"    Source: {r['source']}")
        lines.append("")

    lines.append(f"=== {footer} ===")
    return "\n".join(lines)


def research_for_script(topic: str, max_results: int = 8, language: str = "fr") -> str:
    results = search_topic(topic, max_results)
    return format_research_context(results, language)
