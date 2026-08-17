# Security

## Local communication

BiliSum does not expose its own localhost HTTP listener. Browser-to-host communication uses Chrome Native Messaging over stdin/stdout. The native host manifest contains explicit `allowed_origins`; wildcard extension origins are not used.

The host may communicate with locally installed Ollama and download the selected Bilibili media stream for transcription. Media URL validation rejects non-HTTP(S) URLs, credentials in URLs, loopback/private/link-local media targets and URLs containing embedded credentials.

## Updates

Portable updates are fetched only from the repository configured in `release_channel.json`. The updater:

- requires HTTPS GitHub release assets;
- requires and verifies the release asset SHA-256 digest;
- rejects path traversal in ZIP archives;
- verifies the package `VERSION` against release metadata;
- preserves `.runtime/` and refuses to overwrite source Git checkouts.

## Secrets

No API key is required. Do not commit browser cookies, account credentials, `.runtime/`, environment files, private signing keys or downloaded model data.

## Reporting

Use a private GitHub security advisory for vulnerabilities that could expose local files, execute unintended code, bypass Native Messaging origin restrictions, or tamper with updates.
