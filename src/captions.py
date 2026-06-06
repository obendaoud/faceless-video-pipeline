"""Word-level captions using Whisper — generates ASS (karaoke highlight) + SRT."""

import os
import json
from faster_whisper import WhisperModel


def transcribe_word_level(audio_path: str, language: str = "fr", model_size: str = "base") -> list[dict]:
    model = WhisperModel(model_size, device="cpu", compute_type="int8")

    segments, _ = model.transcribe(
        audio_path, language=language, word_timestamps=True
    )

    words = []
    for segment in segments:
        if segment.words:
            for w in segment.words:
                words.append(
                    {
                        "word": w.word.strip(),
                        "start": round(w.start, 3),
                        "end": round(w.end, 3),
                    }
                )

    return words


def group_words(words: list[dict], words_per_group: int = 4) -> list[dict]:
    groups = []
    for i in range(0, len(words), words_per_group):
        chunk = words[i : i + words_per_group]
        groups.append(
            {
                "words": chunk,
                "text": " ".join(w["word"] for w in chunk),
                "start": chunk[0]["start"],
                "end": chunk[-1]["end"],
            }
        )
    return groups


def _ass_time(seconds: float) -> str:
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    cs = int((seconds % 1) * 100)
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"


def generate_ass(
    words: list[dict],
    output_path: str,
    video_width: int = 1080,
    video_height: int = 1920,
    niche_captions: dict | None = None,
) -> str:
    cfg = niche_captions or {}
    highlight = cfg.get("highlight_color", "&H0000FFFF")
    base_color = cfg.get("base_color", "&H00FFFFFF")
    outline = cfg.get("outline_color", "&H00000000")
    font = cfg.get("font", "Arial")
    font_size = cfg.get("font_size", 18)
    bold = -1 if cfg.get("bold", True) else 0
    outline_width = cfg.get("outline_width", 3)
    words_per_group = cfg.get("words_per_group", 4)
    position_y = cfg.get("position_y", 85)

    margin_v = int(video_height * (100 - position_y) / 100)

    groups = group_words(words, words_per_group)

    header = f"""[Script Info]
Title: Auto-generated captions
ScriptType: v4.00+
PlayResX: {video_width}
PlayResY: {video_height}
WrapStyle: 0

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,{font},{font_size},{base_color},{highlight},{outline},&H80000000,{bold},0,0,0,100,100,0,0,1,{outline_width},1,2,40,40,{margin_v},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

    events = []
    for group in groups:
        start = _ass_time(group["start"])
        end = _ass_time(group["end"])

        parts = []
        for w in group["words"]:
            dur_cs = int((w["end"] - w["start"]) * 100)
            parts.append(f"{{\\kf{dur_cs}}}{w['word']}")

        line = " ".join(parts) if not parts else "".join(
            f"{{\\kf{int((w['end'] - w['start']) * 100)}}}{w['word']} "
            for w in group["words"]
        ).rstrip()

        events.append(f"Dialogue: 0,{start},{end},Default,,0,0,0,,{line}")

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(header)
        f.write("\n".join(events))
        f.write("\n")

    return output_path


def generate_srt(words: list[dict], output_path: str, words_per_group: int = 4) -> str:
    groups = group_words(words, words_per_group)

    with open(output_path, "w", encoding="utf-8") as f:
        for i, group in enumerate(groups, 1):
            start = _srt_time(group["start"])
            end = _srt_time(group["end"])
            f.write(f"{i}\n{start} --> {end}\n{group['text']}\n\n")

    return output_path


def _srt_time(seconds: float) -> str:
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    ms = int((seconds % 1) * 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def generate_captions(
    audio_path: str,
    output_dir: str,
    language: str = "fr",
    video_width: int = 1080,
    video_height: int = 1920,
    niche_captions: dict | None = None,
) -> dict:
    os.makedirs(output_dir, exist_ok=True)

    niche_cfg = niche_captions or {}
    model_size = niche_cfg.get("whisper_model", "base")
    words = transcribe_word_level(audio_path, language, model_size)

    words_json = os.path.join(output_dir, "words.json")
    with open(words_json, "w", encoding="utf-8") as f:
        json.dump(words, f, ensure_ascii=False, indent=2)

    wpg = (niche_captions or {}).get("words_per_group", 4)

    ass_path = generate_ass(
        words,
        os.path.join(output_dir, "captions.ass"),
        video_width,
        video_height,
        niche_captions,
    )

    srt_path = generate_srt(
        words, os.path.join(output_dir, "captions.srt"), wpg
    )

    silence_gap = niche_cfg.get("silence_gap", 0.5)
    speech_regions = []
    if words:
        region_start = words[0]["start"]
        region_end = words[0]["end"]
        for w in words[1:]:
            if w["start"] - region_end < silence_gap:
                region_end = w["end"]
            else:
                speech_regions.append((region_start, region_end))
                region_start = w["start"]
                region_end = w["end"]
        speech_regions.append((region_start, region_end))

    return {
        "ass_path": ass_path,
        "srt_path": srt_path,
        "words_path": words_json,
        "words": words,
        "speech_regions": speech_regions,
    }
