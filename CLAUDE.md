# CLAUDE.md

## Project Overview

Pipeline Python semi-automatique pour creer des videos faceless (YouTube Shorts, TikTok, Instagram Reels). Chaque etape genere des artefacts valides par l'utilisateur avant de continuer.

Flow: Research (DuckDuckGo) -> Script (Claude API) -> Images (Replicate Flux) -> TTS (Edge-TTS) -> Captions (Whisper ASS) -> Assembly (FFmpeg) -> Upload (YouTube API)

## Tech Stack

- **Language**: Python 3.11+, no type stubs, use `|` union syntax
- **LLM**: Anthropic SDK (`anthropic` package), model `claude-haiku-4-5-20251001` by default
- **Images**: Replicate SDK, model `black-forest-labs/flux-schnell`
- **TTS**: `edge-tts` (async, Microsoft voices), fallback to ElevenLabs REST API, then macOS `say`
- **Captions**: `faster-whisper` (CTranslate2 backend, CPU int8), outputs ASS (karaoke) + SRT
- **Video**: Pure FFmpeg via `subprocess.run()` — no MoviePy. Uses `zoompan`, `concat`, `libass`, `amix` filters
- **CLI**: `rich` for interactive prompts, panels, tables
- **Config**: YAML niche profiles in `niches/`, dotenv for secrets
- **State**: JSON state machine in `state.json` per project, enables resume

## Project Structure

```
pipeline.py              Entry point — orchestrates all stages
config.yaml              Global config (mostly superseded by niche profiles)
niches/*.yaml            Niche profiles — control EVERYTHING (script tone, visuals, voice, captions, music)
src/
  research.py            DuckDuckGo search -> factual context for LLM
  script_generator.py    LLM script gen with Pydantic models (VideoScript, Scene)
  image_generator.py     Replicate Flux image generation per scene
  tts_generator.py       TTS with 3-tier fallback chain
  captions.py            Whisper word-level transcription -> ASS + SRT
  video_assembler.py     FFmpeg pipeline: Ken Burns + ASS burn-in + music ducking
  state.py               Stage-based state machine with JSON persistence
  uploader.py            YouTube Data API v3 OAuth2 resumable upload
assets/music/            Background music files (MP3/WAV)
output/                  Generated projects (gitignored)
```

## Commands

```bash
# Run pipeline (interactive)
.venv/bin/python pipeline.py

# Run with topic and niche
.venv/bin/python pipeline.py "topic here" --niche tech

# Resume crashed pipeline
.venv/bin/python pipeline.py --resume output/YYYYMMDD_HHMM_slug

# Setup YouTube OAuth (one-time)
.venv/bin/python -m src.uploader --setup

# Install deps
.venv/bin/pip install -r requirements.txt
```

## Coding Conventions

- All source files in `src/`, entry point is `pipeline.py`
- Pydantic models for structured data (`VideoScript`, `Scene`)
- Functions return paths as strings, not Path objects
- FFmpeg called via `subprocess.run(cmd, capture_output=True, check=True)`
- Async only in TTS module (edge-tts requires it), wrapped with `asyncio.run()`
- State machine stages: `research`, `script`, `images`, `audio`, `captions`, `assembly`, `upload`
- Each stage handler: `start_stage()` -> do work -> `complete_stage()` with artifacts dict
- Niche YAML is the single source of truth for pipeline behavior per content type
- Secrets in `.env`, never hardcoded, loaded via `python-dotenv`
- Console output via `rich.console.Console` — never bare `print()` in pipeline.py
- Error handling: `fail_stage()` then `sys.exit(1)` in pipeline stages
- Image prompts always in English (even for French scripts) for better AI generation
- ASS subtitle colors in BGR hex format (e.g., `&H0000FFFF` = yellow)

## Key Design Decisions

- **FFmpeg over MoviePy**: faster, more reliable, no Python GIL issues on video processing
- **Edge-TTS over paid TTS**: free, good quality, 300+ voices, built-in for MVP
- **faster-whisper over openai-whisper**: no PyTorch dependency, uses CTranslate2, much lighter
- **DuckDuckGo over Google**: no API key needed, good enough for anti-hallucination grounding
- **Replicate Flux over DALL-E**: better price ($0.003/image), higher quality for illustrations
- **ASS over SRT for video**: supports per-word color highlighting (karaoke effect)
- **SRT kept alongside ASS**: needed for YouTube caption upload
- **Semi-auto over full-auto**: user validates script/images/audio before expensive assembly step
- **State machine with JSON**: simple, no DB needed, human-readable, enables `--resume`

## Adding a New Niche

Copy `niches/tech.yaml`, rename, and customize all sections: `script`, `visuals`, `voice`, `captions`, `music`, `thumbnail`, `topics`. The niche YAML controls every pipeline stage.

## Environment Variables

Required:
- `ANTHROPIC_API_KEY` — Claude API
- `REPLICATE_API_TOKEN` — Replicate (Flux images)

Optional:
- `ELEVENLABS_API_KEY` — Premium TTS fallback
- `OPENAI_API_KEY` — Alternative LLM provider
- `YOUTUBE_CLIENT_ID` / `YOUTUBE_CLIENT_SECRET` — YouTube upload
