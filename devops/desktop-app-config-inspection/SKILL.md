---
title: Inspect Desktop App Internal Config via Upstream Source
name: desktop-app-config-inspection
category: devops
description: Reverse-engineer a Linux desktop app's config storage, data model, and lock behavior by reading its upstream source code. Emphasizes read-only inspection and safe cleanup before acting.
---

# Desktop App Config Inspection via Upstream Source

When a desktop application on Linux stores configuration in opaque internal formats (SQLite, JSON, binary) and lacks CLI documentation, inspect the upstream source code to understand its data model **before** touching any files.

## When to use

- App won't start after manual config changes
- Need to understand where an app stores its data on Linux
- App has no CLI `--help` or documented config paths
- Debugging corruption or lock-file issues

## Workflow

1. **Locate upstream source**
   - Find the app's GitHub repository or official source archive.

2. **Download source without `git`/`unzip`**
   ```bash
   curl -fsSL -o /tmp/app-src.zip "https://github.com/<owner>/<repo>/archive/refs/heads/main.zip"
   python3 -c "import zipfile, os; z=zipfile.ZipFile('/tmp/app-src.zip'); z.extractall('/tmp/app-src')"
   ```

3. **Search for storage logic**
   ```bash
   grep -rn 'path_provider\|getApplicationSupportDirectory\|shared_preferences\|database\|profiles' /tmp/app-src/lib/
   ```

4. **Read the data model classes**
   - Find model files (e.g., `lib/models/profile.dart`, `lib/models/config.dart`).
   - Note ID generation schemes (Snowflake, UUID, autoincrement).
   - Note file path conventions (e.g., `profiles/{id}.yaml`).

5. **Inspect live app state (read-only)**
   ```bash
   # SQLite
   python3 -c "import sqlite3; c=sqlite3.connect('~/.local/share/<app>/database.sqlite'); print(c.execute('PRAGMA table_info(profiles)').fetchall())"

   # JSON prefs
   python3 -m json.tool ~/.local/share/<app>/shared_preferences.json
   ```

6. **Check for single-instance locks**
   ```bash
   ps aux | grep -i <app>
   ls -la ~/.local/share/<app>/*.lock
   ```

## Critical rules

- **Prefer official methods first.** If the app has a CLI import/export API or documented config file format, use that instead.
- **Read-only inspection.** Do not modify internal DBs, lock files, or private config files until you have full schema understanding and user consent.
- **Never assume simple IDs.** Apps may use Snowflake (`((timestamp - epoch) << 22) | workerId | sequence`), UUIDs, or other distributed ID schemes.
- **Kill old processes before retesting.** A lingering process holding a lock file can make the app silently `exit(0)` on restart.

## Pitfalls

- Modifying `shared_preferences.json` or SQLite rows with guessed values often violates invariants and breaks startup.
- GUI-only apps (Flutter, Electron) frequently have **no CLI import capability** — accept this and guide the user through the GUI.
- `timeout N <gui-app>` is the standard way to test GUI app startup from a headless terminal without blocking forever.