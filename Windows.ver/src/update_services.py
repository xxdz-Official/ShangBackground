from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any
from urllib import request

import core_engine as core

GITHUB_REPO = "purrfecto114-lgtm/ShangBackground"
GITHUB_PROJECT_URL = f"https://github.com/{GITHUB_REPO}"
GITHUB_LATEST_RELEASE_URL = f"{GITHUB_PROJECT_URL}/releases/latest"
GITHUB_LATEST_API_URL = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
MAX_RELEASE_JSON_BYTES = 2 * 1024 * 1024
# Accept normal Release tags and text snippets such as:
#   1.3, 1.3.0, v1.3.0, app_ver=1.3, ShangBackground-1.3.0,
#   1.3.0-beta.1, 1.3.0+build.5
# Compatibility note: old releases used two-segment versions (1.x);
# they are normalized as 1.x.0 for update ordering.
# The version tuple intentionally ignores prerelease/build metadata for update ordering.
VERSION_RE = re.compile(
    r"(?<!\d)[vV]?\s*(?:app[_\s-]*ver(?:sion)?\s*[:=]\s*)?"
    r"(\d+)\.(\d+)(?:\.(\d+))?"
    r"(?:[-+][0-9A-Za-z][0-9A-Za-z._-]*)?(?![\d.])"
)


@dataclass(slots=True)
class ReleaseInfo:
    version: str = "0.0.0"
    tag: str = ""
    name: str = ""
    url: str = GITHUB_LATEST_RELEASE_URL
    project_url: str = GITHUB_PROJECT_URL
    published_at: str = ""
    body: str = ""
    assets: list[dict[str, Any]] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "tag": self.tag,
            "name": self.name,
            "url": self.url,
            "project_url": self.project_url,
            "published_at": self.published_at,
            "body": self.body,
            "assets": self.assets,
        }


def parse_version(value: str | None) -> tuple[int, int, int]:
    """Parse a project version from tags, release names, or app_ver snippets."""
    text = str(value or "").strip()
    match = VERSION_RE.search(text)
    if not match:
        raise ValueError(f"无法解析版本号，需要两段或三段式版本，如 1.3 / 1.3.0 / v1.3.0 / app_ver=1.3：{text or '<empty>'}")
    major, minor, patch = match.groups()
    return int(major), int(minor), int(patch or 0)


def normalize_tag(tag: str | None) -> str:
    major, minor, patch = parse_version(tag)
    return f"{major}.{minor}.{patch}"


def _pick_version_source(data: dict[str, Any]) -> str:
    candidates = [data.get("tag_name"), data.get("name"), data.get("body")]
    for item in candidates:
        if item and VERSION_RE.search(str(item)):
            return str(item)
    for asset in data.get("assets", []) or []:
        for key in ("name", "browser_download_url"):
            item = asset.get(key)
            if item and VERSION_RE.search(str(item)):
                return str(item)
    return str(data.get("tag_name") or "")


def fetch_latest_github_release(timeout: int = 12) -> ReleaseInfo:
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "ShangBackground-Updater",
    }
    req = request.Request(GITHUB_LATEST_API_URL, headers=headers)
    with request.urlopen(req, timeout=timeout) as resp:
        payload = resp.read(MAX_RELEASE_JSON_BYTES + 1)
    if len(payload) > MAX_RELEASE_JSON_BYTES:
        raise ValueError("GitHub Release 响应过大")
    data = json.loads(payload.decode("utf-8"))
    if not isinstance(data, dict):
        raise ValueError("GitHub Release 响应格式无效")

    tag = data.get("tag_name") or ""
    latest_version = normalize_tag(_pick_version_source(data))
    assets: list[dict[str, Any]] = []
    for asset in data.get("assets", []) or []:
        assets.append({
            "name": asset.get("name", "") or "",
            "size": int(asset.get("size") or 0),
            "download_url": asset.get("browser_download_url", "") or "",
        })

    return ReleaseInfo(
        version=latest_version,
        tag=tag,
        name=data.get("name") or "",
        url=data.get("html_url") or GITHUB_LATEST_RELEASE_URL,
        project_url=GITHUB_PROJECT_URL,
        published_at=data.get("published_at") or "",
        body=data.get("body") or "",
        assets=assets,
    )


def check_latest_release(current_version: str, timeout: int = 12) -> tuple[bool, ReleaseInfo]:
    info = fetch_latest_github_release(timeout=timeout)
    return parse_version(info.version) > parse_version(current_version), info


def check_updates_headless(timeout: int = 12) -> tuple[bool, str, dict[str, Any]]:
    try:
        has_update, info = check_latest_release(getattr(core, "VERSION", "1.3.0"), timeout=timeout)
        info_dict = info.as_dict()
        info_dict["has_update"] = has_update
        return True, ("发现新版本" if has_update else "当前已是最新版本"), info_dict
    except Exception as exc:
        return False, f"检查更新失败：{exc}", {}


try:
    from PySide6.QtCore import QThread, Signal

    class UpdateChecker(QThread):
        """Qt worker. The first signal argument means request success, not update availability."""
        finished = Signal(bool, str, dict)

        def run(self) -> None:
            ok, message, info = check_updates_headless()
            self.finished.emit(ok, message, info)
except Exception:
    class UpdateChecker:
        """Headless fallback for tests before GUI dependencies are installed."""
        def __init__(self):
            self.finished = lambda ok, message, info: None

        def start(self) -> None:
            ok, message, info = check_updates_headless()
            self.finished(ok, message, info)
