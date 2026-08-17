from __future__ import annotations

import hashlib
import json
import shutil
import tempfile
import time
import urllib.request
import zipfile
from pathlib import Path
from typing import Any

GITHUB_API = "https://api.github.com"
USER_AGENT = "BiliSum-Updater/5.2"


def _version_tuple(value: str) -> tuple[int, ...]:
    raw = str(value or "").strip().lstrip("vV")
    parts: list[int] = []
    for token in raw.split("."):
        digits = "".join(ch for ch in token if ch.isdigit())
        parts.append(int(digits or 0))
    return tuple((parts + [0, 0, 0])[:3])


def _request_json(url: str, timeout: float = 15.0) -> dict[str, Any]:
    req = urllib.request.Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": USER_AGENT,
            "X-GitHub-Api-Version": "2026-03-10",
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def load_release_config(root: Path) -> dict[str, Any]:
    path = root / "release_channel.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise RuntimeError("Invalid release_channel.json")
    return data


def check_update(root: Path, current_version: str) -> dict[str, Any]:
    cfg = load_release_config(root)
    if not cfg.get("updates_enabled", True):
        return {"ok": True, "available": False, "disabled": True, "current_version": current_version}
    repo = str(cfg.get("repository") or "").strip()
    if not repo or "/" not in repo:
        return {"ok": True, "available": False, "unconfigured": True, "current_version": current_version}
    release = _request_json(f"{GITHUB_API}/repos/{repo}/releases/latest")
    latest = str(release.get("tag_name") or "").lstrip("vV")
    available = _version_tuple(latest) > _version_tuple(current_version)
    asset_prefix = str(cfg.get("asset_prefix") or "BiliSum-Portable-")
    asset = None
    for item in release.get("assets") or []:
        name = str(item.get("name") or "")
        if name.startswith(asset_prefix) and name.endswith(".zip"):
            asset = item
            break
    return {
        "ok": True,
        "available": bool(available and asset),
        "current_version": current_version,
        "latest_version": latest,
        "release_name": release.get("name") or release.get("tag_name") or latest,
        "release_notes": release.get("body") or "",
        "published_at": release.get("published_at") or "",
        "asset": {
            "name": asset.get("name"),
            "url": asset.get("browser_download_url"),
            "size": asset.get("size"),
            "digest": asset.get("digest"),
        } if asset else None,
    }


def _safe_extract(zip_path: Path, destination: Path) -> Path:
    destination.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path) as zf:
        for member in zf.infolist():
            target = (destination / member.filename).resolve()
            if destination.resolve() not in target.parents and target != destination.resolve():
                raise RuntimeError("Unsafe path in update archive")
        zf.extractall(destination)
    children = [p for p in destination.iterdir() if p.name != "__MACOSX"]
    if len(children) == 1 and children[0].is_dir():
        return children[0]
    return destination


def stage_update(root: Path, current_version: str) -> dict[str, Any]:
    if (root / ".git").exists():
        raise RuntimeError("This is a Git checkout. Use git pull for source checkouts instead of the built-in updater.")
    info = check_update(root, current_version)
    if not info.get("available"):
        return {**info, "staged": False}
    asset = info.get("asset") or {}
    url = str(asset.get("url") or "")
    digest = str(asset.get("digest") or "")
    if not url.startswith("https://github.com/"):
        raise RuntimeError("Unexpected update asset URL")
    runtime = root / ".runtime" / "updates"
    runtime.mkdir(parents=True, exist_ok=True)
    version = str(info.get("latest_version") or "unknown")
    archive = runtime / f"BiliSum-{version}.zip"
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    hasher = hashlib.sha256()
    with urllib.request.urlopen(req, timeout=60) as response, open(archive, "wb") as out:
        while True:
            chunk = response.read(1024 * 1024)
            if not chunk:
                break
            hasher.update(chunk)
            out.write(chunk)
    actual = hasher.hexdigest()
    expected = digest.split(":", 1)[1].lower() if digest.startswith("sha256:") else ""
    if not expected:
        archive.unlink(missing_ok=True)
        raise RuntimeError("Release asset has no SHA-256 digest; refusing an unverifiable update")
    if actual.lower() != expected:
        archive.unlink(missing_ok=True)
        raise RuntimeError("Downloaded update failed SHA-256 verification")
    staging_dir = runtime / f"staging-{version}-{int(time.time())}"
    package_root = _safe_extract(archive, staging_dir)
    version_file = package_root / "VERSION"
    if not version_file.exists() or version_file.read_text(encoding="utf-8").strip() != version:
        shutil.rmtree(staging_dir, ignore_errors=True)
        raise RuntimeError("Update archive version does not match release metadata")
    return {**info, "staged": True, "staging_path": str(package_root), "sha256": actual}


def launch_apply(root: Path, staging_path: str) -> dict[str, Any]:
    staging = Path(staging_path).resolve()
    if not staging.exists():
        raise RuntimeError("Staged update is missing")
    from .updater import apply_in_place
    return {**apply_in_place(root.resolve(), staging), "applying": False}
