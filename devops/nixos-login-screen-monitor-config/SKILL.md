---
name: nixos-login-screen-monitor-config
description: >
  Configure NixOS display manager (SDDM) monitor outputs separately from the
  desktop environment (e.g. Hyprland). Solves the common problem where the
  login screen appears on the laptop built-in screen instead of the external
  monitor, even though the DE is configured to use the external monitor only.
triggers:
  - Login screen shows on wrong monitor after reboot
  - SDDM login appears on laptop screen instead of external display
  - Need to open laptop lid to see login screen despite external monitor being primary
  - Display manager ignores Hyprland / home.nix monitor configuration
  - NixOS multi-monitor login screen configuration
  - "重启时还要打开笔记本登陆"

---

## Problem

On NixOS with a laptop + external monitor setup, users often configure their
desktop environment (e.g. Hyprland in `home.nix`) to disable the built-in
screen (`eDP-1`) and use only the external monitor (`HDMI-A-1`).

However, **the display manager (SDDM) runs in its own session and does NOT
read the desktop environment's monitor configuration**. After reboot, the
login screen still appears on the laptop screen, forcing the user to open
the laptop lid to log in.

## Root Cause

- `home.nix` monitor settings (e.g. Hyprland's `monitor = [...]`) only apply
  **after** logging into the desktop session.
- SDDM Wayland mode uses its own Wayland compositor (e.g. kwin_wayland) and
  has very limited monitor control capabilities.
- SDDM cannot inherit Hyprland monitor rules.

## Solution: Use X11 SDDM + xrandr setupCommands

Switch SDDM to X11 mode and use `services.xserver.displayManager.setupCommands`
to configure monitors before the login window appears.

### 1. Edit `/etc/nixos/configuration.nix`

```nix
# Display manager
services.displayManager.sddm.enable = true;
services.xserver.enable = true;  # REQUIRED for X11 SDDM

# Disable Wayland mode for SDDM (comment out or remove)
# services.displayManager.sddm.wayland.enable = true;

# Configure login screen monitors: disable laptop screen, use external only
services.xserver.displayManager.setupCommands = ''
  ${pkgs.xorg.xrandr}/bin/xrandr | grep -q "HDMI-A-1 connected" && \
    ${pkgs.xorg.xrandr}/bin/xrandr --output eDP-1 --off --output HDMI-A-1 --auto --primary
  ${pkgs.xorg.xrandr}/bin/xrandr | grep -q "HDMI-1 connected" && \
    ${pkgs.xorg.xrandr}/bin/xrandr --output eDP-1 --off --output HDMI-1 --auto --primary
'';
```

**Notes:**
- Use `''` (two single quotes) for Nix indented strings, not `'`.
- `services.xserver.enable = true;` is **mandatory** when using SDDM X11 mode.
- The desktop environment (Hyprland) remains Wayland; only the login screen
  uses X11.
- Monitor names may differ between Wayland (`HDMI-A-1`) and X11 (`HDMI-1` or
  `HDMI-A-1`). Add fallbacks as needed.

### 2. Rebuild

```bash
sudo nixos-rebuild switch --flake /etc/nixos
```

### 3. Reboot

The display manager service does **not** auto-restart after rebuild.
A full reboot is required to see the login screen on the correct monitor.

## Verification After Reboot

- Login screen should appear on the external monitor.
- Laptop built-in screen (`eDP-1`) should remain off during login.
- After logging in, Hyprland should still use the external monitor as
  configured in `home.nix`.

## Pitfalls

1. **Forgetting `services.xserver.enable = true`** — causes Nix evaluation
   error: "SDDM requires either services.xserver.enable or
   services.displayManager.sddm.wayland.enable to be true".

2. **Using single quotes `'` instead of double single quotes `''`** for Nix
   indented strings — causes syntax error at evaluation time.

3. **Wrong monitor names in X11** — X11 may use `HDMI-1` while Wayland uses
   `HDMI-A-1`. Always check with `xrandr` in an X11 session if unsure.

4. **Expecting auto-restart** — `display-manager.service` is NOT restarted
   automatically by `nixos-rebuild switch`. You must reboot.

## Alternative Approaches Considered

- **Keep SDDM Wayland + configure its compositor**: Not practical. SDDM
  Wayland mode has very limited monitor configuration options and does not
  expose xrandr-like control.
- **Configure kernel/firmware to prefer external output at boot**: Overly
  complex and hardware-dependent; not a reliable general solution.
- **Use greetd instead of SDDM**: greetd is simpler but still requires a
  compositor (e.g. cage, sway) for multi-monitor control, which introduces
  similar configuration complexity.

The X11 SDDM + `setupCommands` approach is the most robust and well-documented
method for NixOS.