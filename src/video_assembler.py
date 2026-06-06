"""Video assembly using FFmpeg + Pillow subtitle burn-in (no libass dependency)."""

import json
import os
import shutil
import subprocess
import tempfile
from PIL import Image, ImageDraw, ImageFont
import numpy as np


ZOOMPAN_EFFECTS = [
    "zoompan=z='min(zoom+0.0008,1.12)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={frames}:s={w}x{h}:fps={fps}",
    "zoompan=z='if(eq(on,1),1.12,max(zoom-0.0008,1.0))':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={frames}:s={w}x{h}:fps={fps}",
    "zoompan=z='min(zoom+0.0008,1.12)':x='if(eq(on,1),0,x+1)':y='ih/2-(ih/zoom/2)':d={frames}:s={w}x{h}:fps={fps}",
]


def _prepare_image(image_path: str, width: int, height: int, output_path: str) -> str:
    img = Image.open(image_path).convert("RGB")

    img_ratio = img.width / img.height
    target_ratio = width / height

    if img_ratio > target_ratio:
        new_h = height
        new_w = int(new_h * img_ratio)
    else:
        new_w = width
        new_h = int(new_w / img_ratio)

    img = img.resize((new_w, new_h), Image.LANCZOS)

    left = (new_w - width) // 2
    top = (new_h - height) // 2
    img = img.crop((left, top, left + width, top + height))
    img.save(output_path, quality=95)

    return output_path


def _build_music_ducking_filter(
    speech_regions: list[tuple[float, float]],
    normal_vol: float,
    ducked_vol: float,
) -> str:
    if not speech_regions:
        return f"volume={normal_vol}"

    conditions = []
    for start, end in speech_regions:
        conditions.append(f"between(t,{start:.2f},{end:.2f})")

    speech_expr = "+".join(conditions)
    return f"volume='{ducked_vol}+({normal_vol}-{ducked_vol})*(1-({speech_expr}))':eval=frame"


def _find_font(size: int) -> ImageFont.FreeTypeFont:
    """Auto-detect a bold font across platforms, falling back gracefully."""
    import platform

    candidates = []
    if platform.system() == "Darwin":
        candidates = [
            "/System/Library/Fonts/Supplemental/Impact.ttf",
            "/System/Library/Fonts/Helvetica.ttc",
            "/Library/Fonts/Arial Bold.ttf",
        ]
    elif platform.system() == "Linux":
        candidates = [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        ]
    else:
        candidates = ["C:/Windows/Fonts/impact.ttf", "C:/Windows/Fonts/arialbd.ttf"]

    for path in candidates:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except OSError:
                continue
    return ImageFont.load_default(size)


def _render_subtitle_frames(
    words: list[dict],
    video_width: int,
    video_height: int,
    fps: int,
    duration: float,
    output_dir: str,
    niche_captions: dict | None = None,
) -> str:
    """Render Hormozi-style subtitle overlays: centered, UPPERCASE, word-by-word yellow highlight."""
    cfg = niche_captions or {}
    font_size = cfg.get("font_size", 72)
    words_per_group = cfg.get("words_per_group", 2)
    position_y_pct = cfg.get("position_y", 45)

    # Parse highlight color — support hex (#FFD93D) or fall back to yellow
    highlight_hex = cfg.get("highlight_color_hex", cfg.get("highlight_color", "#FFD93D"))
    if isinstance(highlight_hex, str) and highlight_hex.startswith("#"):
        h = highlight_hex.lstrip("#")
        highlight_color = (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16), 255)
    else:
        highlight_color = (255, 217, 61, 255)  # #FFD93D

    white = (255, 255, 255, 255)
    stroke_color = (0, 0, 0, 255)
    stroke_width = 3
    pad_x, pad_y = 30, 18

    font = _find_font(font_size)

    # Group words into chunks
    groups = []
    for i in range(0, len(words), words_per_group):
        chunk = words[i : i + words_per_group]
        groups.append({
            "words": chunk,
            "text": " ".join(w["word"].upper() for w in chunk),
            "start": float(chunk[0]["start"]),
            "end": float(chunk[-1]["end"]),
        })

    total_frames = int(duration * fps)
    os.makedirs(output_dir, exist_ok=True)

    blank = Image.new("RGBA", (video_width, video_height), (0, 0, 0, 0))
    blank_path = os.path.join(output_dir, "blank.png")
    blank.save(blank_path)

    frame_map = {}

    for group in groups:
        group_words = group["words"]
        text_upper = group["text"]

        # Measure full text to compute background box
        measure_img = Image.new("RGBA", (1, 1), (0, 0, 0, 0))
        measure_draw = ImageDraw.Draw(measure_img)
        bbox = measure_draw.textbbox((0, 0), text_upper, font=font)
        text_w = bbox[2] - bbox[0]
        text_h = bbox[3] - bbox[1]

        box_w = text_w + pad_x * 2
        box_h = text_h + pad_y * 2
        box_x = (video_width - box_w) // 2
        box_y = int(video_height * position_y_pct / 100) - box_h // 2

        # Generate one frame per word in the group (word-by-word highlight)
        for wi, w in enumerate(group_words):
            word_start = int(float(w["start"]) * fps)
            word_end = int(float(w["end"]) * fps)

            img = Image.new("RGBA", (video_width, video_height), (0, 0, 0, 0))
            draw = ImageDraw.Draw(img)

            # Semi-transparent rounded background
            draw.rounded_rectangle(
                [(box_x, box_y), (box_x + box_w, box_y + box_h)],
                radius=14,
                fill=(0, 0, 0, 180),
            )

            # Draw each word — active word in highlight color, others in white
            cursor_x = box_x + pad_x
            text_y = box_y + pad_y

            for wj, ww in enumerate(group_words):
                word_text = ww["word"].upper()
                fill = highlight_color if wj == wi else white

                draw.text(
                    (cursor_x, text_y), word_text, font=font,
                    fill=fill,
                    stroke_width=stroke_width, stroke_fill=stroke_color,
                )

                w_bbox = measure_draw.textbbox((0, 0), word_text, font=font)
                w_width = w_bbox[2] - w_bbox[0]
                cursor_x += w_width

                # Add space between words
                if wj < len(group_words) - 1:
                    space_bbox = measure_draw.textbbox((0, 0), " ", font=font)
                    cursor_x += space_bbox[2] - space_bbox[0]

            frame_path = os.path.join(output_dir, f"sub_{word_start:06d}_w{wi}.png")
            img.save(frame_path)

            for f_idx in range(word_start, min(word_end + 1, total_frames)):
                frame_map[f_idx] = frame_path

    concat_file = os.path.join(output_dir, "subs_concat.txt")
    with open(concat_file, "w") as f:
        for f_idx in range(total_frames):
            path = frame_map.get(f_idx, blank_path)
            f.write(f"file '{path}'\n")
            f.write(f"duration {1/fps:.6f}\n")

    return concat_file


def assemble_video(
    image_paths: list[str],
    audio_path: str,
    ass_path: str,
    output_path: str,
    config: dict,
    music_path: str | None = None,
    speech_regions: list[tuple[float, float]] | None = None,
    niche_music: dict | None = None,
    niche_captions: dict | None = None,
    words: list[dict] | None = None,
) -> str:
    width = config.get("width", 1080)
    height = config.get("height", 1920)
    fps = config.get("fps", 30)

    music_cfg = niche_music or {}
    normal_vol = music_cfg.get("volume_normal", 0.15)
    ducked_vol = music_cfg.get("volume_ducked", 0.04)
    fade_out = music_cfg.get("fade_out", 1.0)

    duration = _get_audio_duration(audio_path)
    scene_duration = duration / len(image_paths)
    frames_per_scene = int(scene_duration * fps)

    with tempfile.TemporaryDirectory() as tmpdir:
        prepared = []
        for i, img in enumerate(image_paths):
            out = os.path.join(tmpdir, f"img_{i:03d}.png")
            _prepare_image(img, width, height, out)
            prepared.append(out)

        scene_clips = []
        for i, img in enumerate(prepared):
            clip_path = os.path.join(tmpdir, f"clip_{i:03d}.ts")
            effect = ZOOMPAN_EFFECTS[i % len(ZOOMPAN_EFFECTS)].format(
                frames=frames_per_scene, w=width, h=height, fps=fps
            )

            cmd = [
                "ffmpeg", "-y", "-loop", "1", "-i", img,
                "-vf", effect,
                "-t", f"{scene_duration:.3f}",
                "-c:v", "libx264", "-preset", "fast",
                "-pix_fmt", "yuv420p",
                "-an", clip_path,
            ]
            subprocess.run(cmd, capture_output=True, check=True)
            scene_clips.append(clip_path)

        concat_file = os.path.join(tmpdir, "concat.txt")
        with open(concat_file, "w") as f:
            for clip in scene_clips:
                f.write(f"file '{clip}'\n")

        raw_video = os.path.join(tmpdir, "raw.mp4")
        subprocess.run(
            [
                "ffmpeg", "-y", "-f", "concat", "-safe", "0",
                "-i", concat_file,
                "-c:v", "libx264", "-preset", "medium",
                "-pix_fmt", "yuv420p",
                "-an", raw_video,
            ],
            capture_output=True,
            check=True,
        )

        # Add audio (voice + optional music with ducking)
        if music_path and os.path.exists(music_path):
            ducking_filter = _build_music_ducking_filter(
                speech_regions or [], normal_vol, ducked_vol
            )
            fade_filter = f"afade=t=out:st={max(0, duration - fade_out):.2f}:d={fade_out}"

            cmd = [
                "ffmpeg", "-y",
                "-i", raw_video,
                "-i", audio_path,
                "-i", music_path,
                "-filter_complex",
                f"[1:a]aformat=sample_fmts=fltp:sample_rates=44100:channel_layouts=stereo[voice];"
                f"[2:a]aloop=loop=-1:size=44100*{int(duration)+1},{ducking_filter},{fade_filter},"
                f"atrim=0:{duration:.3f},aformat=sample_fmts=fltp:sample_rates=44100:channel_layouts=stereo[music];"
                f"[voice][music]amix=inputs=2:duration=first[aout]",
                "-map", "0:v",
                "-map", "[aout]",
                "-c:v", "copy",
                "-c:a", "aac", "-b:a", "192k",
                "-t", f"{duration:.3f}",
                os.path.join(tmpdir, "with_audio.mp4"),
            ]
            subprocess.run(cmd, capture_output=True, check=True)
            video_with_audio = os.path.join(tmpdir, "with_audio.mp4")
        else:
            video_with_audio = os.path.join(tmpdir, "with_voice.mp4")
            subprocess.run(
                [
                    "ffmpeg", "-y",
                    "-i", raw_video, "-i", audio_path,
                    "-map", "0:v", "-map", "1:a",
                    "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
                    "-t", f"{duration:.3f}",
                    video_with_audio,
                ],
                capture_output=True,
                check=True,
            )

        # Burn in subtitles using Pillow overlay (no libass needed)
        os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)

        if words:
            subs_dir = os.path.join(tmpdir, "subs")
            subs_concat = _render_subtitle_frames(
                words, width, height, fps, duration, subs_dir, niche_captions
            )

            subs_video = os.path.join(tmpdir, "subs.mp4")
            subprocess.run(
                [
                    "ffmpeg", "-y",
                    "-f", "concat", "-safe", "0",
                    "-i", subs_concat,
                    "-c:v", "png",
                    "-pix_fmt", "rgba",
                    subs_video,
                ],
                capture_output=True,
                check=True,
            )

            subprocess.run(
                [
                    "ffmpeg", "-y",
                    "-i", video_with_audio,
                    "-i", subs_video,
                    "-filter_complex", "[0:v][1:v]overlay=0:0:shortest=1[outv]",
                    "-map", "[outv]",
                    "-map", "0:a",
                    "-c:v", "libx264", "-preset", "medium", "-crf", "18",
                    "-c:a", "copy",
                    output_path,
                ],
                capture_output=True,
                check=True,
            )
        else:
            shutil.copy2(video_with_audio, output_path)

    return output_path


def _get_audio_duration(audio_path: str) -> float:
    result = subprocess.run(
        [
            "ffprobe", "-v", "quiet",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            audio_path,
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    return float(result.stdout.strip())
