# Architecture

## Components

### Browser extension

`extension/` is a Manifest V3 extension. It handles Bilibili navigation, subtitle retrieval, UI, batching and cache metadata.

The extension communicates with the local host through `chrome.runtime.connectNative()` using the host name `com.bilisum.local`.

### Native host

`host/bilisum_host/native.py` implements Chrome Native Messaging framing over stdin/stdout. It does not bind a BiliSum network listener.

The host exposes a small RPC surface:

- `health`
- `jobs.start.notes`
- `jobs.start.transcription`
- `jobs.get`
- `save.*`
- `updates.*`

### Processing core

`host/bilisum_host/core.py` owns two independent queues:

- notes queue
- transcription queue

Separating the queues prevents a long Whisper task from blocking note generation.

### Runtime state

`.runtime/` is intentionally outside version control. It contains virtual environments, Whisper model files, transcript/note caches, native host registration metadata, settings and staged updates.

## Browser navigation

Bilibili uses client-side navigation. BiliSum combines `webNavigation` events, URL polling and DOM self-healing so the floating panel remains available when the user changes videos without a full page reload.

## Text pipeline

1. Fetch Bilibili video metadata and subtitle tracks.
2. For parts with no subtitle track, obtain the audio source and submit a local Whisper task.
3. Preserve part index and timestamps.
4. For long transcripts, extract structured chunks first.
5. Produce the final structured note using a JSON schema.
6. Cache the transcript and note independently.

The note prompt is constrained to source material; it must not add outside facts.

## Update channels

The portable channel checks a GitHub Release in the repository configured by `release_channel.json`. It verifies the GitHub-provided SHA-256 asset digest before extraction. `.runtime/` and `.git/` are preserved.

A future store channel should be distributed through Chrome Web Store and rely on browser-managed extension updates. The native host registrar supports adding a store extension ID alongside the deterministic development ID.
