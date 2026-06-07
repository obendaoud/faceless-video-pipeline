"""Character overlay system — composites a recurring character (Wojak) onto scene images."""

import os
import hashlib
import httpx
import replicate
from PIL import Image


EMOTION_MAP = {
    "curiosity": "curious",
    "tension": "worried",
    "shock": "shocked",
    "fear": "doomer",
    "empowerment": "chad",
    "relief": "comfy",
    "neutral": "neutral",
    "happy": "happy",
    "sad": "doomer",
    "angry": "angry",
}

WOJAK_PROMPTS = {
    "neutral": "wojak meme face, simple line art, bald head, neutral blank expression, looking forward, white background, clean minimal style, meme art",
    "curious": "wojak meme face, simple line art, bald head, one eyebrow raised, curious intrigued expression, looking to the side, white background, clean minimal style, meme art",
    "worried": "wojak meme face, simple line art, bald head, nervous sweating worried expression, furrowed brows, white background, clean minimal style, meme art",
    "shocked": "wojak meme face, simple line art, bald head, mouth wide open shocked expression, eyes very wide, white background, clean minimal style, meme art",
    "doomer": "doomer wojak meme face, simple line art, dark circles under eyes, sad depressed expression, black beanie hat, white background, clean minimal style, meme art",
    "chad": "chad yes wojak meme face, simple line art, strong jawline, confident smirk, determined expression, blonde hair, white background, clean minimal style, meme art",
    "comfy": "comfy wojak meme face, simple line art, bald head, gentle peaceful smile, relaxed calm expression, eyes half closed, white background, clean minimal style, meme art",
    "happy": "happy wojak meme face, simple line art, bald head, big genuine smile, bright happy expression, white background, clean minimal style, meme art",
    "angry": "angry wojak meme face, simple line art, bald head, furrowed brows, angry frustrated expression, gritting teeth, white background, clean minimal style, meme art",
}


def _get_wojak_path(emotion: str, assets_dir: str) -> str:
    return os.path.join(assets_dir, f"wojak_{emotion}.png")


def generate_wojak_set(assets_dir: str, emotions: list[str] | None = None) -> dict[str, str]:
    """Generate a set of Wojak faces for all emotions. Skips already generated ones."""
    import time

    os.makedirs(assets_dir, exist_ok=True)
    emotions = emotions or list(WOJAK_PROMPTS.keys())
    paths = {}

    for i, emotion in enumerate(emotions):
        path = _get_wojak_path(emotion, assets_dir)
        if os.path.exists(path):
            paths[emotion] = path
            continue

        prompt = WOJAK_PROMPTS.get(emotion, WOJAK_PROMPTS["neutral"])

        if i > 0:
            time.sleep(12)

        output = replicate.run(
            "black-forest-labs/flux-schnell",
            input={
                "prompt": prompt,
                "width": 512,
                "height": 512,
                "num_outputs": 1,
                "output_format": "png",
            },
        )

        url = str(output[0]) if isinstance(output, list) else str(output)
        resp = httpx.get(url, follow_redirects=True, timeout=60)
        resp.raise_for_status()

        with open(path, "wb") as f:
            f.write(resp.content)

        paths[emotion] = path

    return paths


def _remove_background(image: Image.Image, threshold: int = 230) -> Image.Image:
    """Remove white/near-white background from a Wojak image."""
    img = image.convert("RGBA")
    data = img.getdata()

    new_data = []
    for r, g, b, a in data:
        if r > threshold and g > threshold and b > threshold:
            new_data.append((r, g, b, 0))
        else:
            new_data.append((r, g, b, a))

    img.putdata(new_data)
    return img


def overlay_character(
    background_path: str,
    emotion: str,
    output_path: str,
    assets_dir: str = "assets/characters/wojak",
    position: str = "bottom-right",
    scale: float = 0.35,
) -> str:
    """Overlay a Wojak character on a background image."""
    mapped = EMOTION_MAP.get(emotion, "neutral")
    wojak_path = _get_wojak_path(mapped, assets_dir)

    if not os.path.exists(wojak_path):
        wojak_path = _get_wojak_path("neutral", assets_dir)

    if not os.path.exists(wojak_path):
        import shutil
        shutil.copy2(background_path, output_path)
        return output_path

    bg = Image.open(background_path).convert("RGBA")
    wojak = Image.open(wojak_path).convert("RGBA")

    wojak = _remove_background(wojak)

    char_h = int(bg.height * scale)
    char_w = int(wojak.width * (char_h / wojak.height))
    wojak = wojak.resize((char_w, char_h), Image.LANCZOS)

    margin = int(bg.width * 0.04)

    if position == "bottom-right":
        x = bg.width - char_w - margin
        y = bg.height - char_h - margin
    elif position == "bottom-left":
        x = margin
        y = bg.height - char_h - margin
    elif position == "bottom-center":
        x = (bg.width - char_w) // 2
        y = bg.height - char_h - margin
    elif position == "center-right":
        x = bg.width - char_w - margin
        y = (bg.height - char_h) // 2
    else:
        x = bg.width - char_w - margin
        y = bg.height - char_h - margin

    # Add white outline/glow so Wojak pops on dark backgrounds
    from PIL import ImageFilter
    outline = Image.new("RGBA", (char_w + 12, char_h + 12), (0, 0, 0, 0))
    outline.paste(wojak, (6, 6), wojak)
    alpha = outline.split()[3]
    dilated = alpha.filter(ImageFilter.MaxFilter(7))
    glow = Image.new("RGBA", outline.size, (255, 255, 255, 0))
    glow.putalpha(dilated)
    glow.paste(wojak, (6, 6), wojak)

    bg.paste(glow, (x - 6, y - 6), glow)

    bg.convert("RGB").save(output_path, quality=95)
    return output_path


def overlay_all_scenes(
    image_paths: list[str],
    emotions: list[str],
    output_dir: str,
    assets_dir: str = "assets/characters/wojak",
    position: str = "bottom-right",
    scale: float = 0.35,
) -> list[str]:
    """Overlay Wojak on all scene images, matching emotion to expression."""
    os.makedirs(output_dir, exist_ok=True)
    results = []

    for img_path, emotion in zip(image_paths, emotions):
        basename = os.path.basename(img_path)
        out_path = os.path.join(output_dir, basename)

        overlay_character(img_path, emotion, out_path, assets_dir, position, scale)
        results.append(out_path)

    return results
