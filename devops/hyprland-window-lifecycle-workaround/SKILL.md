---
name: hyprland-window-lifecycle-workaround
description: Diagnose and fix "app closes/exits when I close the window" on Hyprland, especially for apps that should minimize to tray. Covers killactive interception, system tray diagnostics, and special-workspace alternatives.
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [hyprland, wayland, tray, minimize, killactive, windowrule, nixos]
---

# Hyprland Window Lifecycle Workaround

When a Hyprland user reports that closing a window kills the app entirely — instead of minimizing to tray or staying in the background — use this diagnostic flow.

## Trigger conditions

- "Closing the window exits the app" (WeChat, FlClash, Telegram, etc.)
- "Hyprland has no minimize button"
- App has a "minimize on close" or "tray" setting that appears not to work
- User runs NixOS + home-manager + Hyprland + waybar

## Core insight

Hyprland has no traditional minimize. Apps that rely on system tray to stay alive after closing **can be silently broken by WM bindings** — specifically `killactive`, which force-destroys the window and gives the app no chance to intercept the close event.

## Step-by-step diagnosis

### 1. Check how the user closes the window

```bash
grep -E "bind.*killactive|bind.*close" ~/.config/hypr/hyprland.conf /etc/nixos/home.nix 2>/dev/null
```

**Critical finding**: If the user presses `Super+C` mapped to `killactive,`, the app is **forcibly destroyed**. No application-level `minimizeOnExit` setting can intercept this.

**Tell the user**: Test with the mouse — click the window's native X button instead of `killactive`. If the app survives, the binding is the problem.

### 2. Inspect the app's own tray/minimize settings

Many apps store this in internal JSON/SQLite even when the UI hides the option.

Example: FlClash (Flutter)
```bash
python3 -c "
import json
p = json.load(open('$HOME/.local/share/com.follow.clash/shared_preferences.json'))
c = json.loads(p['flutter.config'])
print('minimizeOnExit:', c.get('appSettingProps',{}).get('minimizeOnExit'))
print('showTrayTitle:', c.get('appSettingProps',{}).get('showTrayTitle'))
"
```

If the setting is `true` but closing still kills the app, continue to tray diagnostics.

### 3. Verify system tray infrastructure

Waybar must have a `tray` module, and the StatusNotifierWatcher must be registered:

```bash
# Is waybar running with tray support?
busctl --user list | grep -i "StatusNotifierWatcher"

# Is the tray module in waybar config?
grep -r '"tray"' ~/.config/waybar/ /etc/xdg/waybar/ 2>/dev/null
```

If waybar has no tray host, the app has nowhere to minimize to. Fix waybar config first.

### 4. Check app-specific behavior on Linux

Some Linux ports simply lack tray support (e.g. `wechat-uos` closes and exits — no daemon mode). If steps 1-3 are clean and the app still dies, the app itself is the limitation.

## Workarounds

### A) Use special workspace as "minimize"

Add to Hyprland config (via `~/.config/hypr/hyprland.conf` or NixOS `home.nix`):

```nix
bind = [
  "SUPER, H, movetoworkspace, special:hidden"
  "SUPER SHIFT, H, togglespecialworkspace, hidden"
];
```

- `Super+H` hides the current window (like minimize)
- `Super+Shift+H` brings it back

### B) Pin always-on apps to a dedicated workspace

```nix
windowrulev2 = [
  "workspace 9 silent, class:^(com.tencent.wechat|WeChat|wechat-uos)$"
];
```

This keeps the app out of the way without ever closing it.

### C) For NixOS + home-manager managed configs

The live `~/.config/hypr/hyprland.conf` is a **read-only symlink** to the Nix store. Edit the source:

```bash
# Usually here for flake-based setups
sudo sed -i 's/"SUPER, V, togglefloating,"/"SUPER, V, togglefloating,"\n        "SUPER, H, movetoworkspace, special:hidden"\n        "SUPER SHIFT, H, togglespecialworkspace, hidden"/' /etc/nixos/home.nix
```

**Pitfall**: `sed` insert position. If you append after a list's closing `];`, verify you didn't insert inside the preceding block. Always check syntax after:

```bash
nix-instantiate --parse /etc/nixos/home.nix
```

Then rebuild:
```bash
sudo nixos-rebuild switch
```

## Decision tree

1. User closes with `killactive` (e.g. `Super+C`)?
   → Tell them to use the mouse X button instead. Problem solved.

2. Mouse X button still kills the app?
   → Check app's tray setting (step 2). If `true`, check tray infrastructure (step 3).

3. Tray infrastructure missing?
   → Fix waybar config or panel.

4. Everything looks correct but app still dies?
   → The Linux port lacks tray/minimize support (e.g. `wechat-uos`). Use workaround A or B.

## Pitfalls

1. **`killactive` bypasses everything**: No application code can intercept it. This is the #1 cause of "minimizeOnExit doesn't work" reports.
2. **Home-manager configs are read-only symlinks**: Editing `~/.config/hypr/hyprland.conf` directly fails with "read-only file system". Edit `/etc/nixos/home.nix` (or wherever the home-manager source lives) and rebuild.
3. **sed insertion inside nested blocks**: Appending after `];` of one list can accidentally place content inside the previous list if line numbers shift. Always verify with `nix-instantiate --parse`.
4. **Some apps simply don't support tray on Linux**: Don't chase phantom bugs. `wechat-uos` is a known example — it exits on close, period.
5. **Waybar default config is Sway-oriented**: The default `config.jsonc` uses `sway/workspaces` which silently fails on Hyprland, but the `tray` module is generic and works.

## Success criteria

- User can hide/recall windows with `Super+H` / `Super+Shift+H`
- Apps pinned to dedicated workspaces launch there automatically
- If the app supports tray, closing with the mouse X button minimizes instead of exiting
