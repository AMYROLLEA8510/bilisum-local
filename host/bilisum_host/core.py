#!/usr/bin/env python3
"""Local processing core for BiliSum.

This module owns transcription, note-generation jobs, caching, and file output.
Transport is provided by the native messaging host; this module does not open a
network listener.
"""
from __future__ import annotations

import hashlib
import importlib.util
import ipaddress
import json
import os
import platform
import queue
import shutil
import socket
import subprocess
import tempfile
import threading
import time
import traceback
import urllib.parse
import urllib.request
import uuid
from pathlib import Path
from typing import Any

VERSION = "5.2.0"
MAX_REQUEST_BYTES = 512 * 1024
MAX_MEDIA_BYTES = 800 * 1024 * 1024
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36"
)

DATA_DIR = Path(__file__).resolve().parent / ".runtime"
CACHE_DIR = DATA_DIR / "asr_cache"
NOTE_CACHE_DIR = DATA_DIR / "note_cache"
MODEL_DIR = DATA_DIR / "whisper_models"
TEMP_DIR = DATA_DIR / "tmp"
OLLAMA_BASE = "http://127.0.0.1:11434"
CONFIG_FILE = DATA_DIR / "config.json"
CONFIG_LOCK = threading.Lock()

JOBS: dict[str, dict[str, Any]] = {}
JOBS_LOCK = threading.Lock()
NOTE_QUEUE: queue.Queue[str] = queue.Queue()
ASR_QUEUE: queue.Queue[str] = queue.Queue()
WORKERS: dict[str, threading.Thread] = {}
MODEL_LOCK = threading.Lock()
MODEL = None
MODEL_KEY: tuple[str, str, str] | None = None
MODEL_META: dict[str, Any] = {"loaded": False}


def now() -> float:
    return time.time()



def update_job(job_id: str, **changes: Any) -> None:
    with JOBS_LOCK:
        if job_id not in JOBS:
            return
        JOBS[job_id].update(changes)
        JOBS[job_id]["updated_at"] = now()


def get_job(job_id: str) -> dict[str, Any] | None:
    with JOBS_LOCK:
        job = JOBS.get(job_id)
        return dict(job) if job else None


def clean_old_jobs() -> None:
    cutoff = now() - 24 * 3600
    with JOBS_LOCK:
        old = [k for k, v in JOBS.items() if v.get("updated_at", 0) < cutoff]
        for k in old:
            JOBS.pop(k, None)




def load_config() -> dict[str, Any]:
    with CONFIG_LOCK:
        try:
            if CONFIG_FILE.exists():
                data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    return data
        except Exception:
            pass
        return {}


def write_config(data: dict[str, Any]) -> None:
    with CONFIG_LOCK:
        CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
        tmp = CONFIG_FILE.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(CONFIG_FILE)


def validate_save_directory(path_value: str) -> Path:
    if not path_value or not str(path_value).strip():
        raise RuntimeError("No save directory is configured")
    path = Path(str(path_value)).expanduser().resolve()
    if not path.exists() or not path.is_dir():
        raise RuntimeError("The selected save directory no longer exists")
    if not os.access(path, os.W_OK):
        raise RuntimeError("The selected save directory is not writable")
    return path


def configured_save_directory() -> Path | None:
    value = str(load_config().get("save_dir") or "").strip()
    if not value:
        return None
    try:
        return validate_save_directory(value)
    except Exception:
        return None


def safe_filename(value: str, default: str = "BiliSum_notes.txt") -> str:
    raw = str(value or default).strip().replace("\\", "_").replace("/", "_")
    bad = '<>:"/\\|?*' if os.name == "nt" else "/\x00"
    table = str.maketrans({ch: "_" for ch in bad})
    raw = raw.translate(table)
    raw = " ".join(raw.split()).strip(" .")
    if not raw:
        raw = default
    if len(raw) > 180:
        stem, suffix = os.path.splitext(raw)
        raw = stem[: max(1, 180 - len(suffix))].rstrip() + suffix
    return raw


def pick_directory_native() -> str:
    system = platform.system().lower()
    try:
        if system == "windows":
            script = (
                "Add-Type -AssemblyName System.Windows.Forms;"
                "$d=New-Object System.Windows.Forms.FolderBrowserDialog;"
                "$d.Description='Choose a folder for BiliSum notes';"
                "$d.ShowNewFolderButton=$true;"
                "if($d.ShowDialog() -eq [System.Windows.Forms.DialogResult]::OK){[Console]::Out.Write($d.SelectedPath)}"
            )
            result = subprocess.run(
                ["powershell.exe", "-NoProfile", "-STA", "-Command", script],
                capture_output=True, text=True, timeout=180,
            )
            if result.returncode == 0 and result.stdout.strip():
                return result.stdout.strip()
        elif system == "darwin":
            result = subprocess.run(
                ["osascript", "-e", 'POSIX path of (choose folder with prompt "Choose a folder for BiliSum notes")'],
                capture_output=True, text=True, timeout=180,
            )
            if result.returncode == 0 and result.stdout.strip():
                return result.stdout.strip()
        else:
            if shutil.which("zenity"):
                result = subprocess.run(["zenity", "--file-selection", "--directory", "--title=Choose a folder for BiliSum notes"], capture_output=True, text=True, timeout=180)
                if result.returncode == 0 and result.stdout.strip():
                    return result.stdout.strip()
            if shutil.which("kdialog"):
                result = subprocess.run(["kdialog", "--getexistingdirectory", str(Path.home())], capture_output=True, text=True, timeout=180)
                if result.returncode == 0 and result.stdout.strip():
                    return result.stdout.strip()
    except subprocess.TimeoutExpired:
        raise RuntimeError("Folder selection timed out")
    except Exception as exc:
        raise RuntimeError(f"Could not open the native folder picker: {exc}")
    return ""


def process_save_directory_job(job_id: str) -> None:
    try:
        update_job(job_id, status="running", stage="choosing_directory", progress=10, detail="Waiting for folder selection")
        selected = pick_directory_native()
        if not selected:
            update_job(job_id, status="done", stage="done", progress=100, detail="Folder selection cancelled", result={"ok": False, "cancelled": True, "directory": ""})
            return
        directory = validate_save_directory(selected)
        config = load_config(); config["save_dir"] = str(directory); write_config(config)
        update_job(job_id, status="done", stage="done", progress=100, detail="Save folder selected", result={"ok": True, "cancelled": False, "directory": str(directory)})
    except Exception as exc:
        update_job(job_id, status="error", stage="error", progress=100, detail=str(exc), error=str(exc))


def save_text_file(filename: str, content: str) -> dict[str, Any]:
    directory = configured_save_directory()
    if not directory:
        raise RuntimeError("Please choose a BiliSum save folder first")
    name = safe_filename(filename, "BiliSum_notes.txt")
    target = (directory / name).resolve()
    if target.parent != directory.resolve():
        raise RuntimeError("Invalid save filename")
    # UTF-8 with BOM keeps Windows Notepad and older text editors from showing mojibake.
    target.write_text(str(content or ""), encoding="utf-8-sig")
    return {"ok": True, "path": str(target), "directory": str(directory), "filename": name, "bytes": target.stat().st_size}


def is_public_http_url(url: str) -> bool:
    try:
        parsed = urllib.parse.urlsplit(url)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            return False
        if parsed.username is not None or parsed.password is not None:
            return False
        infos = socket.getaddrinfo(parsed.hostname, parsed.port or (443 if parsed.scheme == "https" else 80))
        addresses = {info[4][0] for info in infos}
        if not addresses:
            return False
        for address in addresses:
            ip = ipaddress.ip_address(address)
            if not ip.is_global:
                return False
        return True
    except Exception:
        return False


def media_suffix(url: str) -> str:
    try:
        suffix = Path(urllib.parse.urlsplit(url).path).suffix.lower()
        if suffix and len(suffix) <= 8:
            return suffix
    except Exception:
        pass
    return ".media"


def download_media(urls: list[str], target_base: Path, referer: str, job_id: str) -> Path:
    last_error: Exception | None = None
    for index, url in enumerate(urls):
        if not is_public_http_url(url):
            last_error = RuntimeError("Rejected non-public media URL")
            continue
        target = target_base.with_suffix(media_suffix(url))
        try:
            update_job(job_id, stage="downloading", progress=3, detail=f"Downloading audio source {index + 1}/{len(urls)}")
            req = urllib.request.Request(
                url,
                headers={
                    "User-Agent": USER_AGENT,
                    "Referer": referer or "https://www.bilibili.com/",
                    "Accept": "*/*",
                    "Accept-Encoding": "identity",
                    "Range": "bytes=0-",
                },
                method="GET",
            )
            with urllib.request.urlopen(req, timeout=35) as response:
                length = response.headers.get("Content-Length")
                if length and int(length) > MAX_MEDIA_BYTES:
                    raise RuntimeError("Media is too large for the configured local ASR limit")
                total = int(length) if length and length.isdigit() else 0
                read = 0
                with open(target, "wb") as out:
                    while True:
                        chunk = response.read(1024 * 1024)
                        if not chunk:
                            break
                        read += len(chunk)
                        if read > MAX_MEDIA_BYTES:
                            raise RuntimeError("Media exceeded the local ASR size limit")
                        out.write(chunk)
                        if total:
                            pct = 3 + min(17, int(read / total * 17))
                            update_job(job_id, progress=pct)
            if target.stat().st_size < 1024:
                raise RuntimeError("Downloaded media file is unexpectedly small")
            return target
        except Exception as exc:
            last_error = exc
            try:
                target.unlink(missing_ok=True)
            except Exception:
                pass
    raise RuntimeError(f"Could not download the Bilibili audio stream: {last_error}")


def physical_memory_gb() -> float:
    """Best-effort physical RAM detection using only the Python standard library."""
    try:
        if os.name == "nt":
            import ctypes

            class MEMORYSTATUSEX(ctypes.Structure):
                _fields_ = [
                    ("dwLength", ctypes.c_ulong),
                    ("dwMemoryLoad", ctypes.c_ulong),
                    ("ullTotalPhys", ctypes.c_ulonglong),
                    ("ullAvailPhys", ctypes.c_ulonglong),
                    ("ullTotalPageFile", ctypes.c_ulonglong),
                    ("ullAvailPageFile", ctypes.c_ulonglong),
                    ("ullTotalVirtual", ctypes.c_ulonglong),
                    ("ullAvailVirtual", ctypes.c_ulonglong),
                    ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
                ]

            stat = MEMORYSTATUSEX()
            stat.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
            if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat)):
                return round(stat.ullTotalPhys / (1024**3), 2)
        if sys_platform := platform.system().lower():
            if sys_platform == "darwin":
                out = subprocess.check_output(["sysctl", "-n", "hw.memsize"], text=True, timeout=2).strip()
                return round(int(out) / (1024**3), 2)
            if hasattr(os, "sysconf"):
                pages = os.sysconf("SC_PHYS_PAGES")
                page_size = os.sysconf("SC_PAGE_SIZE")
                if pages and page_size:
                    return round((pages * page_size) / (1024**3), 2)
    except Exception:
        pass
    return 0.0


def recommended_whisper_model() -> str:
    ram = physical_memory_gb()
    # Keep Chinese transcription usable even on modest machines. "base" is the
    # low-memory fallback; "small" is noticeably better and remains the normal choice.
    if not ram or ram < 7.0:
        return "base"
    return "small"


def system_profile() -> dict[str, Any]:
    return {
        "os": platform.system(),
        "release": platform.release(),
        "arch": platform.machine(),
        "python": platform.python_version(),
        "cpu_count": os.cpu_count() or 0,
        "memory_gb": physical_memory_gb(),
        "nvidia_detected": have_nvidia(),
        "recommended_whisper_model": recommended_whisper_model(),
    }


def have_nvidia() -> bool:
    exe = shutil.which("nvidia-smi")
    if not exe:
        return False
    try:
        result = subprocess.run([exe, "-L"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=4)
        return result.returncode == 0
    except Exception:
        return False


def _create_model(model_name: str, device: str, compute_type: str):
    if importlib.util.find_spec("faster_whisper") is None:
        raise RuntimeError("faster-whisper is not installed. Run the SETUP script for this operating system again.")
    from faster_whisper import WhisperModel

    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    return WhisperModel(
        model_name,
        device=device,
        compute_type=compute_type,
        download_root=str(MODEL_DIR),
        cpu_threads=max(1, min(12, os.cpu_count() or 4)),
        num_workers=1,
    )


def get_model(model_name: str, device_pref: str, force_cpu: bool = False):
    global MODEL, MODEL_KEY, MODEL_META
    model_name = (model_name or "auto").strip()
    if model_name.lower() == "auto":
        model_name = recommended_whisper_model()
    device_pref = (device_pref or "auto").lower()
    if force_cpu or device_pref == "cpu":
        device, compute = "cpu", "int8"
    elif device_pref == "cuda":
        device, compute = "cuda", "float16"
    else:
        device, compute = ("cuda", "float16") if have_nvidia() else ("cpu", "int8")

    key = (model_name, device, compute)
    with MODEL_LOCK:
        if MODEL is not None and MODEL_KEY == key:
            return MODEL, dict(MODEL_META)
        try:
            model = _create_model(model_name, device, compute)
        except Exception as exc:
            if device_pref == "auto" and device == "cuda":
                device, compute = "cpu", "int8"
                key = (model_name, device, compute)
                model = _create_model(model_name, device, compute)
                MODEL_META = {
                    "loaded": True,
                    "model": model_name,
                    "device": device,
                    "compute_type": compute,
                    "fallback": f"CUDA unavailable; CPU fallback: {exc}",
                }
            else:
                raise
        else:
            MODEL_META = {"loaded": True, "model": model_name, "device": device, "compute_type": compute, "fallback": ""}
        MODEL = model
        MODEL_KEY = key
        return MODEL, dict(MODEL_META)


def cache_path(cache_key: str, model: str, language: str) -> Path:
    raw = f"{cache_key}|{model}|{language or 'auto'}".encode("utf-8")
    digest = hashlib.sha256(raw).hexdigest()
    return CACHE_DIR / f"{digest}.json"


def load_cache(path: Path) -> dict[str, Any] | None:
    try:
        if path.exists():
            data = json.loads(path.read_text(encoding="utf-8"))
            if data.get("segments"):
                data["cached"] = True
                return data
    except Exception:
        pass
    return None


def save_cache(path: Path, data: dict[str, Any]) -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


def looks_like_cuda_runtime_error(exc: Exception) -> bool:
    text = str(exc).lower()
    return any(x in text for x in ("cuda", "cudnn", "cublas", "cudnn_ops", "library cublas", "out of memory"))


def transcribe_with_model(path: Path, model_name: str, device_pref: str, language: str, job_id: str):
    update_job(job_id, stage="loading_model", progress=22, detail=f"Loading Whisper {model_name}")
    model, meta = get_model(model_name, device_pref)

    def run(active_model, active_meta):
        update_job(
            job_id,
            stage="transcribing",
            progress=26,
            detail=f"Whisper {model_name} · {active_meta.get('device', 'cpu')} {active_meta.get('compute_type', '')}".strip(),
        )
        segments, info = active_model.transcribe(
            str(path),
            language=(language or None),
            task="transcribe",
            beam_size=3,
            vad_filter=True,
            vad_parameters={"min_silence_duration_ms": 500},
            condition_on_previous_text=True,
            word_timestamps=False,
        )
        out = []
        duration = float(getattr(info, "duration", 0.0) or 0.0)
        for seg in segments:
            text = str(getattr(seg, "text", "") or "").strip()
            if not text:
                continue
            start = float(getattr(seg, "start", 0.0) or 0.0)
            end = float(getattr(seg, "end", start) or start)
            out.append({"from": round(start, 3), "to": round(end, 3), "content": text})
            if duration > 0:
                pct = 26 + min(68, int(max(0.0, min(1.0, end / duration)) * 68))
                update_job(job_id, progress=pct)
        result_info = {
            "language": str(getattr(info, "language", "") or ""),
            "language_probability": float(getattr(info, "language_probability", 0.0) or 0.0),
            "duration": duration,
        }
        return out, result_info

    try:
        lines, info = run(model, meta)
        return lines, info, meta
    except Exception as exc:
        if (device_pref or "auto").lower() == "auto" and meta.get("device") == "cuda" and looks_like_cuda_runtime_error(exc):
            update_job(job_id, stage="loading_model", progress=24, detail="GPU Whisper unavailable; falling back to CPU INT8")
            model, meta = get_model(model_name, "cpu", force_cpu=True)
            lines, info = run(model, meta)
            meta["fallback"] = f"GPU runtime unavailable; CPU fallback: {exc}"
            return lines, info, meta
        raise


def process_asr_job(job_id: str) -> None:
    job = get_job(job_id)
    if not job:
        return
    payload = job["payload"]
    model_name = str(payload.get("model") or "auto").strip()
    if model_name.lower() == "auto":
        model_name = recommended_whisper_model()
    device = str(payload.get("device") or "auto")
    language = str(payload.get("language") or "").strip().lower()
    cache_key = str(payload.get("cache_key") or job_id)
    cpath = cache_path(cache_key, model_name, language)
    cached = load_cache(cpath)
    if cached:
        update_job(job_id, status="done", stage="done", progress=100, detail="Loaded cached Whisper transcript", result=cached)
        return

    urls = [str(payload.get("audio_url") or "")]
    urls += [str(x) for x in (payload.get("backup_urls") or []) if x]
    urls = [x for x in urls if x]
    if not urls:
        raise RuntimeError("No audio URL was supplied to local Whisper")

    duration_sec = float(payload.get("duration_sec") or 0)
    max_minutes = float(payload.get("max_minutes") or 0)
    if max_minutes > 0 and duration_sec > max_minutes * 60:
        raise RuntimeError(f"Video part is {duration_sec / 60:.1f} min, above the local Whisper limit of {max_minutes:.0f} min")

    TEMP_DIR.mkdir(parents=True, exist_ok=True)
    target_base = TEMP_DIR / f"{job_id}"
    media_path: Path | None = None
    try:
        media_path = download_media(
            urls,
            target_base,
            str(payload.get("referer") or "https://www.bilibili.com/"),
            job_id,
        )
        lines, info, meta = transcribe_with_model(media_path, model_name, device, language, job_id)
        if not lines:
            raise RuntimeError("Whisper completed but produced no speech segments")
        result = {
            "version": VERSION,
            "cache_key": cache_key,
            "model": model_name,
            "device": meta.get("device", ""),
            "compute_type": meta.get("compute_type", ""),
            "fallback": meta.get("fallback", ""),
            "language": info.get("language", ""),
            "language_probability": info.get("language_probability", 0.0),
            "duration": info.get("duration", duration_sec),
            "segments": lines,
            "cached": False,
            "created_at": now(),
        }
        update_job(job_id, stage="caching", progress=97, detail="Caching transcript locally")
        save_cache(cpath, result)
        update_job(job_id, status="done", stage="done", progress=100, detail="Whisper transcript ready", result=result)
    finally:
        if media_path:
            try:
                media_path.unlink(missing_ok=True)
            except Exception:
                pass



def _http_json(url: str, data: dict[str, Any] | None = None, timeout: float = 20.0) -> dict[str, Any]:
    body = None
    headers = {"Accept": "application/json", "User-Agent": "BiliSum-Local/5.0"}
    method = "GET"
    if data is not None:
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json"
        method = "POST"
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=timeout) as response:
        raw = response.read()
    parsed = json.loads(raw.decode("utf-8")) if raw else {}
    if not isinstance(parsed, dict):
        raise RuntimeError("Local model returned an invalid JSON envelope")
    return parsed


def _model_score(name: str, size: int = 0) -> int:
    n = (name or "").lower()
    if not n or any(x in n for x in ("embed", "rerank", "vision", "cloud")):
        return -100000
    score = 0
    prefs = [
        ("qwen3.5", 1000), ("qwen3", 940), ("qwen2.5", 900), ("gemma3", 830),
        ("llama3.2", 790), ("llama3.1", 770), ("mistral", 720), ("glm", 700),
        ("deepseek-r1", 650), ("phi4", 620),
    ]
    for prefix, value in prefs:
        if n.startswith(prefix):
            score += value
            break
    # Prefer moderate local models for reliability instead of blindly choosing the largest.
    gib = size / (1024**3) if size else 0
    if 1.0 <= gib <= 8.0:
        score += 120
    elif 8.0 < gib <= 16.0:
        score += 80
    elif gib > 24.0:
        score -= 80
    return score


def ollama_status(configured: str = "auto") -> dict[str, Any]:
    try:
        data = _http_json(f"{OLLAMA_BASE.rstrip('/')}/api/tags", timeout=4.0)
        entries = data.get("models") or []
        names = [str(x.get("name") or x.get("model") or "") for x in entries if isinstance(x, dict)]
        selected = ""
        if configured and configured != "auto" and configured in names:
            selected = configured
        elif entries:
            ranked = sorted(
                (( _model_score(str(x.get("name") or x.get("model") or ""), int(x.get("size") or 0)), str(x.get("name") or x.get("model") or "")) for x in entries if isinstance(x, dict)),
                reverse=True,
            )
            if ranked and ranked[0][0] > -10000:
                selected = ranked[0][1]
        return {"ok": True, "models": names, "selected_model": selected, "has_model": bool(selected)}
    except Exception as exc:
        return {"ok": False, "models": [], "selected_model": "", "has_model": False, "reason": str(exc)}


def note_cache_path(payload: dict[str, Any]) -> Path:
    # Do not include volatile UI metadata in the cache key.
    stable = {k: v for k, v in payload.items() if k not in {"cache_key", "title"}}
    raw = json.dumps(stable, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return NOTE_CACHE_DIR / f"{hashlib.sha256(raw).hexdigest()}.json"


def process_note_job(job_id: str) -> None:
    job = get_job(job_id)
    if not job:
        return
    payload = job["payload"]
    cpath = note_cache_path(payload)
    cached = load_cache(cpath)
    # Transcript cache expects `segments`, so note cache is read separately.
    if cpath.exists():
        try:
            data = json.loads(cpath.read_text(encoding="utf-8"))
            if data.get("content"):
                data["cached"] = True
                update_job(job_id, status="done", stage="done", progress=100, detail="Loaded cached note result", result=data)
                return
        except Exception:
            pass

    configured = str(payload.get("model") or "auto")
    status = ollama_status(configured)
    if not status.get("ok"):
        raise RuntimeError(f"Ollama is not available: {status.get('reason') or 'unknown error'}")
    model = status.get("selected_model")
    if not model:
        raise RuntimeError("Ollama is running but no compatible chat model is installed")

    messages = payload.get("messages") or []
    if not isinstance(messages, list) or not messages:
        raise RuntimeError("Note job has no messages")
    request = {
        "model": model,
        "messages": messages,
        "stream": False,
        "think": False,
        "keep_alive": "10m",
        "options": {
            "temperature": float(payload.get("temperature") if payload.get("temperature") is not None else 0.08),
            "num_ctx": int(payload.get("num_ctx") or 32768),
        },
    }
    if payload.get("format"):
        request["format"] = payload["format"]
    update_job(job_id, stage="generating", progress=25, detail=f"Using {model}")
    started = now()
    data = _http_json(f"{OLLAMA_BASE.rstrip('/')}/api/chat", request, timeout=float(payload.get("timeout_sec") or 1800))
    if data.get("error"):
        raise RuntimeError(f"Ollama: {data.get('error')}")
    content = str((data.get("message") or {}).get("content") or "").strip()
    if not content:
        raise RuntimeError("Ollama returned an empty result")
    result = {
        "content": content,
        "selected_model": model,
        "cached": False,
        "created_at": now(),
        "elapsed_sec": round(now() - started, 2),
        "prompt_tokens": int(data.get("prompt_eval_count") or 0),
        "output_tokens": int(data.get("eval_count") or 0),
    }
    NOTE_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    tmp = cpath.with_suffix(".tmp")
    tmp.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(cpath)
    update_job(job_id, status="done", stage="done", progress=100, detail="Note result ready", result=result)


def process_job(job_id: str, expected_kind: str) -> None:
    job = get_job(job_id)
    if not job:
        return
    kind = str(job.get("kind") or "asr")
    if kind != expected_kind:
        raise RuntimeError(f"Job kind mismatch: expected {expected_kind}, got {kind}")
    if kind == "notes":
        process_note_job(job_id)
    else:
        process_asr_job(job_id)


def worker_loop(kind: str, job_queue: queue.Queue[str]) -> None:
    while True:
        job_id = job_queue.get()
        try:
            detail = "Starting note job" if kind == "notes" else "Starting transcription job"
            update_job(job_id, status="running", stage="starting", progress=1, detail=detail)
            process_job(job_id, kind)
        except Exception as exc:
            update_job(
                job_id,
                status="error",
                stage="error",
                progress=100,
                error=str(exc),
                detail=str(exc),
                traceback=traceback.format_exc(limit=8),
            )
        finally:
            job_queue.task_done()
            clean_old_jobs()


def worker_alive(kind: str) -> bool:
    thread = WORKERS.get(kind)
    return bool(thread and thread.is_alive())



def configure_runtime(*, root: str | Path | None = None, ollama_base: str | None = None) -> None:
    """Configure persistent runtime paths and start worker lanes once."""
    global DATA_DIR, CACHE_DIR, NOTE_CACHE_DIR, MODEL_DIR, TEMP_DIR, OLLAMA_BASE, CONFIG_FILE
    if root is not None:
        DATA_DIR = Path(root).expanduser().resolve()
    CACHE_DIR = DATA_DIR / "asr_cache"
    NOTE_CACHE_DIR = DATA_DIR / "note_cache"
    MODEL_DIR = DATA_DIR / "whisper_models"
    TEMP_DIR = DATA_DIR / "tmp"
    CONFIG_FILE = DATA_DIR / "config.json"
    if ollama_base:
        OLLAMA_BASE = str(ollama_base).rstrip("/")
    for directory in (DATA_DIR, CACHE_DIR, NOTE_CACHE_DIR, MODEL_DIR, TEMP_DIR):
        directory.mkdir(parents=True, exist_ok=True)
    if not worker_alive("notes"):
        WORKERS["notes"] = threading.Thread(target=worker_loop, args=("notes", NOTE_QUEUE), name="bilisum-note-worker", daemon=True)
        WORKERS["notes"].start()
    if not worker_alive("asr"):
        WORKERS["asr"] = threading.Thread(target=worker_loop, args=("asr", ASR_QUEUE), name="bilisum-transcribe-worker", daemon=True)
        WORKERS["asr"].start()


def health() -> dict[str, Any]:
    return {
        "ok": True,
        "service": "bilisum-native-host",
        "version": VERSION,
        "queues": {"notes": NOTE_QUEUE.qsize(), "transcription": ASR_QUEUE.qsize()},
        "workers": {"notes": worker_alive("notes"), "transcription": worker_alive("asr")},
        "transcription_available": importlib.util.find_spec("faster_whisper") is not None,
        "transcription_model": dict(MODEL_META),
        "data_dir": str(DATA_DIR),
        "system": system_profile(),
        "ollama": ollama_status("auto"),
    }


def start_job(kind: str, payload: dict[str, Any]) -> dict[str, Any]:
    if kind not in {"notes", "asr"}:
        raise ValueError("Unknown job kind")
    job_id = uuid.uuid4().hex
    job = {
        "job_id": job_id, "kind": kind, "status": "queued", "stage": "queued", "progress": 0,
        "detail": "Queued", "created_at": now(), "updated_at": now(), "payload": dict(payload or {}),
    }
    target = NOTE_QUEUE if kind == "notes" else ASR_QUEUE
    with JOBS_LOCK:
        JOBS[job_id] = job
    target.put(job_id)
    lane = "notes" if kind == "notes" else "transcription"
    update_job(job_id, detail=f"Queued in {lane} lane", queue_position=target.qsize())
    return {"job_id": job_id, "kind": kind, "status": "queued", "queue_size": target.qsize()}


def public_job(job_id: str) -> dict[str, Any]:
    job = get_job(job_id)
    if not job:
        raise KeyError("Job not found")
    public = {k: v for k, v in job.items() if k not in {"payload", "traceback"}}
    kind = str(job.get("kind") or "asr")
    q = NOTE_QUEUE if kind == "notes" else ASR_QUEUE
    public["queue_size"] = q.qsize()
    public["worker_alive"] = worker_alive(kind)
    public["queued_sec"] = round(max(0.0, now() - float(job.get("created_at") or now())), 1) if job.get("status") == "queued" else 0
    if job.get("status") == "queued" and not public["worker_alive"] and public["queued_sec"] > 5:
        public.update(status="error", stage="error", error="Local worker is not running", detail="Local worker is not running")
    return public



def active_jobs() -> list[dict[str, Any]]:
    with JOBS_LOCK:
        return [
            {"job_id": key, "kind": value.get("kind"), "status": value.get("status")}
            for key, value in JOBS.items()
            if value.get("status") in {"queued", "running"}
        ]

def save_status() -> dict[str, Any]:
    config = load_config()
    raw = str(config.get("save_dir") or "")
    directory = configured_save_directory()
    return {"configured": bool(raw), "available": bool(directory), "directory": str(directory) if directory else raw}


def choose_save_directory() -> dict[str, Any]:
    job_id = uuid.uuid4().hex
    job = {"job_id": job_id, "kind": "save_dir", "status": "queued", "stage": "queued", "progress": 0, "detail": "Waiting for folder selection", "created_at": now(), "updated_at": now(), "payload": {}}
    with JOBS_LOCK:
        JOBS[job_id] = job
    threading.Thread(target=process_save_directory_job, args=(job_id,), name=f"bilisum-save-{job_id[:8]}", daemon=True).start()
    return {"job_id": job_id, "kind": "save_dir", "status": "queued"}


def set_save_directory(directory: str) -> dict[str, Any]:
    path = validate_save_directory(directory)
    config = load_config(); config["save_dir"] = str(path); write_config(config)
    return {"ok": True, "directory": str(path)}


def clear_save_directory() -> dict[str, Any]:
    config = load_config(); config.pop("save_dir", None); write_config(config)
    return {"ok": True, "directory": ""}
