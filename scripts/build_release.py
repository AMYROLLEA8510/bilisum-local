from __future__ import annotations

import hashlib
import json
import shutil
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / 'dist'
INCLUDE_ROOT = [
    'VERSION', 'RUNTIME_SCHEMA', 'release_channel.json', 'README.md', 'LICENSE',
    'SECURITY.md', 'CHANGELOG.md', 'SETUP_WINDOWS.cmd', 'SETUP_MACOS.command',
    'SETUP_LINUX.sh', 'setup_windows.ps1', 'setup_unix.sh',
]
INCLUDE_DIRS = ['extension', 'host', 'docs']
INCLUDE_NESTED = ['scripts/register_native_host.py']
EXCLUDE_NAMES = {'__pycache__', '.runtime', 'dist', '.git', '.github', 'tests'}


def version() -> str:
    value = (ROOT / 'VERSION').read_text(encoding='utf-8').strip()
    if not value:
        raise RuntimeError('VERSION is empty')
    return value


def should_copy(path: Path) -> bool:
    return not any(part in EXCLUDE_NAMES for part in path.parts) and path.suffix != '.pyc'


def copy_tree(src: Path, dst: Path) -> None:
    for path in src.rglob('*'):
        rel = path.relative_to(src)
        if not should_copy(rel):
            continue
        target = dst / rel
        if path.is_dir():
            target.mkdir(parents=True, exist_ok=True)
        elif path.is_file():
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, target)


def verify_versions(ver: str) -> None:
    manifest = json.loads((ROOT / 'extension' / 'manifest.json').read_text(encoding='utf-8'))
    if manifest.get('version') != ver:
        raise RuntimeError('extension manifest version does not match VERSION')
    init_text = (ROOT / 'host' / 'bilisum_host' / '__init__.py').read_text(encoding='utf-8')
    if f'__version__ = "{ver}"' not in init_text:
        raise RuntimeError('host __version__ does not match VERSION')
    core_text = (ROOT / 'host' / 'bilisum_host' / 'core.py').read_text(encoding='utf-8')
    if f'VERSION = "{ver}"' not in core_text:
        raise RuntimeError('core VERSION does not match VERSION')
    pyproject = (ROOT / 'host' / 'pyproject.toml').read_text(encoding='utf-8')
    if f'version = "{ver}"' not in pyproject:
        raise RuntimeError('pyproject version does not match VERSION')


def main() -> None:
    ver = version()
    verify_versions(ver)
    DIST.mkdir(parents=True, exist_ok=True)
    for old in DIST.glob('BiliSum-Portable-*.zip'):
        old.unlink()
    with tempfile.TemporaryDirectory(prefix='bilisum-release-') as tmp:
        package_root = Path(tmp) / f'BiliSum-{ver}'
        package_root.mkdir()
        for name in INCLUDE_ROOT:
            src = ROOT / name
            if not src.exists():
                raise RuntimeError(f'Missing release file: {name}')
            shutil.copy2(src, package_root / name)
        for name in INCLUDE_DIRS:
            src = ROOT / name
            dst = package_root / name
            dst.mkdir(parents=True, exist_ok=True)
            copy_tree(src, dst)
        for name in INCLUDE_NESTED:
            src = ROOT / name
            dst = package_root / name
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
        archive = DIST / f'BiliSum-Portable-v{ver}.zip'
        with zipfile.ZipFile(archive, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
            for path in sorted(package_root.rglob('*')):
                if path.is_file():
                    zf.write(path, path.relative_to(package_root.parent).as_posix())
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    (DIST / 'SHA256SUMS.txt').write_text(f'{digest}  {archive.name}\n', encoding='utf-8')
    print(archive)
    print(f'sha256:{digest}')


if __name__ == '__main__':
    main()
