---
name: nixos-wayland-portal-debug
title: Debug NixOS XDG Desktop Portal Issues on Wayland
description: Systematically diagnose and fix missing XDG Desktop Portal interfaces (FileChooser, ScreenCast, etc.) on NixOS with Wayland compositors like Hyprland, Sway, or river.
triggers:
  - NixOS user reports file chooser not working in Flatpak or native apps
  - No such interface on object /org/freedesktop/portal/desktop errors
  - Missing portal interfaces like FileChooser or ScreenCast
  - xdg-desktop-portal issues on Hyprland Sway or river
---

# NixOS Wayland Portal Debugging

## Quick Diagnosis (run these in order)

### 1. Check portal services are running
```bash
systemctl --user status xdg-desktop-portal
systemctl --user status xdg-desktop-portal-gtk
systemctl --user status xdg-desktop-portal-hyprland  # or -wlr, -kde, etc.
```

### 2. Verify desktop environment detection
```bash
echo "XDG_CURRENT_DESKTOP=$XDG_CURRENT_DESKTOP"
echo "XDG_SESSION_TYPE=$XDG_SESSION_TYPE"
```
Should show your compositor (e.g., `Hyprland`) and `wayland`.

### 3. Introspect what interfaces are actually exposed
```bash
dbus-send --session --dest=org.freedesktop.portal.Desktop \
  --type=method_call --print-reply /org/freedesktop/portal/desktop \
  org.freedesktop.DBus.Introspectable.Introspect 2>&1 | \
  grep 'interface name' | sed 's/.*name="\([^"]*\)".*/\1/'
```
If `org.freedesktop.portal.FileChooser` is missing, the backend providing it is not loaded.

### 4. Check which portals xdg-desktop-portal can see
```bash
# On NixOS, portals are discovered via NIX_XDG_DESKTOP_PORTAL_DIR
echo $NIX_XDG_DESKTOP_PORTAL_DIR
ls -la $NIX_XDG_DESKTOP_PORTAL_DIR/
cat $NIX_XDG_DESKTOP_PORTAL_DIR/*.portal
```

Also check the system-level paths:
```bash
ls -la /run/current-system/sw/share/xdg-desktop-portal/portals/
cat /run/current-system/sw/share/xdg-desktop-portal/portals.conf 2>/dev/null
cat ~/.config/xdg-desktop-portal/portals.conf 2>/dev/null
```

### 5. Check if DBus backend names are registered
```bash
dbus-send --session --dest=org.freedesktop.DBus --type=method_call \
  --print-reply /org/freedesktop/DBus org.freedesktop.DBus.ListNames | \
  grep portal
```

## Common Root Causes on NixOS

### Cause A: xdg.portal not configured in configuration.nix
The most common issue on NixOS + Hyprland. The Hyprland home-manager module may only set up `xdg-desktop-portal-hyprland` (screenshot/screencast), but `xdg-desktop-portal-gtk` (FileChooser, AppChooser, etc.) must be added explicitly.

**Fix** in `/etc/nixos/configuration.nix`:
```nix
xdg.portal = {
  enable = true;
  extraPortals = [ pkgs.xdg-desktop-portal-gtk ];
  configPackages = [ pkgs.xdg-desktop-portal-hyprland ];  # or -wlr
};
```
Then rebuild:
```bash
sudo nixos-rebuild switch --flake /etc/nixos
```

### Cause B: NIX_XDG_DESKTOP_PORTAL_DIR points to home-manager path missing gtk portal
If home-manager (especially the Hyprland home-manager module) configures `xdg.portal` incompletely, `NIX_XDG_DESKTOP_PORTAL_DIR` may point to `/etc/profiles/per-user/USER/share/xdg-desktop-portal/portals/` which **only contains the compositor's portal** (e.g., `hyprland.portal`) and not `gtk.portal`.

Even if NixOS system-level `xdg.portal.extraPortals` includes `xdg-desktop-portal-gtk`, the `xdg-desktop-portal` main service respects `NIX_XDG_DESKTOP_PORTAL_DIR` first, so it will never see the system-level `gtk.portal`.

**Diagnosis**:
```bash
echo $NIX_XDG_DESKTOP_PORTAL_DIR
ls -la $NIX_XDG_DESKTOP_PORTAL_DIR/
# If only hyprland.portal (or -wlr) appears here, this is the cause
```

**Fix for NixOS + home-manager setups**:
You must configure `xdg.portal` in **both** `configuration.nix` (system level) and `home.nix` (user level):

In `/etc/nixos/configuration.nix`:
```nix
xdg.portal = {
  enable = true;
  extraPortals = [ pkgs.xdg-desktop-portal-gtk ];
  configPackages = [ pkgs.xdg-desktop-portal-hyprland ];  # keep here only
};
```

In `/etc/nixos/home.nix`:
```nix
xdg.portal = {
  enable = true;
  extraPortals = [ pkgs.xdg-desktop-portal-gtk ];
  # Do NOT repeat configPackages here to avoid buildEnv conflicts
};
```

**Why**: The home-manager `xdg.portal` module links portals into the user profile directory. If you only configure at the NixOS level, home-manager's Hyprland module may still generate a user profile portal dir that lacks `gtk.portal`.

**BuildEnv conflict pitfall**: If both `configuration.nix` and `home.nix` set `configPackages = [ pkgs.xdg-desktop-portal-hyprland ]`, `home-manager-path` build will fail with "two given paths contain a conflicting subpath" because NixOS and home-manager may pull in different store-path versions of the same package. Keep `configPackages` only in `configuration.nix`.

**Temporary workaround** (if you cannot rebuild immediately):
Create a systemd user override to force the system portal directory:
```bash
mkdir -p ~/.config/systemd/user/xdg-desktop-portal.service.d
cat > ~/.config/systemd/user/xdg-desktop-portal.service.d/portal-dir.conf << 'EOF'
[Service]
Environment=NIX_XDG_DESKTOP_PORTAL_DIR=/run/current-system/sw/share/xdg-desktop-portal/portals
EOF
systemctl --user daemon-reload
systemctl --user restart xdg-desktop-portal
```

### Cause C: configPackages mismatch
If `xdg.portal.configPackages` does not include the compositor's portal package, the `hyprland-portals.conf` (or `wlr-portals.conf`) won't be installed, and xdg-desktop-portal won't know which backend to use for which interface.

**Fix**: Include the compositor portal in `configPackages`:
```nix
xdg.portal.configPackages = [ pkgs.xdg-desktop-portal-hyprland ];
```

### Cause D: Portal service crashed or inactive
```bash
systemctl --user restart xdg-desktop-portal
systemctl --user restart xdg-desktop-portal-gtk
systemctl --user restart xdg-desktop-portal-hyprland
```

## Verification After Fix

1. Rebuild NixOS configuration
2. **Reboot or re-login** (portal services are session-scoped and env vars are cached)
3. Re-run the introspection command from step 3 — `org.freedesktop.portal.FileChooser` should appear
4. Test with: `busctl --user call org.freedesktop.portal.Desktop /org/freedesktop/portal/desktop org.freedesktop.DBus.Introspectable Introspect | grep -i filechooser`

## Pitfalls

- Do NOT manually edit `/etc/profiles/per-user/...` or `/run/current-system/sw/...` — these are Nix store symlinks managed by the NixOS module system. Always edit `configuration.nix`/`home.nix` and rebuild.
- `xdg-desktop-portal-gtk` and `xdg-desktop-portal-gnome` are different packages. On non-GNOME Wayland compositors, use `-gtk`.
- Some apps cache portal availability at startup. Test with a freshly launched app after fixing.
- The `config.common.default = "*";` setting can be used as a fallback wildcard but explicit `configPackages` is preferred for compositor-specific configs.
- **home-manager Hyprland module interaction**: The Hyprland home-manager module may silently set up `xdg.portal` for the user profile. If you only configure `xdg.portal` in `configuration.nix`, the user's `NIX_XDG_DESKTOP_PORTAL_DIR` may still point to a home-manager-generated directory that lacks `gtk.portal`. You must also add `xdg-desktop-portal-gtk` to `xdg.portal.extraPortals` in `home.nix`.
- **buildEnv conflict**: Never set the same `configPackages` in both `configuration.nix` and `home.nix` — this causes a conflicting-subpath build failure because NixOS and home-manager may pull different store-path versions of the same portal package.
