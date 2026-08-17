from __future__ import annotations

import base64
import hashlib
import importlib.util
import json
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'host'))
sys.path.insert(0, str(ROOT / 'scripts'))

from bilisum_host.update_manager import _safe_extract, _version_tuple  # noqa: E402
from register_native_host import allowed_origins, extension_id  # noqa: E402


class ReleaseTests(unittest.TestCase):
    def test_versions_match(self):
        version = (ROOT / 'VERSION').read_text(encoding='utf-8').strip()
        manifest = json.loads((ROOT / 'extension' / 'manifest.json').read_text(encoding='utf-8'))
        self.assertEqual(manifest['version'], version)
        self.assertIn(f'__version__ = "{version}"', (ROOT / 'host' / 'bilisum_host' / '__init__.py').read_text(encoding='utf-8'))
        self.assertIn(f'VERSION = "{version}"', (ROOT / 'host' / 'bilisum_host' / 'core.py').read_text(encoding='utf-8'))
        self.assertIn(f'version = "{version}"', (ROOT / 'host' / 'pyproject.toml').read_text(encoding='utf-8'))

    def test_manifest_has_no_custom_local_http_permission(self):
        manifest = json.loads((ROOT / 'extension' / 'manifest.json').read_text(encoding='utf-8'))
        self.assertIn('nativeMessaging', manifest['permissions'])
        self.assertTrue(all('127.0.0.1' not in item and 'localhost' not in item for item in manifest.get('host_permissions', [])))

    def test_development_extension_id_is_deterministic(self):
        manifest_path = ROOT / 'extension' / 'manifest.json'
        manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
        raw = base64.b64decode(manifest['key'])
        digest = hashlib.sha256(raw).digest()[:16].hex().translate(str.maketrans('0123456789abcdef', 'abcdefghijklmnop'))
        self.assertEqual(extension_id(manifest_path), digest)
        origins = allowed_origins(ROOT)
        self.assertEqual(origins[0], f'chrome-extension://{digest}/')
        self.assertNotIn('*', origins[0])

    def test_version_comparison(self):
        self.assertGreater(_version_tuple('5.2.1'), _version_tuple('5.2.0'))
        self.assertEqual(_version_tuple('v5.2.0'), _version_tuple('5.2.0'))

    def test_safe_extract_rejects_traversal(self):
        with tempfile.TemporaryDirectory() as tmp:
            archive = Path(tmp) / 'bad.zip'
            out = Path(tmp) / 'out'
            with zipfile.ZipFile(archive, 'w') as zf:
                zf.writestr('../escape.txt', 'no')
            with self.assertRaises(RuntimeError):
                _safe_extract(archive, out)


if __name__ == '__main__':
    unittest.main()
