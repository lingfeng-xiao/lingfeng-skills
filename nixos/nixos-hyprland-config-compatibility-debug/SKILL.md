---
title: Debug and Fix Hyprland Config Compatibility on NixOS
name: nixos-hyprland-config-compatibility-debug
description: Systematic debugging and fixing of Hyprland config errors when upgrading Hyprland or importing older dotfiles (e.g., end-4) on NixOS. Covers layerrule syntax changes, windowrulev2 deprecation, removed options, and home-manager override patterns.
trigger: When Hyprland shows red config error notifications on startup, especially after upgrading Hyprland or importing dotfiles (e.g., end-4/illogical-impulse) written for an older version.
---

# Debug and Fix Hyprland Config Compatibility on NixOS

## Key Pitfall: `--verify-config` is USELESS for runtime errors

`hyprland --verify-config -c /path/to/config` returns OK for most invalid syntax. It does NOT catch deprecated keywords, invalid field types, or missing values. Always use **runtime validation** via `hyprctl configerrors`.

## Diagnostic Workflow

1. **Check current errors**
   ```bash
   hyprctl configerrors 2>&1 | sort | uniq -c | sort -rn
   ```

2. **Identify error categories**
   - `config option <X> does not exist` → Option removed in new version
   - `windowrulev2 is deprecated` → Keyword deprecated but usually still functional
   - `Invalid dispatcher, requested "X" does not exist` → Dispatcher renamed/removed
   - `invalid field X: missing a value` → Syntax of that directive changed
   - `source= globbing error: found no match` → Referenced file missing

3. **Check Hyprland version**
   ```bash
   hyprctl version | head -3
   ```

4. **Find where config files come from**
   ```bash
   readlink -f ~/.config/hypr/hyprland/general.conf
   # Often a nix store path from home-manager or a flake
   ```

## Hyprland 0.54.0+ Syntax Changes

### `layerrule` — separator changed from comma to space

| Old syntax | New syntax |
|------------|------------|
| `layerrule = blur, notifications` | `layerrule = blur notifications` |
| `layerrule = noanim, walker` | `layerrule = animation none walker` |
| `layerrule = blurpopups, quickshell:.*` | `layerrule = blur popups quickshell:.*` |
| `layerrule = xray 1, .*` | `layerrule = xray 1 .*` |
| `layerrule = ignorealpha 0.6, bar` | `layerrule = blur ignorealpha 0.6 bar` |
| `layerrule = ignorezero, gtk-layer-shell` | `layerrule = blur ignorezero gtk-layer-shell` |
| `layerrule = animation slide left, sideleft.*` | `layerrule = animation slide left sideleft.*` |

**Critical rule:** `ignorealpha` and `ignorezero` can NO LONGER be standalone rules. They must be merged into a `blur` rule. If a layer previously had separate `blur` + `ignorealpha` lines, merge them into one `blur ignorealpha 0.6 layer` line.

### `windowrulev2` — deprecated but still required

In 0.54.0, `windowrulev2` prints `deprecated` warnings but remains the ONLY keyword that accepts conditional syntax (`class:regex`, `title:regex`, etc.). `windowrule` does NOT support conditions in this version.

**Do NOT bulk-replace `windowrulev2` → `windowrule`.** Keep `windowrulev2` and accept the warnings.

### `splitratio` dispatcher removed

Replace:
```conf
binde = Super, Semicolon, splitratio, -0.1
```
With:
```conf
binde = Super, Semicolon, layoutmsg, splitratio -0.1
```

### `gestures` block — some options removed

Removed in 0.54.0:
- `gestures:workspace_swipe`
- `gestures:workspace_swipe_fingers`
- `gestures:workspace_swipe_min_fingers`

Other gesture options (distance, cancel_ratio, etc.) remain valid.

### `decoration:shadow` — `ignore_window` removed

Remove `decoration:shadow:ignore_window = true`.

### `misc` block — several options removed

Removed in 0.54.0:
- `misc:vfr`
- `misc:vrr`
- `misc:new_window_takes_over_fullscreen`
- `misc:session_lock_xray`

### `plugin:hyprexpo` — options renamed or removed

If hyprexpo plugin is not loaded, the entire `plugin { hyprexpo { ... } }` block should be removed to avoid `Invalid value` errors.

## NixOS Override Strategy

When configs come from a flake (e.g., end-4-nixos) as nix store symlinks, do NOT edit them in place. Instead, create corrected files and override via `home.nix`:

```nix
xdg.configFile."hypr/hyprland/general.conf" = lib.mkForce {
  source = ./hyprland-compat/general.conf;
};
xdg.configFile."hypr/hyprland/rules.conf" = lib.mkForce {
  source = ./hyprland-compat/rules.conf;
};
xdg.configFile."hypr/hyprland/keybinds.conf" = lib.mkForce {
  source = ./hyprland-compat/keybinds.conf;
};
xdg.configFile."hypr/hyprland/colors.conf" = lib.mkForce {
  text = "";
};
```

Then rebuild:
```bash
sudo nixos-rebuild switch --flake .#nixos
```

## Runtime UI Artifacts: Mysterious Popups / Flickering Squares

When the user reports "small squares popping up in the middle of the screen" or similar visual artifacts that are NOT config error banners, use this isolation workflow.

### 1. Distinguish Layer Surfaces vs Regular Windows

Layer-shell clients (notifications, OSDs, launchers, bars) do **not** appear in `hyprctl clients`. Inspect them separately:

```bash
# List all layer surfaces (per monitor)
hyprctl layers

# Watch for changes over time
watch -n 0.5 'hyprctl layers | grep namespace'
```

If a layer is repeatedly appearing and disappearing, note its `namespace` and `pid`.

### 2. Check for Conflicting Compositor Instances

Multiple instances of the same compositor UI framework (e.g., Quickshell) will fight over the same layer namespaces, causing repeated OSD/notification flashes or complete hang/freeze:

```bash
# Count quickshell / waybar / ags instances
ps aux | grep quickshell | grep -v grep
```

**Kill duplicates carefully** — do NOT use `killall -USR1` on quickshell, it kills the process instead of reloading:
```bash
# Kill by PID (keep the main one on tty1)
kill <extra_pid>

# Or kill all and restart fresh:
killall quickshell && sleep 1 && nohup qs -c ii > /tmp/qs-ii.log 2>&1 &
```

**Why `killall -USR1` is wrong for quickshell:** Unlike Hyprland (where USR1 triggers config reload), quickshell's USR1 handler exits the process. Always use SIGTERM or SIGKILL to stop quickshell, then restart it manually.

### 3. Check for Repeated Process Spawning

Look in user journal for a process being launched repeatedly (often by a broken keybind or looping script):

```bash
journalctl --user -n 100 --no-pager | grep -E "(fuzzel|wofi|rofi|dunst|mako)" | tail -20
```

If you see rapid-fire identical lines like `fuzzel[PID]: icon theme not found` with different PIDs, something is spawning that launcher in a loop. Common causes:
- A stuck/broken keyboard shortcut
- A systemd user service in a crash-restart loop
- A shell loop running in a detached terminal

### 4. Process-of-Elimination for Remaining Suspects

If layers and windows are both stable, the artifact may come from:
- **Chrome/Electron notifications** (kill Chrome to test)
- **fcitx5 candidate panel** (can flicker if Wayland frontend is misconfigured)
- **GPU/renderer bug** (check if it persists across apps; may need Hyprland restart)

Kill suspects one by one and ask the user to confirm after each:
```bash
killall chrome        # Test browser notifications
killall fcitx5        # Test IME panel
hyprctl dispatch exit # Nuclear option: restart Hyprland
```

### 5. Inspect Actual Window List

```bash
hyprctl clients -j | jq -r '.[] | "\(.class): \(.title) [\(.size.w)x\(.size.h)]"'
```

If the artifact does NOT appear here OR in `hyprctl layers`, it is likely:
- A tooltip/popup rendered by an application internally
- A GPU/compositor rendering bug

## Verifying Interactive UI Elements (Waybar on-click, etc.)

When the user says "clicking X does nothing" or "no window pops up", do not assume the config is correct just because `nixos-rebuild switch` succeeded. You must verify end-to-end.

### Pitfall: home-manager profile symlink not updated

After `nixos-rebuild switch`, the systemd service `home-manager-lingfeng.service` may activate a **new generation** while the nix profile symlink `~/.local/state/nix/profiles/home-manager` still points to an **old generation**. Running services (like waybar) read their PATH from the old profile, so binaries newly added to `home.packages` are missing.

**Check:**
```bash
# The profile symlink target
readlink ~/.local/state/nix/profiles/home-manager

# The actual generation the systemd service ran
systemctl status home-manager-lingfeng.service | grep ExecStart

# Whether the binary exists in the profile
ls ~/.local/state/nix/profiles/home-manager/home-path/bin/<binary>
```

**Fix:**
```bash
# Manually update the profile link to the latest generation
ln -sfn /nix/store/...-home-manager-generation ~/.local/state/nix/profiles/home-manager-69-link
ln -sfn home-manager-69-link ~/.local/state/nix/profiles/home-manager
# Then restart the affected service
systemctl --user restart waybar
```

### Automated click testing with `wlrctl`

On wlroots-based compositors (Hyprland, Sway), `wlrctl` can simulate pointer events without needing root or `ydotoold` (which often fails to create virtual devices on NixOS).

**Important:** `wlrctl pointer move` uses **relative displacement**, not absolute coordinates.

```bash
# Move cursor to top-left corner first
wlrctl pointer move -9999 -9999
# Then move to target position
wlrctl pointer move 2380 20
wlrctl pointer click
```

**End-to-end verification pattern:**
```bash
# 1. Set waybar on-click to a test marker
# "on-click": "touch /tmp/waybar_click_test"

# 2. Simulate click
wlrctl pointer move -9999 -9999
wlrctl pointer move 2380 20
wlrctl pointer click

# 3. Check if marker was created
ls /tmp/waybar_click_test

# 4. Restore real command and verify window appears
# "on-click": "kcmshell6 kcm_networkmanagement"
wlrctl pointer move -9999 -9999
wlrctl pointer move 2380 20
wlrctl pointer click
sleep 2
hyprctl clients | grep "class:.*kcm"
```

### End-4 upstream best practice: network management GUI

End-4/illogical-impulse upstream binds network clicks to KDE's network KCM, not `nm-applet` or rofi scripts:

```nix
# packages needed
pkgs.kdePackages.kcmutils   # provides kcmshell6
pkgs.kdePackages.plasma-nm  # provides kcm_networkmanagement module

# waybar on-click
"on-click" = "${pkgs.kdePackages.kcmutils}/bin/kcmshell6 kcm_networkmanagement"
```

This produces a full native Qt/KDE network settings window (WiFi scan, connect, VPN, wired) and is the upstream-endorsed approach for this rice.

### Critical: KDE KCM modules fail with empty window in minimal Hyprland

When `kcmshell6 kcm_networkmanagement` opens but shows a completely empty/blank window, the QML engine cannot find runtime dependencies. `kcmshell6` is a closed Nix package; its wrapper only knows its own build-time deps. KCM modules loaded at runtime (like `plasma-nm`) pull in additional QML modules that are NOT in `kcmshell6`'s wrapper.

**Diagnosis via journalctl (not stderr)**

KDE apps log QML errors to the systemd journal, not stderr. Redirecting `2>&1` often captures nothing.

```bash
journalctl --user -b | grep -i "kcmshell\|qml\|module\|unavailable"
```

Typical errors:
```
module "org.kde.plasma.components" is not installed
module "org.kde.ksvg" is not installed
Could not locate plasma theme "default" in plasma/desktoptheme/
```

**Dependency chain**

| Missing QML module | Providing package | Path variable needed |
|--------------------|-------------------|----------------------|
| `org.kde.plasma.components` | `kdePackages.libplasma` | `QML2_IMPORT_PATH`, `QT_PLUGIN_PATH`, `XDG_DATA_DIRS` |
| `org.kde.ksvg` | `kdePackages.ksvg` | `QML2_IMPORT_PATH`, `QT_PLUGIN_PATH` |
| `plasma/desktoptheme/default` | `kdePackages.libplasma` | `XDG_DATA_DIRS` |

**Fix: wrapper script with explicit Qt paths**

Do NOT rely on `home.packages` alone; `kcmshell6`'s wrapper won't see them. Create a Nix wrapper:

```nix
{ pkgs, ... }:
let
  kcmNetworkWrapper = pkgs.writeShellScriptBin "kcm-network" ''
    export QML2_IMPORT_PATH=${pkgs.kdePackages.plasma-nm}/lib/qt-6/qml:\
${pkgs.kdePackages.libplasma}/lib/qt-6/qml:\
${pkgs.kdePackages.ksvg}/lib/qt-6/qml:$QML2_IMPORT_PATH
    export QT_PLUGIN_PATH=${pkgs.kdePackages.plasma-nm}/lib/qt-6/plugins:\
${pkgs.kdePackages.libplasma}/lib/qt-6/plugins:\
${pkgs.kdePackages.ksvg}/lib/qt-6/plugins:$QT_PLUGIN_PATH
    export XDG_DATA_DIRS=${pkgs.kdePackages.plasma-nm}/share:\
${pkgs.kdePackages.libplasma}/share:$XDG_DATA_DIRS
    ${pkgs.kdePackages.kcmutils}/bin/kcmshell6 kcm_networkmanagement
  '';
in
{
  home.packages = [
    pkgs.kdePackages.kcmutils
    pkgs.kdePackages.plasma-nm
    pkgs.kdePackages.libplasma
    pkgs.kdePackages.ksvg
    kcmNetworkWrapper
  ];

  # waybar config
  network = {
    "on-click" = "${kcmNetworkWrapper}/bin/kcm-network";
  };
}
```

Then rebuild and restart waybar. Verify with `journalctl` that QML module errors disappear.

## Verification After Fix

1. Reload config (does not clear old startup errors from the session):
   ```bash
   hyprctl reload
   ```
2. Check that NO **new** errors appear:
   ```bash
   hyprctl configerrors 2>&1 | grep -c "deprecated"
   hyprctl configerrors 2>&1 | grep -c "does not exist"
   hyprctl configerrors 2>&1 | grep -c "invalid field"
   ```
3. To fully verify, **log out and log back in** (or reboot). Old errors from the previous startup are cached in the session and won't disappear until restart.

## Advanced: Upstream Source Stale Detection

When a NixOS home-manager module (e.g., `end-4-nixos`) wraps upstream dotfiles, the real problem is often that the module references an outdated fork while the upstream has moved on.

### Diagnosis

Compare commit dates between the system's locked version and the module's locked version:

```bash
# System's Hyprland version
hyprctl version | grep Date

# Module's locked dotfiles version
grep -B2 -A10 '"repo": "dots-hyprland"' /etc/nixos/end-4-nixos/flake.lock | grep '"date"'

# Upstream latest
curl -s https://api.github.com/repos/end-4/dots-hyprland/commits?per_page=1 | grep '"date"'
```

If the module's dotfiles are months behind upstream, **switch to upstream** instead of patching around stale configs.

### Fixing stale upstream references

1. **Check upstream file structure changes**: Newer versions may move configs into a `dots/` subdirectory (e.g., `.config/hypr/...` → `dots/.config/hypr/...`). Verify with:
   ```bash
   ls /nix/store/...-source/
   ```

2. **Override the submodule input** in system `flake.nix` (cleaner than modifying the submodule itself):
   ```nix
   illogical-impulse = {
     url = "path:./end-4-nixos";
     inputs.nixpkgs.follows = "nixpkgs";
     inputs.hyprland.follows = "hyprland";
     inputs.illogical-impulse-dotfiles = {
       url = "github:end-4/dots-hyprland";
       flake = false;
     };
   };
   ```

3. **Fix paths in the NixOS module** (`end-4-nixos/modules/hyprland.nix`):
   ```nix
   xdg.configFile."hypr/hyprland/general.conf".source =
     "${illogical-impulse-dotfiles}/dots/.config/hypr/hyprland/general.conf";
   ```

4. **Add missing files**: If upstream added new config files (e.g., `colors.conf`), add them to the module.

## Alternative: Downgrade Hyprland

If the dotfiles are complex and upstream hasn't updated, consider locking Hyprland to the revision the dotfiles were written for:

```nix
# flake.nix
hyprland.url = "github:hyprwm/Hyprland?rev=584b844aaf72cd7ea6851117f1bd598b7467ffc1";
```

This avoids all compatibility issues but loses upstream bug fixes.