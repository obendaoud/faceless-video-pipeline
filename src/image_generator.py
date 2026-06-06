import os
import httpx
import replicate


def generate_image(prompt: str, config: dict, output_path: str) -> str:
    style_suffix = config.get("style", "")
    full_prompt = f"{prompt}, {style_suffix}" if style_suffix else prompt

    output = replicate.run(
        config.get("model", "black-forest-labs/flux-schnell"),
        input={
            "prompt": full_prompt,
            "width": config.get("width", 768),
            "height": config.get("height", 1344),
            "num_outputs": 1,
            "output_format": "png",
        },
    )

    image_url = output[0] if isinstance(output, list) else output
    url_str = str(image_url)

    response = httpx.get(url_str, follow_redirects=True, timeout=60)
    response.raise_for_status()

    with open(output_path, "wb") as f:
        f.write(response.content)

    return output_path


def generate_all_images(
    scenes: list[dict], config: dict, output_dir: str
) -> list[str]:
    import time

    os.makedirs(output_dir, exist_ok=True)
    paths = []

    for i, scene in enumerate(scenes):
        scene_num = scene["scene_number"]
        path = os.path.join(output_dir, f"scene_{scene_num:02d}.png")

        if os.path.exists(path):
            paths.append(path)
            continue

        if i > 0:
            rate_limit = config.get("rate_limit_seconds", 12)
            time.sleep(rate_limit)

        generate_image(scene["image_prompt"], config, path)
        paths.append(path)

    return paths
