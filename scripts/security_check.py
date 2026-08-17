from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEXT_SUFFIXES = {'.js', '.json', '.py', '.ps1', '.sh', '.cmd', '.md', '.html', '.css', '.toml', '.txt'}
FORBIDDEN = {
    '8765': 'legacy custom BiliSum port',
    '8766': 'legacy custom BiliSum port',
    'backendBaseUrl': 'legacy HTTP backend configuration',
    'START_BACKEND': 'legacy daemon launcher',
    'ThreadingHTTPServer': 'custom HTTP listener',
    'BaseHTTPRequestHandler': 'custom HTTP listener',
}
SECRET_PATTERNS = [
    re.compile(r'sk-(?:proj-)?[A-Za-z0-9_-]{20,}'),
    re.compile(r'(?i)(api[_-]?key|access[_-]?token|secret)\s*[:=]\s*["\'][^"\']{12,}["\']'),
]


def tracked_text_files():
    for path in ROOT.rglob('*'):
        if not path.is_file():
            continue
        if any(part in {'.git', '.runtime', 'dist', '__pycache__'} for part in path.parts):
            continue
        if path.resolve() == Path(__file__).resolve():
            continue
        if path.suffix.lower() in TEXT_SUFFIXES or path.name in {'VERSION', 'RUNTIME_SCHEMA', 'LICENSE'}:
            yield path


def main() -> int:
    failures: list[str] = []
    for path in tracked_text_files():
        try:
            text = path.read_text(encoding='utf-8')
        except UnicodeDecodeError:
            continue
        rel = path.relative_to(ROOT)
        for needle, reason in FORBIDDEN.items():
            if needle in text:
                failures.append(f'{rel}: contains {reason} ({needle})')
        for pattern in SECRET_PATTERNS:
            if pattern.search(text):
                failures.append(f'{rel}: possible credential material')

    manifest = json.loads((ROOT / 'extension' / 'manifest.json').read_text(encoding='utf-8'))
    for item in manifest.get('host_permissions', []):
        if item.startswith('http://127.0.0.1') or item.startswith('http://localhost'):
            failures.append(f'extension/manifest.json: local HTTP host permission is not allowed: {item}')
    if 'nativeMessaging' not in manifest.get('permissions', []):
        failures.append('extension/manifest.json: nativeMessaging permission is required')

    if (ROOT / '.runtime').exists():
        failures.append('.runtime must not be included in a clean source/release tree')

    if failures:
        print('Security/release checks failed:', file=sys.stderr)
        for item in failures:
            print(f' - {item}', file=sys.stderr)
        return 1
    print('Security/release checks passed.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
