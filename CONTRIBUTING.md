# Contributing

Keep changes narrow and testable.

Before opening a pull request:

```bash
python scripts/security_check.py
python -m unittest discover -s tests -v
node --check extension/background.js
node --check extension/content.js
node --check extension/options.js
node --check extension/setup.js
bash -n setup_unix.sh
```

Do not commit `.runtime/`, models, caches, cookies, credentials, generated release ZIPs or local virtual environments.

For changes to user-visible note structure, keep prompts source-bounded: reorganize the transcript, but do not invent facts that are not present in the subtitle/transcription input.
