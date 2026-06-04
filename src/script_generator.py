"""Script generation — storytelling-first approach with narrative arc."""

import json
import os
import anthropic
from pydantic import BaseModel


class Scene(BaseModel):
    scene_number: int
    narration: str
    image_prompt: str
    emotion: str
    duration_hint: str


class VideoScript(BaseModel):
    title: str
    description: str
    tags: list[str]
    hook: str
    scenes: list[Scene]
    cta: str


SYSTEM_PROMPT = """Tu es un SCÉNARISTE, pas un professeur. Tu écris des histoires courtes qui captivent en 50 secondes.

=== TA SEULE RÈGLE ===
Chaque vidéo raconte une HISTOIRE avec un arc narratif. JAMAIS une liste de faits.

=== STRUCTURE NARRATIVE OBLIGATOIRE ===

HOOK (Scene 1) — 5 sec
→ Une phrase qui FORCE à rester. Pas une question générique. Une affirmation choquante, une situation concrète, un "tu" qui interpelle.
→ Émotion : curiosité ou peur

BUILD (Scenes 2-3) — 15 sec
→ Tu MONTRES le problème. Pas "il existe un problème", mais une scène concrète qu'on VISUALISE.
→ Le spectateur doit se dire "attends, quoi ??"
→ Émotion : montée de tension

CLIMAX (Scene 4) — 8 sec
→ Le moment "oh merde". La révélation. Le retournement. Ce qu'on n'avait pas vu venir.
→ Émotion : choc ou surprise

RESOLUTION (Scenes 5-6) — 15 sec
→ La solution ou la leçon. Concrète, actionnable. Pas de morale vague.
→ Émotion : empowerment, on repart avec quelque chose

=== STYLE D'ÉCRITURE ===
- Tu parles comme un pote qui raconte un truc dingue, pas comme un prof
- Phrases COURTES. 5-10 mots max. Rythme punchy.
- "Tu" direct, pas "on" ou "il"
- Zéro jargon non expliqué
- Chaque phrase fait AVANCER l'histoire, jamais de remplissage
- Si une phrase n'ajoute pas de tension ou d'émotion, SUPPRIME-LA

=== ERREURS INTERDITES ===
- "Saviez-vous que..." / "Imaginez..." / "Dans cet vidéo..." → INTERDIT. Commence IN MEDIA RES.
- Lister des faits sans fil narratif → INTERDIT
- Conclure par "voilà" / "maintenant vous savez" → INTERDIT. Finis sur un PUNCH.
- Narration passive et descriptive → INTERDIT. Raconte, montre, fais ressentir.

=== IMAGE PROMPTS ===
- Style: {visual_style}
- JAMAIS de texte dans l'image
- Chaque image doit transmettre l'ÉMOTION de la scène, pas illustrer les mots
- Pense cinéma : angles, lumière, ambiance. Pas clipart.

=== CONTEXTE ===
Niche: {niche_name}
Langue: {language}
Durée cible: {duration_target}
Max scènes: {max_scenes}"""

USER_PROMPT = """Écris un script vidéo court format sur ce sujet :

**{topic}**

{research_context}

Réponds UNIQUEMENT en JSON :
{{
  "title": "Titre accrocheur (max 80 chars, pas de emoji)",
  "description": "Description YouTube avec hashtags (max 300 chars)",
  "tags": ["tag1", "tag2", "tag3", "tag4", "tag5"],
  "hook": "La phrase d'accroche — doit CHOQUER ou INTRIGUER en 3 secondes",
  "scenes": [
    {{
      "scene_number": 1,
      "narration": "Texte parlé pour cette scène — COURT et PUNCHY",
      "image_prompt": "English cinematic image description, no text in image, convey the EMOTION",
      "emotion": "curiosity/tension/shock/fear/empowerment/relief",
      "duration_hint": "5s"
    }}
  ],
  "cta": "Call-to-action final — pas de 'abonne-toi', finis sur un PUNCH"
}}"""


def _build_prompts(topic: str, niche: dict, research: str) -> tuple[str, str]:
    script_cfg = niche.get("script", {})
    vis_cfg = niche.get("visuals", {})

    system = SYSTEM_PROMPT.format(
        niche_name=niche.get("name", "Général"),
        language=script_cfg.get("language", "fr"),
        visual_style=vis_cfg.get("style", "cinematic digital art, dramatic lighting"),
        duration_target=script_cfg.get("duration_target", "45-55 secondes"),
        max_scenes=script_cfg.get("max_scenes", 6),
    )

    user = USER_PROMPT.format(
        topic=topic,
        research_context=research if research else "",
    )

    return system, user


def generate_script(
    topic: str,
    niche: dict,
    research_context: str = "",
    provider: str = "anthropic",
) -> VideoScript:
    system, user = _build_prompts(topic, niche, research_context)

    if provider == "openai":
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
