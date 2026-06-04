"""YouTube upload via Data API v3 — OAuth2 + resumable upload."""

import os
import json
import time
import httpx

YOUTUBE_UPLOAD_URL = "https://www.googleapis.com/upload/youtube/v3/videos"
YOUTUBE_CAPTIONS_URL = "https://www.googleapis.com/youtube/v3/captions"
TOKEN_FILE = os.path.expanduser("~/.config/automate-video/youtube_tokens.json")
SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]


def _load_tokens() -> dict | None:
    if not os.path.exists(TOKEN_FILE):
        return None
    with open(TOKEN_FILE, encoding="utf-8") as f:
        return json.load(f)


def _save_tokens(tokens: dict) -> None:
    os.makedirs(os.path.dirname(TOKEN_FILE), exist_ok=True)
    fd = os.open(TOKEN_FILE, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        json.dump(tokens, f, indent=2)


def _refresh_token(tokens: dict) -> dict:
    client_id = os.environ.get("YOUTUBE_CLIENT_ID", "")
    client_secret = os.environ.get("YOUTUBE_CLIENT_SECRET", "")

    resp = httpx.post(
        "https://oauth2.googleapis.com/token",
        data={
            "client_id": client_id,
            "client_secret": client_secret,
            "refresh_token": tokens["refresh_token"],
            "grant_type": "refresh_token",
        },
    )
    resp.raise_for_status()
    new_tokens = resp.json()
    tokens["access_token"] = new_tokens["access_token"]
    _save_tokens(tokens)
    return tokens


def setup_oauth(client_id: str, client_secret: str) -> dict:
    """Interactive OAuth2 setup — run once to authorize."""
    auth_url = (
        f"https://accounts.google.com/o/oauth2/auth"
        f"?client_id={client_id}"
        f"&redirect_uri=urn:ietf:wg:oauth:2.0:oob"
        f"&scope={' '.join(SCOPES)}"
        f"&response_type=code"
        f"&access_type=offline"
    )
    print(f"\nOuvre cette URL dans ton navigateur:\n{auth_url}\n")
    code = input("Colle le code d'autorisation ici: ").strip()

    resp = httpx.post(
        "https://oauth2.googleapis.com/token",
        data={
            "client_id": client_id,
            "client_secret": client_secret,
            "code": code,
            "grant_type": "authorization_code",
            "redirect_uri": "urn:ietf:wg:oauth:2.0:oob",
        },
    )
    resp.raise_for_status()
    tokens = resp.json()
    _save_tokens(tokens)
    print("Tokens sauvegardés.")
    return tokens


def upload_video(
    video_path: str,
    title: str,
    description: str,
    tags: list[str] | None = None,
    srt_path: str | None = None,
    category_id: str = "28",  # Science & Technology
) -> str | None:
    tokens = _load_tokens()
    if not tokens:
        print("YouTube non configuré. Lance: python -m src.uploader --setup")
        return None

    tokens = _refresh_token(tokens)
    access_token = tokens["access_token"]

    metadata = {
        "snippet": {
            "title": title[:100],
            "description": description[:5000],
            "tags": tags or [],
            "categoryId": category_id,
        },
        "status": {
            "privacyStatus": "private",
            "selfDeclaredMadeForKids": False,
        },
    }

    file_size = os.path.getsize(video_path)

    init_resp = httpx.post(
        f"{YOUTUBE_UPLOAD_URL}?uploadType=resumable&part=snippet,status",
        headers={
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json; charset=UTF-8",
            "X-Upload-Content-Length": str(file_size),
            "X-Upload-Content-Type": "video/mp4",
        },
        json=metadata,
    )
    init_resp.raise_for_status()
    upload_url = init_resp.headers["Location"]

    with open(video_path, "rb") as f:
        video_data = f.read()

    for attempt in range(5):
        try:
            resp = httpx.put(
                upload_url,
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Content-Type": "video/mp4",
                    "Content-Length": str(file_size),
                },
                content=video_data,
                timeout=300,
            )
            resp.raise_for_status()
            video_id = resp.json()["id"]

            if srt_path and os.path.exists(srt_path):
                _upload_captions(access_token, video_id, srt_path)

            return f"https://youtube.com/shorts/{video_id}"

        except (httpx.HTTPStatusError, httpx.TimeoutException):
            if attempt < 4:
                wait = 2 ** (attempt + 1)
                time.sleep(wait)
                continue
            raise

    return None


def _upload_captions(access_token: str, video_id: str, srt_path: str) -> None:
    with open(srt_path, "rb") as f:
        srt_data = f.read()

    httpx.post(
        f"{YOUTUBE_CAPTIONS_URL}?uploadType=multipart&part=snippet",
        headers={"Authorization": f"Bearer {access_token}"},
        files={
            "": (
                None,
                json.dumps(
                    {
                        "snippet": {
                            "videoId": video_id,
                            "language": "fr",
                            "name": "Français",
                        }
                    }
                ),
                "application/json",
            ),
            "media": ("captions.srt", srt_data, "application/octet-stream"),
        },
    )


if __name__ == "__main__":
    import sys

    if "--setup" in sys.argv:
        cid = input("YouTube Client ID: ").strip()
        csecret = input("YouTube Client Secret: ").strip()
        setup_oauth(cid, csecret)
