"""Script generation — multi-provider LLM with research grounding and niche awareness."""

import json
import os
import anthropic
from pydantic import BaseModel


class Scene(BaseModel):
    scene_number: int
    narration: str
    image_prompt: str
    duration_hint: str


class VideoScript(BaseModel):
    title: str
    description: str
    tags: list[str]
    hook: str
    scenes: list[Scene]
    cta: str


SYSTEM_PROMPT = """Tu es un scénariste expert en contenu vidéo court format pour YouTube Shorts, TikTok et Instagram Reels.

Niche: {niche_name}
Ton: {tone}
Langue: {language}

Règles:
- Le hook (3-5 secondes) doit immédiatement captiver. Styles recommandés: {hook_styles}
- Chaque scène dure 5-10 secondes de narration.
- Le texte de narration doit être naturel, parlé, pas écrit. Phrases courtes.
- Les image_prompt doivent décrire une illustration en anglais. Style: {visual_style}
- Sujets visuels recommandés: {visual_subjects}
- Éviter dans les visuels: {visual_avoid}
- CTA style: {cta_style}
- Total: {max_scenes} scènes pour {duration_target} de vidéo.
- INTERDIT: {forbidden}

Tu dois aussi générer un titre YouTube accrocheur, une description avec hashtags, et des tags pertinents."""

USER_PROMPT = """Crée un script vidéo court format sur le sujet suivant:

**Sujet:** {topic}

{research_context}

Réponds UNIQUEMENT avec un JSON valide:
{{
  "title": "Titre accrocheur pour YouTube (max 100 chars)",
  "description": "Description YouTube avec hashtags et CTA (max 300 chars)",
  "tags": ["tag1", "tag2", "tag3", "tag4", "tag5"],
  "hook": "Phrase d'accroche captivante (3-5 sec)",
  "scenes": [
    {{
      "scene_number": 1,
      "narration": "Texte de narration parlé pour cette scène",
      "image_prompt": "Detailed English image description: digital illustration of...",
      "duration_hint": "5-8s"
    }}
  ],
  "cta": "Call-to-action final engageant"
}}"""


def _build_prompts(topic: str, niche: dict, research: str) -> tuple[str, str]:
    script_cfg = niche.get("script", {})
    vis_cfg = niche.get("visuals", {})

    system = SYSTEM_PROMPT.format(
        niche_name=niche.get("name", "Général"),
        tone=script_cfg.get("tone", "engageant"),
        language=script_cfg.get("language", "fr"),
        hook_styles=", ".join(script_cfg.get("hooks", ["Question provocante"])),
        visual_style=vis_cfg.get("style", "modern digital illustration"),
        visual_subjects=", ".join(vis_cfg.get("subjects", [])),
        visual_avoid=", ".join(vis_cfg.get("avoid", [])),
        cta_style=script_cfg.get("cta_style", "Abonne-toi"),
        max_scenes=script_cfg.get("max_scenes", 6),
        duration_target=script_cfg.get("duration_target", "45-55 secondes"),
        forbidden=", ".join(script_cfg.get("forbidden", [])),
    )

    user = USER_PROMPT.format(
        topic=topic,
        research_context=research if research else "(Pas de recherche disponible)",
    )

    return system, user


def generate_script(
    topic: str,
    niche: dict,
    research_context: str = "",
    provider: str = "anthropic",
) -> VideoScript:
    system, user = _build_prompts(topic, niche, research_context)

    if provider == "anthropic":
        text = _call_anthropic(system, user, niche)
    elif provider == "openai":
        text = _call_openai(system, user, niche)
    else:
        text = _call_anthropic(system, user, niche)

    start = text.find("{")
    end = text.rfind("}") + 1
    data = json.loads(text[start:end])

    return VideoScript(**data)


def _call_anthropic(system: str, user: str, niche: dict) -> str:
    client = anthropic.Anthropic()
    model = niche.get("llm", {}).get("model", "claude-haiku-4-5-20251001")

    response = client.messages.create(
        model=model,
        max_tokens=2048,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    return response.content[0].text


def _call_openai(system: str, user: str, niche: dict) -> str:
    from openai import OpenAI

    client = OpenAI()
    model = niche.get("llm", {}).get("openai_model", "gpt-4o-mini")

    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        response_format={"type": "json_object"},
        max_tokens=2048,
    )
    return response.choices[0].message.content


def save_script(script: VideoScript, path: str) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(script.model_dump(), f, ensure_ascii=False, indent=2)


def load_script(path: str) -> VideoScript:
    with open(path, encoding="utf-8") as f:
        return VideoScript(**json.load(f))
