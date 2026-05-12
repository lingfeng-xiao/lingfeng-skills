---
name: obsidian-manual-plugin-ops
description: Manually install, configure, and remove Obsidian community plugins when the in-app marketplace is unavailable or the user prefers direct file management.
triggers:
  - User wants to install an Obsidian plugin without using the community plugin browser
  - User needs to roll back or uninstall an Obsidian plugin
  - Obsidian plugin market is blocked or not loading
---

# Obsidian Manual Plugin Operations

## Install a plugin

1. Find the plugin's GitHub repository.
2. Download the latest release assets:
   - `main.js` (required)
   - `manifest.json` (required)
   - `styles.css` (optional, only if the plugin provides one)
3. Create the plugin directory inside the vault:
   ```
   .obsidian/plugins/<plugin-id>/
   ```
   The `<plugin-id>` is the `id` field from `manifest.json`.
4. Place the downloaded files into that directory.
5. Add the plugin ID to `.obsidian/community-plugins.json`:
   ```json
   [
     "obsidian-git",
     "<plugin-id>"
   ]
   ```
6. **Fully restart Obsidian** (quit the application completely, then reopen). Simply closing the window may not be enough on all platforms.
7. Enable the plugin in Settings → Community Plugins.

## Preset default configuration

Many plugins read defaults from `.obsidian/plugins/<id>/data.json`. You can create this file before first launch to pre-configure the plugin.

To discover available config keys:
- Check the plugin source for a `DEFAULT_SETTINGS` or `defaultSettings` export.
- The settings schema is usually in a file named `*Setting*.ts` in the source repo.
- Common settings include: `defaultSearchEngine`, `darkMode`, `openInSameTab`, `highlightFormat`.

## Uninstall / Rollback

1. Remove the plugin ID from `.obsidian/community-plugins.json`.
2. Delete the directory `.obsidian/plugins/<plugin-id>/` entirely.
3. Restart Obsidian.

## Common pitfalls

- **Restart required for new plugins**: Obsidian only scans `community-plugins.json` at startup. Enabling/disabling an already-known plugin in the Settings UI does not require restart, but adding a new entry to the JSON list does.
- **Desktop-only plugins**: If `manifest.json` contains `"isDesktopOnly": true`, the plugin will not load on mobile and may silently fail if the desktop environment check does not pass.
- **Version mismatch**: If `manifest.json` declares `"minAppVersion": "1.4.0"` but Obsidian is older, the plugin will be disabled automatically.
