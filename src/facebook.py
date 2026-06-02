"""Publish a video as a Facebook Reel via the Graph API (resumable upload).

Reels publishing is a 3-step flow:
  1. start   -> POST /{page_id}/video_reels  (upload_phase=start) -> video_id + upload_url
  2. upload  -> POST the binary to upload_url with Authorization: OAuth <token>
  3. finish  -> POST /{page_id}/video_reels  (upload_phase=finish, video_state=PUBLISHED)

Required credentials (env vars, see .env.example):
  FB_PAGE_ID            numeric Page ID
  FB_PAGE_ACCESS_TOKEN  long-lived Page access token with
                        pages_manage_posts + pages_read_engagement

Docs: https://developers.facebook.com/docs/video-api/guides/reels-publishing
"""
from __future__ import annotations

import os
import time

import requests

GRAPH_VERSION = os.environ.get("FB_GRAPH_VERSION", "v21.0")
GRAPH = f"https://graph.facebook.com/{GRAPH_VERSION}"
RUPLOAD = f"https://rupload.facebook.com/video-upload/{GRAPH_VERSION}"


class FacebookError(RuntimeError):
    pass


def _check(resp: requests.Response) -> dict:
    try:
        data = resp.json()
    except ValueError:
        raise FacebookError(f"Non-JSON response ({resp.status_code}): {resp.text[:300]}")
    if resp.status_code >= 400 or "error" in data:
        err = data.get("error", data)
        raise FacebookError(f"Graph API error ({resp.status_code}): {err}")
    return data


def _start(page_id: str, token: str) -> dict:
    resp = requests.post(
        f"{GRAPH}/{page_id}/video_reels",
        data={"upload_phase": "start", "access_token": token},
        timeout=30,
    )
    return _check(resp)


def _upload(upload_url_or_video_id: str, video_path: str, token: str) -> None:
    size = os.path.getsize(video_path)
    # The start phase returns an `upload_url`; if absent, build the rupload URL.
    url = upload_url_or_video_id
    if not url.startswith("http"):
        url = f"{RUPLOAD}/{upload_url_or_video_id}"
    headers = {
        "Authorization": f"OAuth {token}",
        "offset": "0",
        "file_size": str(size),
        "Content-Type": "application/octet-stream",
    }
    with open(video_path, "rb") as fh:
        resp = requests.post(url, headers=headers, data=fh, timeout=300)
    _check(resp)


def _finish(page_id: str, token: str, video_id: str, description: str) -> dict:
    resp = requests.post(
        f"{GRAPH}/{page_id}/video_reels",
        data={
            "upload_phase": "finish",
            "video_id": video_id,
            "video_state": "PUBLISHED",
            "description": description,
            "access_token": token,
        },
        timeout=30,
    )
    return _check(resp)


def comment(object_id: str, message: str, token: str | None = None) -> dict:
    """Post a comment on a published object (post or video). Returns {'id': ...}."""
    token = token or os.environ.get("FB_PAGE_ACCESS_TOKEN")
    if not token:
        raise FacebookError("Missing FB_PAGE_ACCESS_TOKEN")
    resp = requests.post(
        f"{GRAPH}/{object_id}/comments",
        data={"message": message, "access_token": token},
        timeout=30,
    )
    return _check(resp)


def _wait_until_ready(video_id: str, token: str, timeout: float = 120.0) -> None:
    """Poll the Reel's processing status until it's published or ready."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        resp = requests.get(
            f"{GRAPH}/{video_id}",
            params={"fields": "status", "access_token": token},
            timeout=30,
        )
        data = _check(resp)
        status = (data.get("status") or {})
        video_status = status.get("video_status") or status.get("processing_phase", {}).get("status")
        if video_status in ("ready", "published"):
            return
        if video_status == "error":
            raise FacebookError(f"Reel processing failed: {status}")
        time.sleep(5)
    # Not fatal: Facebook often finishes processing after we stop polling.


def post_reel(
    video_path: str,
    description: str = "",
    page_id: str | None = None,
    token: str | None = None,
    wait: bool = True,
) -> dict:
    """Upload and publish `video_path` as a Reel. Returns the finish response."""
    page_id = page_id or os.environ.get("FB_PAGE_ID")
    token = token or os.environ.get("FB_PAGE_ACCESS_TOKEN")
    if not page_id or not token:
        raise FacebookError(
            "Missing FB_PAGE_ID / FB_PAGE_ACCESS_TOKEN (set them in .env or the environment)."
        )
    if not os.path.exists(video_path):
        raise FileNotFoundError(video_path)

    started = _start(page_id, token)
    video_id = started["video_id"]
    upload_target = started.get("upload_url", video_id)

    _upload(upload_target, video_path, token)
    result = _finish(page_id, token, video_id, description)

    if wait:
        try:
            _wait_until_ready(video_id, token)
        except FacebookError:
            raise
        except Exception:
            pass

    result["video_id"] = video_id
    return result


if __name__ == "__main__":
    import sys

    from dotenv import load_dotenv

    load_dotenv()
    path = sys.argv[1] if len(sys.argv) > 1 else "output/demo_real.mp4"
    desc = sys.argv[2] if len(sys.argv) > 2 else "Test reel"
    print(post_reel(path, desc))
