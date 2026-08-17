from __future__ import annotations

import json
import os
import struct
import sys
import traceback
from pathlib import Path
from typing import Any

from . import __version__
from . import core
from .update_manager import check_update, launch_apply, stage_update

HOST_NAME = "com.bilisum.local"
MAX_RESPONSE_BYTES = 1024 * 1024 - 4096
ROOT = Path(__file__).resolve().parents[2]
RUNTIME = ROOT / ".runtime"


def configure_stdio() -> None:
    if os.name == "nt":
        import msvcrt
        msvcrt.setmode(sys.stdin.fileno(), os.O_BINARY)
        msvcrt.setmode(sys.stdout.fileno(), os.O_BINARY)


def read_message() -> dict[str, Any] | None:
    raw_len = sys.stdin.buffer.read(4)
    if not raw_len:
        return None
    if len(raw_len) != 4:
        raise EOFError("Incomplete native message header")
    length = struct.unpack("@I", raw_len)[0]
    if length <= 0 or length > 64 * 1024 * 1024:
        raise ValueError("Invalid native message size")
    payload = sys.stdin.buffer.read(length)
    if len(payload) != length:
        raise EOFError("Incomplete native message body")
    data = json.loads(payload.decode("utf-8"))
    if not isinstance(data, dict):
        raise ValueError("Native message must be an object")
    return data


def write_message(data: dict[str, Any]) -> None:
    payload = json.dumps(data, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    if len(payload) > MAX_RESPONSE_BYTES:
        payload = json.dumps({"id": data.get("id"), "ok": False, "error": "Response is too large for Chrome native messaging"}, separators=(",", ":")).encode("utf-8")
    sys.stdout.buffer.write(struct.pack("@I", len(payload)))
    sys.stdout.buffer.write(payload)
    sys.stdout.buffer.flush()


def dispatch(method: str, params: dict[str, Any]) -> Any:
    if method == "health":
        return core.health()
    if method == "jobs.start.notes":
        return core.start_job("notes", params)
    if method == "jobs.start.transcription":
        return core.start_job("asr", params)
    if method == "jobs.get":
        return core.public_job(str(params.get("job_id") or ""))
    if method == "jobs.result.page":
        return core.job_result_page(
            str(params.get("job_id") or ""),
            int(params.get("offset") or 0),
            int(params.get("limit") or 400),
        )
    if method == "batch.begin":
        return core.batch_lease_begin(str(params.get("lease_id") or ""), float(params.get("ttl_sec") or 180))
    if method == "batch.heartbeat":
        return core.batch_lease_heartbeat(str(params.get("lease_id") or ""), float(params.get("ttl_sec") or 180))
    if method == "batch.end":
        return core.batch_lease_end(str(params.get("lease_id") or ""))
    if method == "save.status":
        return core.save_status()
    if method == "save.choose":
        return core.choose_save_directory()
    if method == "save.set":
        return core.set_save_directory(str(params.get("directory") or ""))
    if method == "save.clear":
        return core.clear_save_directory()
    if method == "save.note":
        return core.save_text_file(str(params.get("filename") or "BiliSum_notes.txt"), str(params.get("content") or ""))
    if method == "updates.check":
        return check_update(ROOT, __version__)
    if method == "updates.stage":
        if core.active_jobs() or core.batch_lease_active():
            raise RuntimeError("Finish or pause the current BiliSum batch before preparing an update")
        return stage_update(ROOT, __version__)
    if method == "updates.apply":
        active = core.active_jobs()
        if active or core.batch_lease_active():
            raise RuntimeError("Finish or pause current BiliSum tasks before installing an update")
        return launch_apply(ROOT, str(params.get("staging_path") or ""))
    raise ValueError(f"Unknown method: {method}")


def main() -> None:
    configure_stdio()
    core.configure_runtime(root=RUNTIME)
    while True:
        try:
            message = read_message()
            if message is None:
                break
            req_id = message.get("id")
            method = str(message.get("method") or "")
            params = message.get("params") if isinstance(message.get("params"), dict) else {}
            try:
                result = dispatch(method, params)
                write_message({"id": req_id, "ok": True, "result": result})
            except Exception as exc:
                write_message({"id": req_id, "ok": False, "error": str(exc), "error_type": exc.__class__.__name__})
        except (EOFError, BrokenPipeError):
            break
        except Exception as exc:
            try:
                write_message({"id": None, "ok": False, "error": str(exc)})
            except Exception:
                break


if __name__ == "__main__":
    main()
