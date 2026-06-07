"""Web research module — DuckDuckGo search to ground LLM scripts in facts."""

from duckduckgo_search import DDGS


def search_topic(topic: str, max_results: int = 8) -> list[dict]:
    with DDGS() as ddgs:
        results = list(ddgs.text(topic, max_results=max_results))
    return [
        {
            "title": r.get("title", ""),
            "snippet": r.get("body", "")[:300],
            "source": r.get("href", ""),
        }
        for r in results
    ]


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
