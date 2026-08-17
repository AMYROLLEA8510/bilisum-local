#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
HOST_DIR="$ROOT/host"
REQ="$HOST_DIR/requirements_asr.txt"
OS_NAME="$(uname -s)"; ARCH="$(uname -m)"
case "$OS_NAME" in Darwin) PLATFORM="macos-$ARCH";; Linux) PLATFORM="linux-$ARCH";; *) echo "Unsupported OS: $OS_NAME"; exit 2;; esac
VENV="$ROOT/.runtime/envs/$PLATFORM/venv"
PY="$VENV/bin/python"; HOST_EXE="$VENV/bin/bilisum-native-host"
mkdir -p "$(dirname "$VENV")"
step(){ printf '\n==> %s\n' "$1"; }
fail(){ printf 'ERROR: %s\n' "$1" >&2; exit 1; }
api_ok(){ curl -fsS --max-time 3 http://127.0.0.1:11434/api/tags >/dev/null 2>&1; }
memory_gb(){ if [ "$OS_NAME" = Darwin ]; then b=$(sysctl -n hw.memsize 2>/dev/null || echo 0); awk -v b="$b" 'BEGIN{printf "%.0f",b/1073741824}'; elif [ -r /proc/meminfo ]; then k=$(awk '/MemTotal:/ {print $2;exit}' /proc/meminfo); awk -v k="${k:-0}" 'BEGIN{printf "%.0f",k/1048576}'; else echo 0; fi; }
RAM="$(memory_gb)"; if [ "${RAM:-0}" -lt 6 ] 2>/dev/null; then DEFAULT_MODEL=qwen3.5:0.8b; elif [ "${RAM:-0}" -lt 10 ] 2>/dev/null; then DEFAULT_MODEL=qwen3.5:2b; else DEFAULT_MODEL=qwen3.5:4b; fi
printf 'BiliSum setup - %s / %s / ~%s GB RAM\n' "$OS_NAME" "$ARCH" "$RAM"
step "1/4 Ollama"
if ! api_ok; then
  if command -v ollama >/dev/null 2>&1; then nohup ollama serve >"$ROOT/.runtime/ollama.log" 2>&1 &
  else
    command -v curl >/dev/null 2>&1 || fail "curl is required."
    if [ "$OS_NAME" = Linux ]; then curl -fsSL https://ollama.com/install.sh | sh
    else
      echo "Ollama is not installed. Install the macOS app from ollama.com, start it, then rerun this setup."
      exit 1
    fi
  fi
  for _ in $(seq 1 30); do api_ok && break; sleep 1; done
fi
api_ok || fail "Ollama is not responding."
TAGS="$(curl -fsS http://127.0.0.1:11434/api/tags)"; NAMES="$(printf '%s' "$TAGS" | grep -Eo '"name"[[:space:]]*:[[:space:]]*"[^"]+"' | sed -E 's/.*"([^"]+)"$/\1/' || true)"; USABLE="$(printf '%s\n' "$NAMES" | grep -Ei '^(qwen3\.5|qwen3:|qwen2\.5|gemma3|llama3\.[123]|mistral|ministral|phi[34]|deepseek-r1|glm)' | grep -Eiv '(embed|rerank|cloud)' | head -n1 || true)"
if [ -n "$USABLE" ]; then echo "Using existing model: $USABLE"; else echo "Downloading $DEFAULT_MODEL"; curl -fS --max-time 7200 -H 'Content-Type: application/json' -d "{\"model\":\"$DEFAULT_MODEL\",\"stream\":false}" http://127.0.0.1:11434/api/pull >/dev/null; fi
step "2/4 Local transcription runtime"
if ! [ -x "$PY" ] || ! "$PY" -c 'import faster_whisper' >/dev/null 2>&1; then
  rm -rf "$VENV"
  SYSTEM_PY=""; for c in python3.12 python3.11 python3.10 python3 python; do if command -v "$c" >/dev/null 2>&1 && "$c" -c 'import sys;raise SystemExit(0 if (3,10)<=sys.version_info[:2]<(3,13) else 1)' >/dev/null 2>&1; then SYSTEM_PY="$(command -v "$c")"; break; fi; done
  if [ -n "$SYSTEM_PY" ]; then "$SYSTEM_PY" -m venv "$VENV" >/dev/null 2>&1 || true; fi
  if ! [ -x "$PY" ]; then
    UV="$(command -v uv 2>/dev/null || true)"; if [ -z "$UV" ]; then curl -LsSf https://astral.sh/uv/install.sh | env UV_NO_MODIFY_PATH=1 sh; UV="$HOME/.local/bin/uv"; fi
    "$UV" venv --python '>=3.10,<3.13' "$VENV"
  fi
  "$PY" -m pip install --disable-pip-version-check -r "$REQ"
fi
step "3/4 BiliSum host"
"$PY" -m pip install --disable-pip-version-check --no-deps --editable "$HOST_DIR" >/dev/null
[ -x "$HOST_EXE" ] || fail "Native host launcher was not created."
"$PY" "$ROOT/scripts/register_native_host.py" --root "$ROOT" --host-executable "$HOST_EXE"
tr -d "\r\n" < "$ROOT/RUNTIME_SCHEMA" > "$ROOT/.runtime/runtime_schema.txt"
step "4/4 Ready"
printf 'Setup complete. Load the %s/extension folder as an unpacked extension in Chrome/Edge/Chromium.\n' "$ROOT"
