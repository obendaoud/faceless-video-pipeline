"""Video assembly using FFmpeg + Pillow subtitle burn-in (no libass dependency)."""

import json
import os
import random
import shutil
import subprocess
import tempfile
from PIL import Image, ImageDraw, ImageFont
import numpy as np
import platform


ZOOMPAN_EFFECTS = [
    # Zoom in center
    "zoompan=z='min(zoom+0.0015,1.5)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={frames}:s={w}x{h}:fps={fps}",
    # Zoom out from center
    "zoompan=z='if(lte(zoom,1.0),1.5,max(1.001,zoom-0.0015))':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={frames}:s={w}x{h}:fps={fps}",
    # Pan right
    "zoompan=z='1.15':x='if(lte(on,1),0,min(x+2,iw-iw/zoom))':y='ih/2-(ih/zoom/2)':d={frames}:s={w}x{h}:fps={fps}",
    # Pan left
    "zoompan=z='1.15':x='if(lte(on,1),iw/zoom,max(0,x-2))':y='ih/2-(ih/zoom/2)':d={frames}:s={w}x{h}:fps={fps}",
    # Zoom in top-left to center
    "zoompan=z='min(zoom+0.0015,1.5)':x='if(lte(on,1),0,min(x+1,iw/2-iw/zoom/2))':y='if(lte(on,1),0,min(y+1,ih/2-ih/zoom/2))':d={frames}:s={w}x{h}:fps={fps}",
    # Zoom out from bottom-right
    "zoompan=z='if(lte(zoom,1.0),1.5,max(1.001,zoom-0.0015))':x='if(lte(on,1),iw/2,max(0,x-1))':y='if(lte(on,1),ih/2,max(0,y-1))':d={frames}:s={w}x{h}:fps={fps}",
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
    language: str = "fr",
) -> str:
    """Render Hormozi-style subtitle overlays: centered, UPPERCASE, word-by-word yellow highlight."""
    cfg = niche_captions or {}
    font_size = cfg.get("font_size", 72)
    words_per_group = cfg.get("words_per_group", 2)
    position_y_pct = cfg.get("position_y", 45)
    rtl = language in ("ar", "he", "fa", "ur")

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
        group_words_list = group["words"]
        render_order = list(reversed(group_words_list)) if rtl else group_words_list
        text_upper = " ".join(w["word"].upper() for w in render_order)

        measure_img = Image.new("RGBA", (1, 1), (0, 0, 0, 0))
        measure_draw = ImageDraw.Draw(measure_img)
        bbox = measure_draw.textbbox((0, 0), text_upper, font=font)
        text_w = bbox[2] - bbox[0]
        text_h = bbox[3] - bbox[1]

        box_w = text_w + pad_x * 2
        box_h = text_h + pad_y * 2
        box_x = (video_width - box_w) // 2
        box_y = int(video_height * position_y_pct / 100) - box_h // 2

        for wi, w in enumerate(group_words_list):
            word_start = int(float(w["start"]) * fps)
            word_end = int(float(w["end"]) * fps)

            img = Image.new("RGBA", (video_width, video_height), (0, 0, 0, 0))
            draw = ImageDraw.Draw(img)

            draw.rounded_rectangle(
                [(box_x, box_y), (box_x + box_w, box_y + box_h)],
                radius=14,
                fill=(0, 0, 0, 180),
            )

            cursor_x = box_x + pad_x
            text_y = box_y + pad_y

            for wj, ww in enumerate(render_order):
                word_text = ww["word"].upper()
                original_idx = len(render_order) - 1 - wj if rtl else wj
                fill = highlight_color if original_idx == wi else white

                draw.text(
                    (cursor_x, text_y), word_text, font=font,
                    fill=fill,
                    stroke_width=stroke_width, stroke_fill=stroke_color,
                )

                w_bbox = measure_draw.textbbox((0, 0), word_text, font=font)
                w_width = w_bbox[2] - w_bbox[0]
                cursor_x += w_width

                if wj < len(render_order) - 1:
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


def _build_watermark_filter(watermark_cfg: dict, width: int, height: int) -> str | None:
    if not watermark_cfg or not watermark_cfg.get("enabled", False):
        return None

    text = watermark_cfg.get("text", "")
    if not text:
        return None

    font_size = watermark_cfg.get("font_size", 24)
    opacity = watermark_cfg.get("opacity", 0.6)
    position = watermark_cfg.get("position", "bottom-right")
    alpha = int(opacity * 255)
    alpha_hex = f"{alpha:02x}"

    pos_map = {
        "top-left": ("x=20", "y=20"),
        "top-right": (f"x=w-tw-20", "y=20"),
        "bottom-left": ("x=20", f"y=h-th-20"),
        "bottom-right": (f"x=w-tw-20", f"y=h-th-20"),
    }
    x_expr, y_expr = pos_map.get(position, pos_map["bottom-right"])

    font_candidates = []
    if platform.system() == "Darwin":
        font_candidates = [
            "/Library/Fonts/Arial.ttf",
            "/System/Library/Fonts/Helvetica.ttc",
        ]
    elif platform.system() == "Linux":
        font_candidates = [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        ]

    fontfile_arg = ""
    for fp in font_candidates:
        if os.path.exists(fp):
            fontfile_arg = f":fontfile='{fp}'"
            break

    return (
        f"drawtext=text='{text}':fontsize={font_size}"
        f"{fontfile_arg}"
        f":fontcolor=white@{opacity}:{x_expr}:{y_expr}"
    )


def _generate_branding_image(
    width: int, height: int, output_path: str,
    lines: list[tuple[str, int]],
    palette: list[str],
) -> str:
    from PIL import Image, ImageDraw

    img = Image.new("RGB", (width, height))
    draw = ImageDraw.Draw(img)

    colors = [_hex_to_rgb(c) for c in (palette or ["#6366f1", "#8b5cf6"])]
    c1, c2 = colors[0], colors[-1]
    for y in range(height):
        ratio = y / height
        r = int(c1[0] + (c2[0] - c1[0]) * ratio)
        g = int(c1[1] + (c2[1] - c1[1]) * ratio)
        b = int(c1[2] + (c2[2] - c1[2]) * ratio)
        draw.line([(0, y), (width, y)], fill=(r, g, b))

    total_h = sum(sz + 20 for _, sz in lines)
    y_cursor = (height - total_h) // 2

    for text, font_size in lines:
        font = _find_font(font_size)
        bbox = draw.textbbox((0, 0), text, font=font)
        tw = bbox[2] - bbox[0]
        x = (width - tw) // 2
        draw.text((x, y_cursor), text, font=font, fill=(255, 255, 255),
                  stroke_width=3, stroke_fill=(0, 0, 0))
        y_cursor += font_size + 20

    img.save(output_path, quality=95)
    return output_path


def _hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    h = hex_color.lstrip("#")
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))


def _build_intro_outro_clips(
    tmpdir: str,
    width: int, height: int, fps: int,
    branding: dict,
    palette: list[str],
    title: str = "",
    cta: str = "",
) -> tuple[str | None, str | None]:
    if not branding:
        return None, None

    channel = branding.get("channel_name", "")
    intro_dur = branding.get("intro_duration", 0)
    outro_dur = branding.get("outro_duration", 0)
    subscribe = branding.get("subscribe_text", "")

    intro_clip = None
    if channel and intro_dur > 0:
        intro_img = os.path.join(tmpdir, "intro.png")
        lines = [(channel, 72)]
        if title:
            short_title = title[:50] + ("..." if len(title) > 50 else "")
            lines.append((short_title, 36))
        _generate_branding_image(width, height, intro_img, lines, palette)

        intro_clip = os.path.join(tmpdir, "intro.mp4")
        cmd = [
            "ffmpeg", "-y", "-loop", "1", "-i", intro_img,
            "-t", str(intro_dur),
            "-vf", f"scale={width}:{height},format=yuv420p",
            "-c:v", "libx264", "-preset", "fast",
            "-pix_fmt", "yuv420p", "-an", intro_clip,
        ]
        subprocess.run(cmd, capture_output=True, check=True)

    outro_clip = None
    if outro_dur > 0 and (cta or subscribe):
        outro_img = os.path.join(tmpdir, "outro.png")
        lines = []
        if cta:
            lines.append((cta[:60], 48))
        if subscribe:
            lines.append((subscribe, 36))
        _generate_branding_image(width, height, outro_img, lines, palette)

        outro_clip = os.path.join(tmpdir, "outro.mp4")
        cmd = [
            "ffmpeg", "-y", "-loop", "1", "-i", outro_img,
            "-t", str(outro_dur),
            "-vf", f"scale={width}:{height},format=yuv420p",
            "-c:v", "libx264", "-preset", "fast",
            "-pix_fmt", "yuv420p", "-an", outro_clip,
        ]
        subprocess.run(cmd, capture_output=True, check=True)

    return intro_clip, outro_clip


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
    scenes: list[dict] | None = None,
    watermark: dict | None = None,
    branding: dict | None = None,
    title: str = "",
    cta: str = "",
    color_palette: list[str] | None = None,
) -> str:
    width = config.get("width", 1080)
    height = config.get("height", 1920)
    fps = config.get("fps", 30)
    crf = config.get("crf", 23)

    music_cfg = niche_music or {}
    normal_vol = music_cfg.get("volume_normal", 0.15)
    ducked_vol = music_cfg.get("volume_ducked", 0.04)
    fade_out = music_cfg.get("fade_out", 1.0)

    duration = _get_audio_duration(audio_path)

    # If scene durations provided (from script), use those instead of uniform split
    scene_durations = []
    if scenes:
        total_hint = sum(s.get("duration_hint", 0) for s in scenes)
        if total_hint > 0:
            for s in scenes:
                ratio = s.get("duration_hint", duration / len(image_paths)) / total_hint
                scene_durations.append(duration * ratio)
        else:
            scene_durations = [duration / len(image_paths)] * len(image_paths)
    else:
        scene_durations = [duration / len(image_paths)] * len(image_paths)

    with tempfile.TemporaryDirectory() as tmpdir:
        prepared = []
        for i, img in enumerate(image_paths):
            out = os.path.join(tmpdir, f"img_{i:03d}.png")
            _prepare_image(img, width, height, out)
            prepared.append(out)

        scene_clips = []
        last_effect_idx = -1
        for i, img in enumerate(prepared):
            sc_dur = scene_durations[i]
            sc_frames = int(sc_dur * fps)
            clip_path = os.path.join(tmpdir, f"clip_{i:03d}.mp4")

            available = [j for j in range(len(ZOOMPAN_EFFECTS)) if j != last_effect_idx]
            effect_idx = random.choice(available)
            last_effect_idx = effect_idx
            effect = ZOOMPAN_EFFECTS[effect_idx].format(
                frames=sc_frames, w=width, h=height, fps=fps
            )

            cmd = [
                "ffmpeg", "-y", "-loop", "1", "-i", img,
                "-vf", effect,
                "-t", f"{sc_dur:.3f}",
                "-c:v", "libx264", "-preset", "fast",
                "-pix_fmt", "yuv420p",
                "-an", clip_path,
            ]
            subprocess.run(cmd, capture_output=True, check=True)
            scene_clips.append(clip_path)

        intro_clip, outro_clip = _build_intro_outro_clips(
            tmpdir, width, height, fps,
            branding or {},
            color_palette or [],
            title=title,
            cta=cta,
        )

        # Build xfade chain for smooth crossfade transitions between scene clips
        crossfade_duration = 0.3
        if len(scene_clips) > 1:
            filters = []
            for i in range(len(scene_clips) - 1):
                src = "[0:v]" if i == 0 else f"[v{i}]"
                offset = sum(scene_durations[:i + 1]) - crossfade_duration * (i + 1)
                if offset < 0:
                    offset = 0
                dst = f"[{i + 1}:v]"
                out = f"[v{i + 1}]" if i < len(scene_clips) - 2 else "[vout]"
                filters.append(
                    f"{src}{dst}xfade=transition=fade:duration={crossfade_duration}:offset={offset:.3f}{out}"
                )

            filter_str = ";".join(filters)
            xfade_video = os.path.join(tmpdir, "xfade_video.mp4")
            cmd = (
                ["ffmpeg", "-y"]
                + [item for clip in scene_clips for item in ["-i", clip]]
                + [
                    "-filter_complex", filter_str,
                    "-map", "[vout]",
                    "-c:v", "libx264", "-preset", "fast", "-pix_fmt", "yuv420p",
                    xfade_video,
                ]
            )
            subprocess.run(cmd, capture_output=True, check=True)
        else:
            xfade_video = scene_clips[0]

        # Concat intro + crossfaded scenes + outro via concat demuxer
        all_parts = []
        if intro_clip:
            all_parts.append(intro_clip)
        all_parts.append(xfade_video)
        if outro_clip:
            all_parts.append(outro_clip)

        raw_video = os.path.join(tmpdir, "raw.mp4")
        if len(all_parts) > 1:
            concat_file = os.path.join(tmpdir, "concat.txt")
            with open(concat_file, "w") as f:
                for part in all_parts:
                    f.write(f"file '{part}'\n")
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
        else:
            raw_video = all_parts[0]

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

            wm_filter = _build_watermark_filter(watermark, width, height)
            if wm_filter:
                filter_expr = f"[0:v][1:v]overlay=0:0:shortest=1,{wm_filter}[outv]"
            else:
                filter_expr = "[0:v][1:v]overlay=0:0:shortest=1[outv]"

            subprocess.run(
                [
                    "ffmpeg", "-y",
                    "-i", video_with_audio,
                    "-i", subs_video,
                    "-filter_complex", filter_expr,
                    "-map", "[outv]",
                    "-map", "0:a",
                    "-c:v", "libx264", "-preset", "medium", "-crf", str(crf),
                    "-c:a", "copy",
                    output_path,
                ],
                capture_output=True,
                check=True,
            )
        else:
            wm_filter = _build_watermark_filter(watermark, width, height)
            if wm_filter:
                subprocess.run(
                    [
                        "ffmpeg", "-y",
                        "-i", video_with_audio,
                        "-vf", wm_filter,
                        "-c:v", "libx264", "-preset", "medium", "-crf", str(crf),
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
