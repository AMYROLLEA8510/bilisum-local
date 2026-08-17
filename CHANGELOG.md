# Changelog

## 5.2.1

- Added stability-first two-video batch pipelines with conservative local-model parallelism.
- Added per-video batch checkpoints, resume-after-restart, and explicit retry for failed items.
- Added streaming Ollama progress, dynamic context sizing, and one automatic retry for interrupted model responses.
- Added a batch activity lease so portable updates cannot stage or apply during an active batch.
- Added paged Native Messaging delivery for very large Whisper transcripts.
- Removed duplicate full-transcript copies from stored batch records and added transcript-cache pruning while preserving summaries.
- Limited long-video Q&A to relevant transcript excerpts instead of sending the entire transcript blindly.
- Tightened list-page video discovery to reduce accidental inclusion of recommendation links.

## 5.2.0

- Replaced the custom BiliSum localhost service with Chrome Native Messaging.
- Removed custom BiliSum port configuration from the extension and settings UI.
- Added optional portable updates with GitHub Release digest verification.
- Added deterministic development extension ID and explicit native-host origin allowlist.
- Preserved local models, caches and settings across portable updates.
- Simplified product copy and diagnostic wording.
- Kept separate queues for note generation and transcription.
- Retained SPA navigation recovery, batch TXT output and selectable save directory.
