"""Video assembly using pure FFmpeg — Ken Burns, ASS subtitles, music ducking."""

import os
import subprocess
import shutil
import tempfile
from PIL import Image


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


def assemble_video(
    image_paths: list[str],
    audio_path: str,
    ass_path: str,
    output_path: str,
    config: dict,
    music_path: str | None = None,
    speech_regions: list[tuple[float, float]] | None = None,
    niche_music: dict | None = None,
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

        os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)

        ass_abs = os.path.abspath(ass_path)
        escaped_ass = ass_abs.replace("\\", "/").replace(":", "\\:")

        subprocess.run(
            [
                "ffmpeg", "-y",
                "-i", video_with_audio,
                "-vf", f"ass='{escaped_ass}'",
                "-c:v", "libx264", "-preset", "medium",
                "-crf", "18",
                "-c:a", "copy",
                output_path,
            ],
            capture_output=True,
            check=True,
        )

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
