"""TTS with fallback chain: Edge-TTS (free) → ElevenLabs (premium) → macOS say."""

import asyncio
import os
import subprocess
import edge_tts


async def _edge_tts(text: str, voice: str, rate: str, pitch: str, output_path: str) -> str:
    communicate = edge_tts.Communicate(text, voice, rate=rate, pitch=pitch)
    await communicate.save(output_path)
    return output_path


def _elevenlabs_tts(text: str, output_path: str) -> str:
    api_key = os.environ.get("ELEVENLABS_API_KEY")
    if not api_key:
        raise RuntimeError("ELEVENLABS_API_KEY not set")

    import httpx

    resp = httpx.post(
        "https://api.elevenlabs.io/v1/text-to-speech/21m00Tcm4TlvDq8ikWAM",
        headers={"xi-api-key": api_key, "Content-Type": "application/json"},
        json={
            "text": text,
            "model_id": "eleven_multilingual_v2",
            "voice_settings": {"stability": 0.5, "similarity_boost": 0.75},
        },
        timeout=120,
    )
    resp.raise_for_status()

    with open(output_path, "wb") as f:
        f.write(resp.content)

    return output_path


def _macos_say(text: str, output_path: str) -> str:
    aiff = output_path.replace(".mp3", ".aiff")
    subprocess.run(["say", "-o", aiff, text], check=True)
    subprocess.run(
        ["ffmpeg", "-y", "-i", aiff, "-q:a", "2", output_path],
        capture_output=True,
        check=True,
    )
    os.remove(aiff)
    return output_path


def generate_audio(
    text: str, output_path: str, niche_voice: dict | None = None
) -> str:
    cfg = niche_voice or {}
    voice = cfg.get("primary", "fr-FR-HenriNeural")
    fallback_voice = cfg.get("fallback", "fr-FR-DeniseNeural")
    rate = cfg.get("rate", "+5%")
    pitch = cfg.get("pitch", "+0Hz")

    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)

    try:
        asyncio.run(_edge_tts(text, voice, rate, pitch, output_path))
        return output_path
    except Exception:
        pass

    try:
        asyncio.run(_edge_tts(text, fallback_voice, rate, pitch, output_path))
        return output_path
    except Exception:
        pass

    if os.environ.get("ELEVENLABS_API_KEY"):
        try:
            return _elevenlabs_tts(text, output_path)
        except Exception:
            pass

    try:
        return _macos_say(text, output_path)
    except Exception:
        raise RuntimeError("All TTS providers failed")
