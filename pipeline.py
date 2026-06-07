#!/usr/bin/env python3
"""
Pipeline semi-automatique de création de vidéos faceless.
Research → Script → Images → TTS → Captions (Whisper) → Assemblage FFmpeg → Upload
"""

import argparse
import os
import sys
import glob
import json
import random
import yaml
from datetime import datetime

from dotenv import load_dotenv
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.prompt import Prompt, Confirm

from src.research import research_for_script
from src.script_generator import generate_script, save_script, load_script
from src.script_validator import validate_script
from src.image_generator import generate_all_images
from src.tts_generator import generate_audio
from src.captions import generate_captions
from src.video_assembler import assemble_video
from src.thumbnail import generate_thumbnails
from src.uploader import upload_video
from src.state import (
    init_state, load_state, save_state,
    start_stage, complete_stage, fail_stage,
    get_resume_stage, is_stage_done,
)

load_dotenv(override=True)
console = Console()


def load_niche(name: str) -> dict:
    path = os.path.join("niches", f"{name}.yaml")
    if not os.path.exists(path):
        console.print(f"[red]Niche '{name}' introuvable. Niches disponibles:[/red]")
        for f in glob.glob("niches/*.yaml"):
            console.print(f"  - {os.path.splitext(os.path.basename(f))[0]}")
        sys.exit(1)
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def get_project_dir(topic: str) -> str:
    slug = "".join(c if c.isalnum() or c in " -_" else "" for c in topic)
    slug = slug.strip().replace(" ", "_")[:50]
    timestamp = datetime.now().strftime("%Y%m%d_%H%M")
    return os.path.join("output", f"{timestamp}_{slug}")


def find_music() -> str | None:
    music_dir = "assets/music"
    if not os.path.isdir(music_dir):
        return None
    files = [
        os.path.join(music_dir, f)
        for f in os.listdir(music_dir)
        if f.endswith((".mp3", ".wav", ".m4a"))
    ]
    return random.choice(files) if files else None


# ── Interactive brief ──────────────────────────────────────────


def interactive_brief() -> dict:
    """Ask QCM questions to build a creative brief for script generation."""
    console.print("\n[bold magenta]═══ BRIEF CRÉATIF ═══[/bold magenta]\n")

    brief = {}

    # 1. Topic (free text)
    brief["topic"] = Prompt.ask("[bold]Sujet de la vidéo[/bold]")

    # 2. Angle
    console.print("\n[bold]Angle narratif:[/bold]")
    console.print("  1. Informatif — expliquer clairement")
    console.print("  2. Parodique — humour et satire")
    console.print("  3. Alarmiste — danger et urgence")
    console.print("  4. Inspirant — motivation et solutions")
    angle_choice = Prompt.ask("Choix", choices=["1", "2", "3", "4"], default="2")
    brief["angle"] = {"1": "informatif", "2": "parodique", "3": "alarmiste", "4": "inspirant"}[angle_choice]

    # 3. Target audience
    console.print("\n[bold]Audience cible:[/bold]")
    console.print("  1. Tech-savvy — connaisseurs tech")
    console.print("  2. Grand public — tout le monde")
    console.print("  3. Professionnels — experts du domaine")
    target_choice = Prompt.ask("Choix", choices=["1", "2", "3"], default="2")
    brief["target"] = {"1": "tech-savvy", "2": "grand public", "3": "professionnels"}[target_choice]

    # 4. Dominant emotion
    console.print("\n[bold]Émotion dominante:[/bold]")
    console.print("  1. Curiosité")
    console.print("  2. Peur")
    console.print("  3. Émerveillement")
    console.print("  4. Indignation")
    emotion_choice = Prompt.ask("Choix", choices=["1", "2", "3", "4"], default="1")
    brief["emotion"] = {"1": "curiosité", "2": "peur", "3": "émerveillement", "4": "indignation"}[emotion_choice]

    # 5. Hook (free text or auto)
    brief["hook"] = Prompt.ask("[bold]Hook d'ouverture[/bold] (ou 'auto')", default="auto")

    # 6. Language
    console.print("\n[bold]Langue:[/bold]")
    console.print("  1. Français")
    console.print("  2. English")
    console.print("  3. Español")
    console.print("  4. العربية")
    lang_choice = Prompt.ask("Choix", choices=["1", "2", "3", "4"], default="1")
    brief["language"] = {"1": "fr", "2": "en", "3": "es", "4": "ar"}[lang_choice]

    # 7. Niche
    available = [
        os.path.splitext(os.path.basename(f))[0]
        for f in sorted(glob.glob("niches/*.yaml"))
    ]
    console.print(f"\n[bold]Niche:[/bold] {', '.join(available)}")
    brief["niche"] = Prompt.ask("Choix", choices=available, default="tech")

    console.print(Panel(
        f"Sujet: {brief['topic']}\nAngle: {brief['angle']}\nCible: {brief['target']}\n"
        f"Émotion: {brief['emotion']}\nHook: {brief['hook']}\nLangue: {brief['language']}\nNiche: {brief['niche']}",
        title="[bold green]Brief créatif[/bold green]",
        border_style="green",
    ))

    return brief


# ── Stage handlers ──────────────────────────────────────────────


def stage_research(state: dict, niche: dict) -> dict:
    console.print("\n[bold cyan]═══ ÉTAPE 1/6: Recherche web ═══[/bold cyan]\n")
    start_stage(state, "research")

    topic = state["topic"]
    console.print(f"[dim]Recherche DuckDuckGo pour: {topic}...[/dim]")

    language = niche.get("script", {}).get("language", "fr")

    try:
        context = research_for_script(topic, language=language)
        lines = [l for l in context.split("\n") if l.strip() and not l.startswith("===")]
        console.print(f"[green]{len(lines)} résultats trouvés[/green]")
        for line in lines[:6]:
            console.print(f"  [dim]{line.strip()[:100]}[/dim]")
    except Exception as e:
        console.print(f"[yellow]Recherche échouée ({e}), on continue sans.[/yellow]")
        context = ""

    complete_stage(state, "research", {"research_context": context})
    return state


def stage_script(state: dict, niche: dict, brief: dict | None = None) -> dict:
    console.print("\n[bold cyan]═══ ÉTAPE 2/6: Génération du script ═══[/bold cyan]\n")

    script_path = os.path.join(state["project_dir"], "script.json")
    if is_stage_done(state, "script") and os.path.exists(script_path):
        if Confirm.ask("[yellow]Script existant trouvé. Le réutiliser?[/yellow]"):
            script = load_script(script_path)
            _display_script(script)
            return state

    start_stage(state, "script")
    research = state.get("artifacts", {}).get("research_context", "")

    # Inject brief context into research if available
    if brief is None:
        brief = state.get("brief")
    if brief:
        brief_context = f"\n\nBRIEF CRÉATIF:\n- Angle: {brief['angle']}\n- Cible: {brief['target']}\n- Émotion dominante: {brief['emotion']}"
        if brief.get("hook") and brief["hook"] != "auto":
            brief_context += f"\n- Hook imposé: {brief['hook']}"
        research = research + brief_context

    console.print(f"[dim]Génération via Claude...[/dim]")
    try:
        script = generate_script(state["topic"], niche, research)
    except Exception as e:
        fail_stage(state, "script", str(e))
        console.print(f"[red]Erreur: {e}[/red]")
        sys.exit(1)

    _display_script(script)

    validation = validate_script(script, niche)
    score_color = "green" if validation["score"] >= 70 else "yellow" if validation["score"] >= 50 else "red"
    console.print(f"\n[{score_color}]Score qualité: {validation['score']}/100[/{score_color}]")
    for w in validation["warnings"]:
        console.print(f"  [yellow]- {w}[/yellow]")

    if not Confirm.ask("\n[bold]Valider ce script?[/bold]"):
        console.print("[yellow]Relance le pipeline pour un nouveau script.[/yellow]")
        sys.exit(0)

    save_script(script, script_path)
    complete_stage(state, "script", {"script_path": script_path})
    return state


def stage_images(state: dict, niche: dict) -> dict:
    console.print("\n[bold cyan]═══ ÉTAPE 3/6: Génération des images ═══[/bold cyan]\n")

    images_dir = os.path.join(state["project_dir"], "images")
    if is_stage_done(state, "images") and os.path.isdir(images_dir):
        existing = sorted(glob.glob(os.path.join(images_dir, "scene_*.png")))
        if existing:
            console.print(f"[green]{len(existing)} images existantes trouvées[/green]")
            if Confirm.ask("[yellow]Réutiliser ces images?[/yellow]"):
                return state

    start_stage(state, "images")
    script = load_script(state["artifacts"]["script_path"])

    vis_section = niche.get("visuals", {})
    vis_config = {
        "model": vis_section.get("model", "black-forest-labs/flux-schnell"),
        "width": vis_section.get("width", 768),
        "height": vis_section.get("height", 1344),
        "style": vis_section.get("style", ""),
    }

    console.print(f"[dim]Génération de {len(script.scenes)} images via Flux Schnell...[/dim]")
    try:
        paths = generate_all_images(
            [s.model_dump() for s in script.scenes], vis_config, images_dir
        )
    except Exception as e:
        fail_stage(state, "images", str(e))
        console.print(f"[red]Erreur: {e}[/red]")
        sys.exit(1)

    for p in paths:
        console.print(f"  [dim]{os.path.basename(p)}[/dim]")
    console.print(f"[green]{len(paths)} images générées[/green]")

    # Character overlay (Wojak)
    char_cfg = niche.get("character", {})
    if char_cfg.get("enabled"):
        from src.character import generate_wojak_set, overlay_all_scenes

        char_type = char_cfg.get("type", "wojak")
        console.print(f"[dim]Génération du personnage {char_type}...[/dim]")

        assets_dir = os.path.join("assets", "characters", char_type)
        emotions = [s.emotion for s in script.scenes]
        generate_wojak_set(assets_dir, emotions)

        overlay_dir = os.path.join(images_dir, "with_character")
        paths = overlay_all_scenes(
            image_paths=paths,
            emotions=emotions,
            output_dir=overlay_dir,
            assets_dir=assets_dir,
            position=char_cfg.get("position", "bottom-right"),
            scale=char_cfg.get("scale", 0.30),
        )
        console.print("[green]Personnage ajouté aux scènes[/green]")

    if not Confirm.ask("\n[bold]Valider les images?[/bold] (vérifie dans le dossier)"):
        console.print("[yellow]Modifie les images puis relance.[/yellow]")
        sys.exit(0)

    complete_stage(state, "images", {"image_paths": paths})
    return state


def stage_audio(state: dict, niche: dict) -> dict:
    console.print("\n[bold cyan]═══ ÉTAPE 4/6: Voix off (TTS) ═══[/bold cyan]\n")

    audio_path = os.path.join(state["project_dir"], "audio", "narration.mp3")
    if is_stage_done(state, "audio") and os.path.exists(audio_path):
        console.print("[green]Audio existant trouvé[/green]")
        if Confirm.ask("[yellow]Réutiliser cet audio?[/yellow]"):
            return state

    start_stage(state, "audio")
    script = load_script(state["artifacts"]["script_path"])

    full_text = script.hook + ". "
    full_text += " ".join(s.narration for s in script.scenes)
    full_text += " " + script.cta

    voice_cfg = niche.get("voice", {})
    voice_name = voice_cfg.get("primary", "fr-FR-HenriNeural")
    console.print(f"[dim]TTS avec voix {voice_name}...[/dim]")

    try:
        generate_audio(full_text, audio_path, voice_cfg)
    except Exception as e:
        fail_stage(state, "audio", str(e))
        console.print(f"[red]Erreur TTS: {e}[/red]")
        sys.exit(1)

    console.print(f"[green]Audio: {audio_path}[/green]")

    if not Confirm.ask("\n[bold]Valider l'audio?[/bold] (écoute le fichier)"):
        console.print("[yellow]Modifie la config voix puis relance.[/yellow]")
        sys.exit(0)

    complete_stage(state, "audio", {"audio_path": audio_path})
    return state


def stage_captions(state: dict, niche: dict) -> dict:
    console.print("\n[bold cyan]═══ ÉTAPE 5/6: Sous-titres (Whisper) ═══[/bold cyan]\n")

    captions_dir = os.path.join(state["project_dir"], "captions")
    if is_stage_done(state, "captions"):
        console.print("[green]Sous-titres existants trouvés[/green]")
        return state

    start_stage(state, "captions")
    audio_path = state["artifacts"]["audio_path"]
    language = niche.get("script", {}).get("language", "fr")
    caption_cfg = niche.get("captions", {})

    console.print(f"[dim]Transcription Whisper (mot par mot)...[/dim]")
    try:
        result = generate_captions(
            audio_path, captions_dir, language,
            video_width=1080, video_height=1920,
            niche_captions=caption_cfg,
        )
    except Exception as e:
        fail_stage(state, "captions", str(e))
        console.print(f"[red]Erreur Whisper: {e}[/red]")
        sys.exit(1)

    console.print(f"[green]ASS: {result['ass_path']}[/green]")
    console.print(f"[green]SRT: {result['srt_path']}[/green]")
    console.print(f"[dim]{len(result['words'])} mots détectés, {len(result['speech_regions'])} régions de parole[/dim]")

    complete_stage(state, "captions", {
        "ass_path": result["ass_path"],
        "srt_path": result["srt_path"],
        "words_json_path": os.path.join(captions_dir, "words.json"),
        "speech_regions": result["speech_regions"],
    })
    return state


def stage_assembly(state: dict, niche: dict) -> dict:
    console.print("\n[bold cyan]═══ ÉTAPE 6/6: Assemblage vidéo (FFmpeg) ═══[/bold cyan]\n")

    if is_stage_done(state, "assembly"):
        console.print(f"[green]Vidéo existante: {state['artifacts'].get('video_path')}[/green]")
        return state

    start_stage(state, "assembly")
    script = load_script(state["artifacts"]["script_path"])

    slug = "".join(c if c.isalnum() or c in " -_" else "" for c in script.title)
    slug = slug.strip().replace(" ", "_")[:40]
    output_path = os.path.join(state["project_dir"], f"{slug}.mp4")

    music_path = find_music()
    if music_path:
        console.print(f"[dim]Musique: {os.path.basename(music_path)}[/dim]")

    vid_section = niche.get("video", {})
    video_config = {
        "width": vid_section.get("width", 1080),
        "height": vid_section.get("height", 1920),
        "fps": vid_section.get("fps", 30),
        "crf": vid_section.get("crf", 23),
    }

    words_json = state["artifacts"].get("words_json_path")
    words = None
    if words_json and os.path.exists(words_json):
        with open(words_json) as f:
            words = json.load(f)

    console.print("[dim]Assemblage FFmpeg (Ken Burns + ASS subs + music ducking)...[/dim]")
    console.print("[dim]Ça peut prendre 1-3 minutes...[/dim]")

    scenes = [s.model_dump() for s in script.scenes]

    try:
        result = assemble_video(
            image_paths=state["artifacts"]["image_paths"],
            audio_path=state["artifacts"]["audio_path"],
            ass_path=state["artifacts"]["ass_path"],
            output_path=output_path,
            config=video_config,
            music_path=music_path,
            speech_regions=state["artifacts"].get("speech_regions"),
            niche_music=niche.get("music"),
            words=words,
            niche_captions=niche.get("captions"),
            scenes=scenes,
            watermark=niche.get("watermark"),
            branding=niche.get("branding"),
            title=script.title,
            cta=script.cta,
            color_palette=niche.get("visuals", {}).get("color_palette"),
        )
    except Exception as e:
        fail_stage(state, "assembly", str(e))
        console.print(f"[red]Erreur FFmpeg: {e}[/red]")
        sys.exit(1)

    console.print(f"\n[bold green]Vidéo créée: {result}[/bold green]")

    console.print("[dim]Génération des thumbnails A/B...[/dim]")
    try:
        thumbs = generate_thumbnails(
            script, state["artifacts"]["image_paths"],
            state["project_dir"], niche,
        )
        for t in thumbs:
            console.print(f"  [green]{os.path.basename(t)}[/green]")
    except Exception as e:
        console.print(f"[yellow]Thumbnails échouées: {e}[/yellow]")
        thumbs = []

    artifacts = {"video_path": result}
    if thumbs:
        artifacts["thumbnail_paths"] = thumbs
    complete_stage(state, "assembly", artifacts)
    return state


# ── Upload (optional) ───────────────────────────────────────────


def stage_upload(state: dict, niche: dict) -> dict:
    if not Confirm.ask("\n[bold]Uploader sur YouTube?[/bold]"):
        return state

    start_stage(state, "upload")
    script = load_script(state["artifacts"]["script_path"])

    upload_cfg = niche.get("upload", {})

    console.print("[dim]Upload YouTube en cours...[/dim]")
    try:
        url = upload_video(
            video_path=state["artifacts"]["video_path"],
            title=script.title,
            description=script.description,
            tags=script.tags,
            srt_path=state["artifacts"].get("srt_path"),
            upload_config=upload_cfg,
        )
    except Exception as e:
        fail_stage(state, "upload", str(e))
        console.print(f"[yellow]Upload échoué: {e}[/yellow]")
        console.print("[dim]Tu peux uploader manuellement.[/dim]")
        return state

    if url:
        console.print(f"[bold green]YouTube: {url}[/bold green]")
        complete_stage(state, "upload", {"youtube_url": url})
    else:
        console.print("[yellow]YouTube non configuré. Upload manuel requis.[/yellow]")

    return state


# ── Helpers ─────────────────────────────────────────────────────


def _display_script(script):
    console.print(Panel(f"[bold]{script.title}[/bold]", title="Titre"))
    console.print(Panel(f"[italic]{script.hook}[/italic]", title="Hook"))

    table = Table(title="Scènes")
    table.add_column("#", style="cyan", width=3)
    table.add_column("Narration", style="white", ratio=3)
    table.add_column("Image prompt", style="dim", ratio=2)

    for scene in script.scenes:
        table.add_row(
            str(scene.scene_number),
            scene.narration,
            scene.image_prompt[:80] + "...",
        )

    console.print(table)
    console.print(Panel(f"[bold green]{script.cta}[/bold green]", title="CTA"))
    console.print(f"[dim]Tags: {', '.join(script.tags)}[/dim]")
    console.print(f"[dim]Description: {script.description[:120]}...[/dim]")


# ── Main ────────────────────────────────────────────────────────


def main():
    parser = argparse.ArgumentParser(description="Faceless video pipeline")
    parser.add_argument("topic", nargs="?", default=None, help="Video topic")
    parser.add_argument("--niche", default="tech", help="Niche profile name")
    parser.add_argument("--resume", metavar="DIR", help="Resume from project directory")
    parser.add_argument("--no-brief", action="store_true", help="Skip interactive brief")
    parser.add_argument("--lang", default=None, help="Override language (fr/en/es/ar)")
    args = parser.parse_args()

    console.print(
        Panel(
            "[bold white]Pipeline Vidéo Faceless v2[/bold white]\n"
            "[dim]Research → Script → Images → TTS → Captions → FFmpeg → Upload[/dim]",
            border_style="cyan",
        )
    )

    brief = None

    # Resume support
    if args.resume:
        state = load_state(args.resume)
        if state:
            resume = get_resume_stage(state)
            console.print(f"[yellow]Reprise depuis l'étape: {resume}[/yellow]")
            brief = state.get("brief")
        else:
            console.print("[red]Aucun état trouvé dans ce dossier.[/red]")
            sys.exit(1)

        niche_name = args.niche if args.niche != "tech" else state.get("niche", "tech")
        niche = load_niche(niche_name)
    else:
        if args.topic or args.no_brief:
            # Direct mode: topic from CLI or prompt
            if args.topic:
                topic = args.topic
            else:
                topic = Prompt.ask("\n[bold]Sujet de la vidéo[/bold]")

            niche_name = args.niche
        else:
            # Interactive brief mode
            brief = interactive_brief()
            topic = brief["topic"]
            niche_name = brief["niche"]

        if not topic.strip():
            console.print("[red]Aucun sujet fourni.[/red]")
            sys.exit(1)

        niche = load_niche(niche_name)

        # Apply --lang override to niche config
        if args.lang:
            niche.setdefault("script", {})["language"] = args.lang

        console.print(f"[dim]Niche: {niche['name']}[/dim]")

        project_dir = get_project_dir(topic)
        state = init_state(project_dir, topic, niche_name)
        if brief:
            state["brief"] = brief
            save_state(state, project_dir)
        console.print(f"[dim]Projet: {project_dir}[/dim]")

    # Run stages (skip completed ones)
    if not is_stage_done(state, "research"):
        stage_research(state, niche)
    if not is_stage_done(state, "script"):
        stage_script(state, niche, brief)
    if not is_stage_done(state, "images"):
        stage_images(state, niche)
    if not is_stage_done(state, "audio"):
        stage_audio(state, niche)
    if not is_stage_done(state, "captions"):
        stage_captions(state, niche)
    if not is_stage_done(state, "assembly"):
        stage_assembly(state, niche)

    stage_upload(state, niche)

    thumb_info = ""
    thumb_paths = state["artifacts"].get("thumbnail_paths", [])
    if thumb_paths:
        thumb_info = f"[white]Thumbnails:[/white] {', '.join(os.path.basename(t) for t in thumb_paths)}\n"

    console.print(
        Panel(
            f"[bold green]Pipeline terminé![/bold green]\n\n"
            f"[white]Vidéo:[/white] {state['artifacts'].get('video_path', 'N/A')}\n"
            f"[white]SRT:[/white] {state['artifacts'].get('srt_path', 'N/A')}\n"
            f"{thumb_info}"
            f"[white]Projet:[/white] {state['project_dir']}\n\n"
            f"[dim]Pour reprendre un pipeline crashé: --resume {state['project_dir']}[/dim]",
            title="Résultat",
            border_style="green",
        )
    )


if __name__ == "__main__":
    main()
