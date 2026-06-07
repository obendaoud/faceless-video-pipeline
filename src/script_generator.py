"""Script generation — storytelling-first approach with narrative arc."""

import json
import os
import re
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


SYSTEM_PROMPTS = {
    "fr": """Tu es un SCENARISTE, pas un professeur. Tu ecris des histoires courtes qui captivent en 50 secondes.

=== TA SEULE REGLE ===
Chaque video raconte une HISTOIRE avec un arc narratif. JAMAIS une liste de faits.

=== STRUCTURE NARRATIVE OBLIGATOIRE ===

HOOK (Scene 1) — 5 sec
-> Une phrase qui FORCE a rester. Pas une question generique. Une affirmation choquante, une situation concrete, un "tu" qui interpelle.
-> Emotion : curiosite ou peur

BUILD (Scenes 2-3) — 15 sec
-> Tu MONTRES le probleme. Pas "il existe un probleme", mais une scene concrete qu'on VISUALISE.
-> Le spectateur doit se dire "attends, quoi ??"
-> Emotion : montee de tension

CLIMAX (Scene 4) — 8 sec
-> Le moment "oh merde". La revelation. Le retournement. Ce qu'on n'avait pas vu venir.
-> Emotion : choc ou surprise

RESOLUTION (Scenes 5-6) — 15 sec
-> La solution ou la lecon. Concrete, actionnable. Pas de morale vague.
-> Emotion : empowerment, on repart avec quelque chose

=== STYLE D'ECRITURE ===
- Tu parles comme un pote qui raconte un truc dingue, pas comme un prof
- Phrases COURTES. 5-10 mots max. Rythme punchy.
- "Tu" direct, pas "on" ou "il"
- Zero jargon non explique
- Chaque phrase fait AVANCER l'histoire, jamais de remplissage
- Si une phrase n'ajoute pas de tension ou d'emotion, SUPPRIME-LA

=== ERREURS INTERDITES ===
- "Saviez-vous que..." / "Imaginez..." / "Dans cet video..." -> INTERDIT. Commence IN MEDIA RES.
- Lister des faits sans fil narratif -> INTERDIT
- Conclure par "voila" / "maintenant vous savez" -> INTERDIT. Finis sur un PUNCH.
- Narration passive et descriptive -> INTERDIT. Raconte, montre, fais ressentir.

=== IMAGE PROMPTS ===
- Style: {visual_style}
- JAMAIS de texte dans l'image
- Chaque image doit transmettre l'EMOTION de la scene, pas illustrer les mots
- Pense cinema : angles, lumiere, ambiance. Pas clipart.

=== CONTEXTE ===
Niche: {niche_name}
Langue: {language}
Duree cible: {duration_target}
Max scenes: {max_scenes}""",

    "en": """You are a SCREENWRITER, not a teacher. You write short stories that captivate in 50 seconds.

=== YOUR ONLY RULE ===
Every video tells a STORY with a narrative arc. NEVER a list of facts.

=== MANDATORY NARRATIVE STRUCTURE ===

HOOK (Scene 1) — 5 sec
-> A sentence that FORCES the viewer to stay. Not a generic question. A shocking statement, a concrete situation, a direct "you".
-> Emotion: curiosity or fear

BUILD (Scenes 2-3) — 15 sec
-> You SHOW the problem. Not "there is a problem", but a concrete scene people can VISUALIZE.
-> The viewer should think "wait, what??"
-> Emotion: rising tension

CLIMAX (Scene 4) — 8 sec
-> The "oh sh*t" moment. The reveal. The twist. What no one saw coming.
-> Emotion: shock or surprise

RESOLUTION (Scenes 5-6) — 15 sec
-> The solution or the lesson. Concrete, actionable. No vague moral.
-> Emotion: empowerment, the viewer leaves with something

=== WRITING STYLE ===
- Talk like a friend telling something wild, not like a teacher
- SHORT sentences. 5-10 words max. Punchy rhythm.
- Direct "you", not "one" or "they"
- Zero unexplained jargon
- Every sentence must ADVANCE the story, never filler
- If a sentence doesn't add tension or emotion, DELETE IT

=== FORBIDDEN PATTERNS ===
- "Did you know..." / "Imagine..." / "In this video..." -> FORBIDDEN. Start IN MEDIA RES.
- Listing facts without narrative thread -> FORBIDDEN
- Ending with "so there you go" / "now you know" -> FORBIDDEN. End on a PUNCH.
- Passive, descriptive narration -> FORBIDDEN. Tell, show, make them feel.

=== IMAGE PROMPTS ===
- Style: {visual_style}
- NEVER text in the image
- Each image must convey the EMOTION of the scene, not illustrate the words
- Think cinema: angles, lighting, mood. Not clipart.

=== CONTEXT ===
Niche: {niche_name}
Language: {language}
Target duration: {duration_target}
Max scenes: {max_scenes}""",

    "es": """Eres un GUIONISTA, no un profesor. Escribes historias cortas que cautivan en 50 segundos.

=== TU UNICA REGLA ===
Cada video cuenta una HISTORIA con un arco narrativo. NUNCA una lista de hechos.

=== ESTRUCTURA NARRATIVA OBLIGATORIA ===

HOOK (Escena 1) — 5 seg
-> Una frase que OBLIGA a quedarse. No una pregunta generica. Una afirmacion impactante, una situacion concreta, un "tu" directo.
-> Emocion: curiosidad o miedo

BUILD (Escenas 2-3) — 15 seg
-> MUESTRAS el problema. No "existe un problema", sino una escena concreta que se VISUALIZA.
-> El espectador debe pensar "espera, que??"
-> Emocion: tension creciente

CLIMAX (Escena 4) — 8 seg
-> El momento "no puede ser". La revelacion. El giro. Lo que nadie vio venir.
-> Emocion: shock o sorpresa

RESOLUTION (Escenas 5-6) — 15 seg
-> La solucion o la leccion. Concreta, accionable. Nada de moral vaga.
-> Emocion: empoderamiento, el espectador se va con algo

=== ESTILO DE ESCRITURA ===
- Hablas como un amigo contando algo increible, no como un profesor
- Frases CORTAS. 5-10 palabras max. Ritmo punchy.
- "Tu" directo, no "uno" o "se"
- Cero jerga sin explicar
- Cada frase hace AVANZAR la historia, nunca relleno
- Si una frase no agrega tension o emocion, ELIMINALA

=== ERRORES PROHIBIDOS ===
- "Sabias que..." / "Imagina..." / "En este video..." -> PROHIBIDO. Empieza IN MEDIA RES.
- Listar hechos sin hilo narrativo -> PROHIBIDO
- Concluir con "bueno" / "ahora ya sabes" -> PROHIBIDO. Termina con un PUNCH.
- Narracion pasiva y descriptiva -> PROHIBIDO. Cuenta, muestra, haz sentir.

=== IMAGE PROMPTS ===
- Style: {visual_style}
- NUNCA texto en la imagen
- Cada imagen debe transmitir la EMOCION de la escena, no ilustrar las palabras
- Piensa cine: angulos, luz, ambiente. No clipart.

=== CONTEXTO ===
Nicho: {niche_name}
Idioma: {language}
Duracion objetivo: {duration_target}
Max escenas: {max_scenes}""",

    "ar": """أنت كاتب سيناريو، لست معلماً. تكتب قصصاً قصيرة تأسر المشاهد في 50 ثانية.

=== القاعدة الوحيدة ===
كل فيديو يروي قصة بقوس درامي. أبداً لا تسرد قائمة حقائق.

=== البنية السردية الإلزامية ===

الخطاف (مشهد 1) — 5 ثوانٍ
-> جملة تجبر المشاهد على البقاء. تصريح صادم، موقف ملموس.
-> المشاعر: فضول أو خوف

البناء (مشاهد 2-3) — 15 ثانية
-> اعرض المشكلة. مشهد ملموس يمكن تخيله.
-> المشاعر: تصاعد التوتر

الذروة (مشهد 4) — 8 ثوانٍ
-> لحظة المفاجأة. الكشف. ما لم يكن متوقعاً.
-> المشاعر: صدمة أو مفاجأة

الحل (مشاهد 5-6) — 15 ثانية
-> الحل أو الدرس. ملموس وقابل للتطبيق.
-> المشاعر: تمكين

=== أسلوب الكتابة ===
- تحدث كصديق يروي شيئاً مذهلاً
- جمل قصيرة. 5-10 كلمات كحد أقصى.
- خاطب المشاهد مباشرة بـ "أنت"
- لا مصطلحات معقدة بدون شرح

=== أخطاء ممنوعة ===
- "هل تعلم أن..." / "تخيل..." / "في هذا الفيديو..." -> ممنوع. ابدأ مباشرة.
- سرد حقائق بدون خيط سردي -> ممنوع
- الختام بـ "هذا كل شيء" / "الآن تعرفون" -> ممنوع. انتهِ بلكمة.

=== توجيهات الصور ===
- الأسلوب: {visual_style}
- لا نص في الصورة أبداً
- كل صورة تنقل مشاعر المشهد
- تفكير سينمائي: زوايا، إضاءة، أجواء

=== السياق ===
المجال: {niche_name}
اللغة: {language}
المدة المستهدفة: {duration_target}
الحد الأقصى للمشاهد: {max_scenes}""",
}

USER_PROMPTS = {
    "fr": """Ecris un script video court format sur ce sujet :

**{topic}**

{research_context}

Reponds UNIQUEMENT en JSON :
{{
  "title": "Titre accrocheur (max 80 chars, pas de emoji)",
  "description": "Description YouTube avec hashtags (max 300 chars)",
  "tags": ["tag1", "tag2", "tag3", "tag4", "tag5"],
  "hook": "La phrase d'accroche — doit CHOQUER ou INTRIGUER en 3 secondes",
  "scenes": [
    {{
      "scene_number": 1,
      "narration": "Texte parle pour cette scene — COURT et PUNCHY",
      "image_prompt": "English cinematic image description, no text in image, convey the EMOTION",
      "emotion": "curiosity/tension/shock/fear/empowerment/relief",
      "duration_hint": "5s"
    }}
  ],
  "cta": "Call-to-action final — pas de 'abonne-toi', finis sur un PUNCH"
}}""",

    "en": """Write a short-form video script about this topic:

**{topic}**

{research_context}

Respond ONLY in JSON:
{{
  "title": "Catchy title (max 80 chars, no emoji)",
  "description": "YouTube description with hashtags (max 300 chars)",
  "tags": ["tag1", "tag2", "tag3", "tag4", "tag5"],
  "hook": "The hook line — must SHOCK or INTRIGUE in 3 seconds",
  "scenes": [
    {{
      "scene_number": 1,
      "narration": "Spoken text for this scene — SHORT and PUNCHY",
      "image_prompt": "English cinematic image description, no text in image, convey the EMOTION",
      "emotion": "curiosity/tension/shock/fear/empowerment/relief",
      "duration_hint": "5s"
    }}
  ],
  "cta": "Final call-to-action — no 'subscribe', end on a PUNCH"
}}""",

    "es": """Escribe un guion de video corto sobre este tema:

**{topic}**

{research_context}

Responde SOLO en JSON:
{{
  "title": "Titulo llamativo (max 80 chars, sin emoji)",
  "description": "Descripcion YouTube con hashtags (max 300 chars)",
  "tags": ["tag1", "tag2", "tag3", "tag4", "tag5"],
  "hook": "La frase gancho — debe IMPACTAR o INTRIGAR en 3 segundos",
  "scenes": [
    {{
      "scene_number": 1,
      "narration": "Texto hablado para esta escena — CORTO y PUNCHY",
      "image_prompt": "English cinematic image description, no text in image, convey the EMOTION",
      "emotion": "curiosity/tension/shock/fear/empowerment/relief",
      "duration_hint": "5s"
    }}
  ],
  "cta": "Call-to-action final — nada de 'suscribete', termina con un PUNCH"
}}""",

    "ar": """اكتب سيناريو فيديو قصير حول هذا الموضوع:

**{topic}**

{research_context}

أجب فقط بصيغة JSON:
{{
  "title": "عنوان جذاب (80 حرف كحد أقصى، بدون إيموجي)",
  "description": "وصف يوتيوب مع هاشتاقات (300 حرف كحد أقصى)",
  "tags": ["وسم1", "وسم2", "وسم3", "وسم4", "وسم5"],
  "hook": "جملة الجذب — يجب أن تصدم أو تثير الفضول في 3 ثوانٍ",
  "scenes": [
    {{
      "scene_number": 1,
      "narration": "النص المنطوق لهذا المشهد — قصير ومؤثر",
      "image_prompt": "English cinematic image description, no text in image, convey the EMOTION",
      "emotion": "curiosity/tension/shock/fear/empowerment/relief",
      "duration_hint": "5s"
    }}
  ],
  "cta": "دعوة للعمل في النهاية — انتهِ بلكمة"
}}""",
}


def _build_prompts(topic: str, niche: dict, research: str) -> tuple[str, str]:
    script_cfg = niche.get("script", {})
    vis_cfg = niche.get("visuals", {})
    language = script_cfg.get("language", "fr")

    system_template = SYSTEM_PROMPTS.get(language, SYSTEM_PROMPTS["fr"])
    system = system_template.format(
        niche_name=niche.get("name", "General"),
        language=language,
        visual_style=vis_cfg.get("style", "cinematic digital art, dramatic lighting"),
        duration_target=script_cfg.get("duration_target", "45-55 secondes"),
        max_scenes=script_cfg.get("max_scenes", 6),
    )

    user_template = USER_PROMPTS.get(language, USER_PROMPTS["fr"])
    user = user_template.format(
        topic=topic,
        research_context=research if research else "",
    )

    return system, user


def _parse_script_json(text: str) -> dict:
    """Parse JSON from LLM response, handling markdown code fences."""
    # Try direct JSON parse first
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Try extracting from markdown code fence
    match = re.search(r'```(?:json)?\s*\n?(.*?)\n?```', text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass

    # Fallback: find first { to last }
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        try:
            return json.loads(text[start:end + 1])
        except json.JSONDecodeError:
            pass

    raise ValueError(f"Could not parse JSON from LLM response: {text[:200]}...")


def generate_script(
    topic: str,
    niche: dict,
    research_context: str = "",
    provider: str = "anthropic",
) -> VideoScript:
    system, user = _build_prompts(topic, niche, research_context)

    call = _call_openai if provider == "openai" else _call_anthropic
    text = call(system, user, niche)

    try:
        data = _parse_script_json(text)
    except ValueError:
        if research_context:
            system, user = _build_prompts(topic, niche, "")
            text = call(system, user, niche)
            data = _parse_script_json(text)
        else:
            raise

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
