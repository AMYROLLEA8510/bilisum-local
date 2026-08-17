from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

PRESERVE = {".runtime", ".git"}


def read_schema(root: Path) -> str:
    try:
        return (root / "RUNTIME_SCHEMA").read_text(encoding="utf-8").strip() or "0"
    except Exception:
        return "0"


def overlay(source: Path, root: Path) -> None:
    for item in source.iterdir():
        if item.name in PRESERVE:
            continue
        target = root / item.name
        if item.is_dir():
            if target.exists() and not target.is_dir():
                target.unlink()
            target.mkdir(parents=True, exist_ok=True)
            for child in item.iterdir():
                child_target = target / child.name
                if child.is_dir():
                    if child_target.exists():
                        shutil.rmtree(child_target)
                    shutil.copytree(child, child_target)
                else:
                    shutil.copy2(child, child_target)
        else:
            shutil.copy2(item, target)


def prepare_runtime(staging: Path, root: Path) -> bool:
    """Reconcile Python dependencies before replacing application files."""
    changed = read_schema(root) != read_schema(staging)
    if not changed:
        return False
    req = staging / "host" / "requirements_asr.txt"
    if req.exists():
        subprocess.run(
            [sys.executable, "-m", "pip", "install", "--disable-pip-version-check", "-r", str(req)],
            check=True,
            cwd=str(root),
        )
    return True


def refresh_editable_host(root: Path) -> None:
    host = root / "host"
    if host.exists():
        subprocess.run(
            [sys.executable, "-m", "pip", "install", "--disable-pip-version-check", "--no-deps", "--editable", str(host)],
            check=True,
            cwd=str(root),
            stdout=subprocess.DEVNULL,
        )


def apply_in_place(root: Path, staging: Path) -> dict:
    runtime = root / ".runtime"
    runtime.mkdir(parents=True, exist_ok=True)
    marker = runtime / "last_update.json"
    try:
        runtime_changed = prepare_runtime(staging, root)
        overlay(staging, root)
        refresh_editable_host(root)
        (runtime / "runtime_schema.txt").write_text(read_schema(root) + "\n", encoding="utf-8")
        version = (root / "VERSION").read_text(encoding="utf-8").strip()
        result = {"ok": True, "updated_at": time.strftime("%Y-%m-%dT%H:%M:%S"), "version": version, "runtime_changed": runtime_changed}
        marker.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        return result
    except Exception as exc:
        marker.write_text(json.dumps({"ok": False, "updated_at": time.strftime("%Y-%m-%dT%H:%M:%S"), "error": str(exc)}, ensure_ascii=False, indent=2), encoding="utf-8")
        raise


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=True)
    parser.add_argument("--staging", required=True)
    args = parser.parse_args()
    result = apply_in_place(Path(args.root).resolve(), Path(args.staging).resolve())
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
