# Migration and backup

## Normal 5.2.x updates

Use BiliSum's built-in update flow. Portable updates preserve `.runtime/`, local models, caches and the selected save directory. Do not uninstall the extension for routine 5.2.x updates.

## First migration from 5.0.x development builds

Early 5.0.x builds did not use the deterministic extension identity used by 5.2.x. Chrome storage therefore should not be assumed to migrate automatically if the old extension is removed.

Before removing an old 5.0.x extension:

1. Finish or pause the current batch and save its combined TXT.
2. Keep the old extension installed until its storage has been exported if cached notes need to be retained.
3. Open the old extension settings page, open DevTools Console, and run:

```js
chrome.storage.local.get(null).then(d => {
  const a = document.createElement('a');
  a.href = URL.createObjectURL(new Blob([JSON.stringify(d)], {type: 'application/json'}));
  a.download = 'BiliSum-legacy-backup.json';
  a.click();
});
```

4. Install 5.2.1 or later.
5. Open **Settings → Backup and migration → Import backup** and select the exported JSON.

The importer also accepts the normal wrapped backup format produced by current BiliSum versions. Imports merge into existing storage rather than clearing it first.

## What a BiliSum storage backup contains

A full extension-storage backup can contain settings, single-video note caches, transcript copies, channel indexes and batch checkpoints. It does not contain Bilibili account passwords or API keys. Treat the backup as personal study data and store it accordingly.
