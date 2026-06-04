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


def format_research_context(results: list[dict]) -> str:
    if not results:
        return ""

    lines = [
        "=== RECHERCHE WEB (données factuelles — ne pas inventer au-delà) ===",
        "",
    ]
    for i, r in enumerate(results, 1):
        lines.append(f"[{i}] {r['title']}")
        lines.append(f"    {r['snippet']}")
        lines.append(f"    Source: {r['source']}")
        lines.append("")

    lines.append(
        "=== FIN RECHERCHE — Utilise UNIQUEMENT les faits ci-dessus. "
        "Ne fabrique pas de noms, chiffres ou citations. ==="
    )
    return "\n".join(lines)


def research_for_script(topic: str, max_results: int = 8) -> str:
    results = search_topic(topic, max_results)
    return format_research_context(results)
