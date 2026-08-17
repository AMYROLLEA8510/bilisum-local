from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import platform
import shutil
import stat
from pathlib import Path

HOST_NAME = "com.bilisum.local"


def extension_id(manifest_path: Path) -> str:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    key = str(manifest.get("key") or "")
    if not key:
        raise RuntimeError("extension/manifest.json has no development key")
    digest = hashlib.sha256(base64.b64decode(key)).digest()[:16].hex()
    return digest.translate(str.maketrans("0123456789abcdef", "abcdefghijklmnop"))


def allowed_origins(root: Path) -> list[str]:
    ids = [extension_id(root / "extension" / "manifest.json")]
    cfg_path = root / "release_channel.json"
    if cfg_path.exists():
        try:
            cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
            store_id = str(cfg.get("store_extension_id") or "").strip()
            if store_id and store_id not in ids:
                ids.append(store_id)
        except Exception:
            pass
    return [f"chrome-extension://{value}/" for value in ids]


def native_manifest(root: Path, host_executable: Path) -> dict:
    return {
        "name": HOST_NAME,
        "description": "BiliSum local processing host",
        "path": str(host_executable.resolve()),
        "type": "stdio",
        "allowed_origins": allowed_origins(root),
    }


def write_manifest(root: Path, host_executable: Path) -> Path:
    runtime = root / ".runtime" / "native"
    runtime.mkdir(parents=True, exist_ok=True)
    path = runtime / f"{HOST_NAME}.json"
    path.write_text(json.dumps(native_manifest(root, host_executable), ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def register_windows(manifest_path: Path, uninstall: bool = False) -> None:
    import winreg
    keys = [
        rf"Software\Google\Chrome\NativeMessagingHosts\{HOST_NAME}",
        rf"Software\Microsoft\Edge\NativeMessagingHosts\{HOST_NAME}",
        rf"Software\Chromium\NativeMessagingHosts\{HOST_NAME}",
    ]
    for key_path in keys:
        if uninstall:
            try:
                winreg.DeleteKey(winreg.HKEY_CURRENT_USER, key_path)
            except FileNotFoundError:
                pass
            continue
        key = winreg.CreateKey(winreg.HKEY_CURRENT_USER, key_path)
        winreg.SetValueEx(key, None, 0, winreg.REG_SZ, str(manifest_path.resolve()))
        winreg.CloseKey(key)


def unix_targets() -> list[Path]:
    home = Path.home()
    system = platform.system().lower()
    if system == "darwin":
        bases = [
            home / "Library/Application Support/Google/Chrome/NativeMessagingHosts",
            home / "Library/Application Support/Microsoft Edge/NativeMessagingHosts",
            home / "Library/Application Support/Chromium/NativeMessagingHosts",
            home / "Library/Application Support/BraveSoftware/Brave-Browser/NativeMessagingHosts",
        ]
    else:
        bases = [
            home / ".config/google-chrome/NativeMessagingHosts",
            home / ".config/microsoft-edge/NativeMessagingHosts",
            home / ".config/chromium/NativeMessagingHosts",
            home / ".config/BraveSoftware/Brave-Browser/NativeMessagingHosts",
        ]
    return [base / f"{HOST_NAME}.json" for base in bases]


def register_unix(manifest_path: Path, uninstall: bool = False) -> None:
    for target in unix_targets():
        if uninstall:
            target.unlink(missing_ok=True)
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(manifest_path, target)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=True)
    parser.add_argument("--host-executable", required=True)
    parser.add_argument("--uninstall", action="store_true")
    args = parser.parse_args()
    root = Path(args.root).resolve()
    host_executable = Path(args.host_executable).resolve()
    if not args.uninstall and not host_executable.exists():
        raise SystemExit(f"Native host executable not found: {host_executable}")
    manifest_path = write_manifest(root, host_executable)
    if os.name == "nt":
        register_windows(manifest_path, args.uninstall)
    else:
        register_unix(manifest_path, args.uninstall)
    print(json.dumps({"ok": True, "host": HOST_NAME, "extension_ids": [o.split('//',1)[1].rstrip('/') for o in allowed_origins(root)], "manifest": str(manifest_path)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
