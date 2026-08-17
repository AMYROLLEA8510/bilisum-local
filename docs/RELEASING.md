# Releasing

## Versioning

- `VERSION`
- `extension/manifest.json` → `version`
- `host/pyproject.toml` → `version`
- `host/bilisum_host/__init__.py` → `__version__`
- `host/bilisum_host/core.py` → `VERSION`

These values must match.

`RUNTIME_SCHEMA` changes only when an update changes local Python/runtime dependencies in a way that requires environment reconciliation.

## Portable release

1. Update version and changelog.
2. Run:

   ```bash
   python scripts/security_check.py
   python -m unittest discover -s tests -v
   python scripts/build_release.py
   ```

3. Commit the version change to `main`.
4. GitHub Actions detects the `VERSION` change, builds the portable ZIP, creates/updates `vX.Y.Z`, and publishes the Release assets automatically. A manual `workflow_dispatch` is also available for recovery.

The built-in updater selects assets whose names begin with `BiliSum-Portable-` and requires the GitHub Release API to provide a `sha256:` digest.

## Update compatibility

Normal source-only updates preserve `.runtime/` and require no model redownload.

If `RUNTIME_SCHEMA` changes, the detached updater installs the staged runtime requirements before replacing program files, then refreshes the editable native-host package.

## Chrome Web Store

Do not use the portable updater to overwrite a store-managed extension. Before preparing a store package:

1. upload an initial draft to the Chrome Web Store dashboard;
2. obtain the store extension ID/public key;
3. place the store ID in `release_channel.json`;
4. rerun setup so the Native Messaging host allows both the portable development ID and the store ID;
5. prepare a store-specific package and let Chrome manage extension updates.
