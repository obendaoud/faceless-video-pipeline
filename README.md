<p align="center">
  <h1 align="center">🎬 Automate Video</h1>
  <p align="center">
    <strong>🇫🇷 Pipeline open-source pour créer des vidéos faceless avec l'IA</strong><br>
    <strong>🇬🇧 Open-source AI pipeline for faceless video creation</strong><br><br>
    YouTube Shorts · TikTok · Instagram Reels
  </p>
  <p align="center">
    <img src="https://img.shields.io/badge/python-3.11+-blue?logo=python&logoColor=white" alt="Python">
    <img src="https://img.shields.io/badge/cost-~%240.03%2Fvideo-brightgreen" alt="Cost">
    <img src="https://img.shields.io/badge/license-MIT-green" alt="License">
    <img src="https://img.shields.io/badge/FFmpeg-powered-orange?logo=ffmpeg&logoColor=white" alt="FFmpeg">
    <img src="https://img.shields.io/badge/Claude-AI-blueviolet?logo=anthropic&logoColor=white" alt="Claude">
  </p>
</p>

---

> 🇫🇷 **Un sujet en entrée, une vidéo prête à publier en sortie.** Semi-automatique : tu valides chaque étape.
>
> 🇬🇧 **One topic in, a publish-ready video out.** Semi-automatic: you validate each step.

```
📝 Topic → 🔍 Research → ✍️ AI Script → 🎨 AI Images → 🎙️ Voiceover → 💬 Karaoke Subs → 🎬 9:16 Video → 🚀 Upload
```

---

## ⚡ Quick Start

```bash
# 1. Clone
git clone https://github.com/ton-user/automate-video.git
cd automate-video

# 2. Setup
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt

# 3. Config
cp .env.example .env
# ✏️ Edit .env → add ANTHROPIC_API_KEY + REPLICATE_API_TOKEN

# 4. Run! / Lance !
.venv/bin/python pipeline.py "5 free AI tools that replace $200 software"
```

---

## 💰 Cost per video / Coût par vidéo

| Step / Étape | Tool / Outil | Cost / Coût |
|:-------------|:-------------|:------------|
| 🔍 Factual research / Recherche factuelle | DuckDuckGo | **Free / Gratuit** |
| ✍️ Script + metadata | Claude API (Haiku) | **~$0.01** |
| 🎨 Images per scene / Images par scène | Replicate Flux Schnell | **~$0.02** |
| 🎙️ Voiceover / Voix off | Edge-TTS (Microsoft) | **Free / Gratuit** |
| 💬 Karaoke subtitles / Sous-titres karaoké | Whisper (local) | **Free / Gratuit** |
| 🎬 Video assembly / Assemblage vidéo | FFmpeg | **Free / Gratuit** |
| 🚀 YouTube upload | YouTube Data API v3 | **Free / Gratuit** |
| | | **Total : ~$0.03** |

---

## 🎭 Niches

> 🇫🇷 Le système de niches YAML pilote **tout** le pipeline : ton du script, style visuel, voix, couleur des sous-titres, volume de la musique.
>
> 🇬🇧 The YAML niche system drives **everything** in the pipeline: script tone, visual style, voice, subtitle color, music volume.

```bash
# 💻 Tech (default / défaut)
.venv/bin/python pipeline.py "How to use Cursor AI" --niche tech

# 💸 Finance
.venv/bin/python pipeline.py "3 mistakes ruining your savings" --niche finance

# 📖 Storytelling
.venv/bin/python pipeline.py "The crazy story of the 15-year-old hacker" --niche storytelling
```

> 🧩 Create your own profile in `niches/your-niche.yaml` by copying an existing one.
>
> 🧩 Crée ton propre profil dans `niches/ta-niche.yaml` en copiant un existant.

---

## 🔥 Features

### 🔍 Anti-hallucination research / Recherche anti-hallucination
> 🇬🇧 Before generating the script, DuckDuckGo fetches **8 factual sources** injected into the prompt. The LLM is forbidden from inventing beyond these facts.
>
> 🇫🇷 Avant de générer le script, DuckDuckGo récupère **8 sources factuelles** injectées dans le prompt. Le LLM a interdiction d'inventer au-delà de ces faits.

### 💬 Karaoke subtitles (word by word) / Sous-titres karaoké (mot par mot)
> 🇬🇧 Whisper transcribes audio with **per-word timestamps**. The active word changes color in real time (ASS format). Color is configurable per niche.
>
> 🇫🇷 Whisper transcrit l'audio avec des **timestamps par mot**. Le mot actif change de couleur en temps réel (format ASS). La couleur est configurable par niche.

### 🎥 Ken Burns on every image / Ken Burns sur chaque image
> 🇬🇧 Each scene gets a **cinematic zoom/pan effect** via FFmpeg `zoompan` filters. Three effects alternate: zoom in, zoom out, lateral pan.
>
> 🇫🇷 Chaque scène a un effet de **zoom/pan cinématique** via les filtres `zoompan` de FFmpeg. Trois effets alternent : zoom in, zoom out, pan latéral.

### 🎵 Smart music ducking / Music ducking intelligent
> 🇬🇧 Background music **automatically lowers** when voice is speaking and **rises during silences**. Based on speech regions detected by Whisper.
>
> 🇫🇷 La musique de fond **baisse automatiquement** quand la voix parle et **remonte dans les silences**. Basé sur les régions de parole détectées par Whisper.

### 💾 State machine + resume
> 🇬🇧 Each step saves its state in `state.json`. If the pipeline crashes, resume **exactly where it stopped**.
>
> 🇫🇷 Chaque étape sauvegarde son état dans `state.json`. Si le pipeline crash, reprends **exactement où il s'est arrêté**.

```bash
.venv/bin/python pipeline.py --resume output/20260604_1530_my_topic
```

### 🎙️ TTS fallback chain
```
Edge-TTS (free/gratuit) → ElevenLabs (premium) → macOS say
```
> 🇬🇧 If one provider fails, the next one takes over automatically.
>
> 🇫🇷 Si un provider échoue, le suivant prend le relais automatiquement.

### 🤖 Multi-provider LLM
> 🇬🇧 Claude (default), OpenAI, or any compatible provider. Configurable per niche.
>
> 🇫🇷 Claude (défaut), OpenAI, ou n'importe quel provider compatible. Configurable par niche.

### 🚀 Automatic YouTube upload / Upload YouTube automatique
> OAuth2 + resumable upload + SRT captions + full metadata

```bash
# One-time setup / Setup unique
.venv/bin/python -m src.uploader --setup
```

---

## 🏗️ Architecture

```
📦 automate-video/
├── 🎬 pipeline.py              ← Entry point / Point d'entrée
├── ⚙️ config.yaml              ← Global config / Config globale
├── 🔑 .env.example             ← API keys template / Template clés API
│
├── 🎭 niches/
│   ├── tech.yaml               ← 💻 Tech / Tutorials
│   ├── finance.yaml            ← 💸 Finance / Business
│   └── storytelling.yaml       ← 📖 Storytelling / Stories
│
├── 🧠 src/
│   ├── research.py             ← 🔍 DuckDuckGo → factual context
│   ├── script_generator.py     ← ✍️ Claude/OpenAI → structured JSON script
│   ├── image_generator.py      ← 🎨 Replicate Flux → per-scene images
│   ├── tts_generator.py        ← 🎙️ Edge-TTS / ElevenLabs / macOS → MP3
│   ├── captions.py             ← 💬 Whisper → ASS karaoke + SRT
│   ├── video_assembler.py      ← 🎬 FFmpeg → final 9:16 video
│   ├── state.py                ← 💾 State machine (crash resume)
│   └── uploader.py             ← 🚀 YouTube Data API v3 (OAuth2)
│
├── 🎵 assets/music/            ← Background music / Musiques de fond
└── 📁 output/                  ← Generated videos / Vidéos générées
```

---

## 📋 Requirements / Pré-requis

| Required / Requis | Install |
|:-------------------|:--------|
| 🐍 Python 3.11+ | [python.org](https://python.org) |
| 🎬 FFmpeg | `brew install ffmpeg` (macOS) · `apt install ffmpeg` (Linux) |
| 🔑 Anthropic API key / Clé API Anthropic | [console.anthropic.com](https://console.anthropic.com) |
| 🔑 Replicate API key / Clé API Replicate | [replicate.com](https://replicate.com) |

**Optional / Optionnel :**

| Service | Usage |
|:--------|:------|
| 🎙️ ElevenLabs | Premium TTS (fallback) |
| 🤖 OpenAI | Alternative LLM provider |
| 📺 YouTube API | Automatic upload / Upload automatique |

---

## 🎵 Background music / Musique de fond

> 🇬🇧 Drop MP3/WAV files in `assets/music/`. The pipeline picks one **at random** and applies automatic ducking.
>
> 🇫🇷 Dépose des fichiers MP3/WAV dans `assets/music/`. Le pipeline en choisit un **au hasard** et applique le ducking automatique.

Royalty-free music sources / Sources de musique libre de droits :
- 🎹 [Pixabay Music](https://pixabay.com/music/)
- 🎸 [Uppbeat](https://uppbeat.io/)
- 🥁 [Mixkit](https://mixkit.co/free-stock-music/)

---

## ⚙️ Configuration

| File / Fichier | Role / Rôle |
|:---------------|:------------|
| `config.yaml` | Global parameters / Paramètres globaux |
| `niches/*.yaml` | Per-niche profiles (override everything) / Profils par niche (surchargent tout) |
| `.env` | API keys (never commit) / Clés API (jamais commit) |

---

## 🗺️ Roadmap

- [ ] 📱 Automatic TikTok upload / Upload TikTok automatique
- [ ] 📸 Instagram Reels upload
- [ ] 🖼️ AI thumbnail generation / Génération de thumbnails IA
- [ ] 🔄 Batch mode (N videos in one command / N vidéos en une commande)
- [ ] 📡 Topic discovery (Reddit, Google Trends, RSS)
- [ ] 🔔 Notifications (Discord, Telegram)
- [ ] 🐳 Docker

---

## 🙏 Credits & Inspirations / Crédits & Inspirations

> 🇬🇧 This project builds on ideas from these amazing open-source repos.
>
> 🇫🇷 Ce projet s'inspire des meilleures idées de ces repos open-source.

| Repo | What we took / Ce qu'on a pris | Author / Auteur |
|:-----|:-------------------------------|:----------------|
| 🎬 [auto-yt-shorts](https://github.com/marvinvr/auto-yt-shorts) | Karaoke word-by-word subtitles, random background music, gameplay overlay / Sous-titres karaoké mot par mot, musique de fond aléatoire, overlay gameplay | [@marvinvr](https://github.com/marvinvr) |
| 🚀 [youtube-shorts-pipeline](https://github.com/rushindrasinha/youtube-shorts-pipeline) | Pure FFmpeg, ASS word-level highlights, music ducking, YAML niches, state machine resume, anti-hallucination research, TTS fallback chain / FFmpeg pur, ASS highlights, music ducking, niches YAML, state machine resume, recherche anti-hallucination, TTS fallback | [@rushindrasinha](https://github.com/rushindrasinha) |

**Tools & services / Outils & services :**

| Tool / Outil | Author / Auteur | Usage |
|:-------------|:----------------|:------|
| 🤖 [Claude API](https://docs.anthropic.com) | [Anthropic](https://anthropic.com) | Script generation / Génération de scripts |
| 🎨 [Flux Schnell](https://replicate.com/black-forest-labs/flux-schnell) | [Black Forest Labs](https://blackforestlabs.ai) | Image generation / Génération d'images |
| 🎙️ [Edge-TTS](https://github.com/rany2/edge-tts) | [@rany2](https://github.com/rany2) | Free text-to-speech / TTS gratuit |
| 🗣️ [faster-whisper](https://github.com/SYSTRAN/faster-whisper) | [SYSTRAN](https://github.com/SYSTRAN) | Word-level transcription / Transcription mot par mot |
| 🎬 [FFmpeg](https://ffmpeg.org) | FFmpeg team | Video assembly, Ken Burns, ASS burn-in, audio mixing |
| 🦆 [duckduckgo-search](https://github.com/deedy5/duckduckgo_search) | [@deedy5](https://github.com/deedy5) | Web research / Recherche web |
| ✨ [Rich](https://github.com/Textualize/rich) | [Textualize](https://github.com/Textualize) | CLI interface |

---

## 📄 License

MIT — do whatever you want / fais ce que tu veux.

---

<p align="center">
  <strong>⭐ Star this repo if you find it useful! / Star ce repo si tu trouves ça utile !</strong><br>
  <sub>Built with 🤖 Claude + 🎨 Flux + 🎙️ Edge-TTS + 🎬 FFmpeg</sub>
</p>
