---
name: flclash-headless-config-import
description: Import a Clash subscription/profile YAML into FLClash (Flutter GUI client) without using the GUI, by directly manipulating its SQLite database, profiles directory, and shared_preferences.json.
version: 1.1.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [flclash, clash, proxy, flutter, sqlite, headless, config-import]
---

# FLClash Headless Config Import

Import a downloaded Clash YAML config into FLClash on Linux when you cannot (or don't want to) use the GUI import dialog.

## Trigger conditions

- User has downloaded a `.yaml` / `.yml` Clash config (e.g. from Chrome) and wants FLClash to use it
- FLClash is already installed
- Session is headless, remote SSH, or the user simply wants automated setup

## Why this skill exists

FLClash stores its state in three places simultaneously:
1. `~/.local/share/com.follow.clash/database.sqlite` — profile metadata
2. `~/.local/share/com.follow.clash/profiles/<id>.yaml` — the actual config files
3. `~/.local/share/com.follow.clash/shared_preferences.json` — Flutter app state, including `currentProfileId`

You must update **all three** for the config to be recognized and auto-selected on launch.

## Step-by-step workflow

### 1. Locate the downloaded config

Usually in `~/Downloads/`:
```bash
ls -la ~/Downloads/ | grep -i -E "yaml|yml|clash"
```

### 2. Verify FLClash data directory exists

If FLClash has never been launched, start it once (even if it fails in headless mode) so it creates the directory structure:
```bash
timeout 3 FlClash 2>/dev/null || true
```

Then verify:
```bash
ls -la ~/.local/share/com.follow.clash/
```

You should see `database.sqlite`, `shared_preferences.json`, `config.yaml`, GeoIP databases, etc.

### 3. Inspect the database schema

Use Python (sqlite3 CLI may not be installed):
```python
import sqlite3, os
db = os.path.expanduser("~/.local/share/com.follow.clash/database.sqlite")
conn = sqlite3.connect(db)
c = conn.cursor()
c.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='profiles'")
print(c.fetchone()[0])
conn.close()
```

**Critical finding**: `id` is `INTEGER PRIMARY KEY` (auto-increment), **not** a UUID string. Inserting a string UUID causes `datatype mismatch`.

### 4. Import the config

Run a Python script that does all three updates atomically:

```python
import sqlite3, os, json, shutil
from datetime import datetime

base_dir = os.path.expanduser("~/.local/share/com.follow.clash")
db_path = os.path.join(base_dir, "database.sqlite")
config_src = os.path.expanduser("~/Downloads/Clash_xxxx.yaml")  # adjust path

# Ensure profiles directory exists
profiles_dir = os.path.join(base_dir, "profiles")
os.makedirs(profiles_dir, exist_ok=True)

# Insert profile metadata
conn = sqlite3.connect(db_path)
cursor = conn.cursor()
now = int(datetime.now().timestamp() * 1000)

cursor.execute("""
    INSERT INTO profiles (
        label, current_group_name, url, last_update_date,
        overwrite_type, script_id, auto_update_duration_millis,
        subscription_info, auto_update, selected_map, unfold_set, "order"
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
""", (
    "Imported Config", None, "", now,
    "0", None, 0,
    None, 0, "{}", "{}", 0
))

profile_id = cursor.lastrowid
conn.commit()
conn.close()

# Copy config file with the integer ID as filename
config_dst = os.path.join(profiles_dir, f"{profile_id}.yaml")
shutil.copy2(config_src, config_dst)

# Update Flutter shared_preferences to set currentProfileId
prefs_path = os.path.join(base_dir, "shared_preferences.json")
with open(prefs_path, 'r') as f:
    prefs = json.load(f)

flutter_config = json.loads(prefs["flutter.config"])
flutter_config["currentProfileId"] = profile_id
prefs["flutter.config"] = json.dumps(flutter_config, ensure_ascii=False)

with open(prefs_path, 'w') as f:
    json.dump(prefs, f, ensure_ascii=False)

print(f"Done. Profile ID: {profile_id}")
```

### 5. Verify

```bash
ls -la ~/.local/share/com.follow.clash/profiles/
python3 -c "import json; d=json.load(open('$HOME/.local/share/com.follow.clash/shared_preferences.json')); print('currentProfileId:', json.loads(d['flutter.config'])['currentProfileId'])"
```

### 6. Launch FLClash

The config should be active immediately when FLClash starts:
```bash
FlClash
```

Or via the desktop environment launcher.

## Troubleshooting: Import Errors

### `cannot unmarshal !!str '...' into config.RawConfig`

This error means the parser received a plain string instead of a YAML object. Common causes:

**1. Subscription URL returns encrypted content**

Some providers serve encrypted subscriptions. Check with curl:
```bash
curl -sI -A "Mozilla/5.0" "YOUR_SUB_URL" | grep -i subscription-encryption
```

If you see `subscription-encryption: true`, the link returns encrypted data that FLClash cannot directly parse.

**Diagnosis steps:**
```bash
# Fetch the subscription content
curl -sL "YOUR_SUB_URL" > /tmp/sub.txt

# Check if it's base64
python3 -c "import base64; d=open('/tmp/sub.txt').read().strip(); base64.b64decode(d)"

# Check response headers for encryption
curl -sI "YOUR_SUB_URL" | grep -i "content-\|subscription-"
```

**Solutions:**
- Download the config via Chrome/browser first (browsers may handle decryption via extensions), then import the **local file** into FLClash
- Ask the provider for an unencrypted subscription link
- Update FLClash to the latest version — newer builds may support the provider's encryption scheme

**2. Confusing "local file import" with "subscription URL"**

Users sometimes paste a subscription URL into the local file picker, or vice versa. Clarify which method they are using:
- **Local file import**: Select the `.yaml` file from `~/Downloads/` — the file must contain valid YAML
- **Subscription URL**: Paste the provider's link — FLClash will fetch and parse it automatically (may fail if encrypted)

**3. File is actually base64-encoded**

Some providers distribute base64-encoded configs with `.yaml` extension. Check:
```python
import yaml, base64
with open("config.yaml") as f:
    content = f.read().strip()
try:
    yaml.safe_load(content)
    print("Valid YAML")
except:
    # Try base64 decode
    decoded = base64.b64decode(content).decode("utf-8")
    yaml.safe_load(decoded)
    print("Base64-encoded YAML — decode first")
```

## Pitfalls

1. **`id` is INTEGER, not UUID** — The `profiles` table uses an auto-increment integer primary key. Naming the file with a UUID will not work.
2. **Must update all three stores** — Database + profiles file + shared_preferences.json. Missing any one means FLClash won't recognize or auto-select the config.
3. **No sqlite3 CLI** — Many minimal NixOS installs don't have `sqlite3` in PATH. Use Python's built-in `sqlite3` module instead.
4. **URL is NOT NULL** — Even for local files without a subscription URL, insert an empty string `""` for the `url` column.
5. **FLClash must have been launched once** — The data directory and `database.sqlite` are created on first run. If they don't exist, launch FLClash briefly first.
6. **Subscription encryption** — Provider links with `subscription-encryption: true` cannot be directly consumed by FLClash. Use browser-downloaded local files instead.

## Runtime behavior on Linux desktops

### Close-to-tray (`minimizeOnExit`)

FLClash stores the `minimizeOnExit` flag inside `shared_preferences.json`:

```json
{
  "flutter.config": "{\"appSettingProps\":{\"minimizeOnExit\":true,\"showTrayTitle\":true,...}}"
}
```

**Important**: The Linux GUI build may **not expose this option in the settings UI**, even though the config key exists. If a user says "there is no such setting," check the actual JSON file before arguing.

Even when `minimizeOnExit` is `true`, it may not work reliably on Wayland compositors (e.g. Hyprland). The NixOS package does include `libayatana-appindicator`, but Flutter's `system_tray` plugin can fail to register a StatusNotifierItem on some Wayland sessions. When this happens, clicking the window's close button simply terminates the process.

**Diagnostic steps:**
```bash
# Check current value
python3 -c "import json; d=json.load(open('$HOME/.local/share/com.follow.clash/shared_preferences.json')); print(json.loads(d['flutter.config']).get('appSettingProps',{}).get('minimizeOnExit'))"

# Check if waybar/panel has a StatusNotifierHost
busctl --user list | grep -i "StatusNotifierItem"
```

### Workaround when tray minimization does not work

Do not rely on the application's close button. Use the compositor's mechanics instead:

**Hyprland example:**
```ini
# "Hide" the window instead of closing it
bind = SUPER, H, movetoworkspace, special:hidden
bind = SUPER SHIFT, H, togglespecialworkspace, hidden

# Pin FLClash to a dedicated workspace
windowrulev2 = workspace 10 silent, class:^(FlClash)$
```

This keeps the Flutter process alive without depending on a functional system tray.

## Success criteria

- `profiles/<id>.yaml` exists with the imported config content
- `profiles` table has a row with matching integer `id`
- `shared_preferences.json` has `currentProfileId` set to that integer
- Launching FLClash shows the imported profile and nodes without manual GUI import
