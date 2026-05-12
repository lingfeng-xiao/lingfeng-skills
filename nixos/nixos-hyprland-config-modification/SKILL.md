---
name: nixos-hyprland-config-modification
description: Modify Hyprland configuration on NixOS when the config file is read-only (home-manager managed).
triggers:
  - User wants to add Hyprland keybindings, settings, or packages on NixOS
  - ~/.config/hypr/hyprland.conf is read-only or symlinked to nix store
  - Need to change Hyprland settings permanently on a NixOS + home-manager setup
---

# NixOS Hyprland Config Modification (Home-Manager Managed)

## Problem
On NixOS with home-manager, `~/.config/hypr/hyprland.conf` is a read-only symlink into the Nix store. Direct edits fail with "Read-only file system". The actual source of truth is typically `/etc/nixos/home.nix` (or a flake-imported home module).

## Workflow

### 1. Apply change temporarily (instant, no rebuild)
Use `hyprctl` to test the change immediately without touching files:
```bash
hyprctl keyword bind "MOD, KEY, exec, command"
```
Example:
```bash
hyprctl keyword bind "CTRL ALT, A, exec, grim -g \$(slurp) - | wl-copy"
```

### 2. Find the source file
Locate the home-manager module that generates Hyprland config:
```bash
ls -la /etc/nixos/
# Look for home.nix or a modules/ directory containing Hyprland settings
```

### 3. Edit the source
Use `sudo` to modify the Nix expression. Typical structure:
```nix
wayland.windowManager.hyprland = {
  enable = true;
  settings = {
    bind = [
      # add entries here
      "CTRL ALT, A, exec, grim -g $(slurp) - | wl-copy"
    ];
  };
};
```

If adding packages (e.g. `grim`, `slurp`), add them to:
```nix
home.packages = with pkgs; [
  grim
  slurp
  wl-clipboard
];
```

### 4. Rebuild to persist
```bash
sudo nixos-rebuild switch
```

## Hyprland 0.47+ / 0.54+ Breaking Changes

### windowrule syntax overhaul
In Hyprland 0.47+ (and fully enforced in 0.54+), `windowrulev2` has been removed. All v2 syntax now lives under `windowrule`, but the **prop names changed**:

| Old syntax | New syntax |
|---|---|
| `windowrulev2 = workspace 9 silent, class:^(...)$` | `windowrule = match:class ^(...)$, workspace 9 silent` |
| `class:^(...)$` | `match:class ^(...)$` |
| `title:^(...)$` | `match:title ^(...)$` |
| `initialClass:^(...)$` | `match:initial_class ^(...)$` |
| `initialTitle:^(...)$` | `match:initial_title ^(...)$` |
| `workspace:...` | `match:workspace ...` |

Key points:
- Props and effects can be in **any order** separated by commas.
- The `match:` prefix is mandatory for all matching props.
- `workspace 9 silent` is still a valid effect; `silent` goes after the workspace number.

Example in `home.nix`:
```nix
windowrule = [
  "match:class ^(com.tencent.wechat|WeChat|wechat-uos)$, workspace 9 silent"
];
```

### Debug config errors via screenshot
If the user reports a red error banner in the top bar but cannot paste the text:
1. Full-screen screenshot: `grim /tmp/screen.png`
2. Analyze with vision to read the error text.
3. Common top-bar errors from Hyprland:
   - `windowrulev2 is deprecated` → migrate to new `windowrule` syntax.
   - `invalid field class:...: missing a value` → forgot `match:` prefix.

## Integrating a Third-Party Hyprland Rice on NixOS

When a user wants to adopt a popular community rice (not just tweak their own config), the workflow is different from simple `home.nix` edits. Below is the proven path for **end-4/dots-hyprland**, which is the highest-starred option; the pattern generalizes to other rices that have community NixOS ports.

### Step 1: Research and choose

| Rank | Repo | Stars | NixOS Support | Notes |
|---|---|---|---|---|
| 1 | [end-4/dots-hyprland](https://github.com/end-4/dots-hyprland) | ~14k | Community port: `xBLACKICEx/end-4-dots-hyprland-nixos` | Material Design 3 + Quickshell (replaces waybar), dynamic wallpaper theming, Overview, AI sidebar. Largest config change. |
| 2 | [caelestia-dots/shell](https://github.com/caelestia-dots/shell) | ~9k | Via [anotherhadi/nixy](https://github.com/anotherhadi/nixy) | "No waybar" custom shell, sleek minimal. Nixy wraps it as a NixOS-native modular config. Less disruptive. |
| 3 | [prasanthrangan/hyprdots](https://github.com/prasanthrangan/hyprdots) | ~8.5k | **Deprecated** | **Do NOT recommend for new installs.** |
| 4 | [mylinuxforwork/dotfiles](https://github.com/mylinuxforwork/dotfiles) | ~4.6k | No native support | ML4W OS with Live ISO. Arch/Fedora/openSuse only. |

**Decision tree:**
- User wants maximum visual impact + highest stars → **end-4**
- User wants NixOS-native, modular, minimal disruption → **nixy/caelestia**

### Step 2: Add the community port as a flake input

Example for end-4:
```nix
# flake.nix
inputs = {
  illogical-impulse = {
    url = "github:xBLACKICEx/end-4-dots-hyprland-nixos";
    inputs.nixpkgs.follows = "nixpkgs";
    inputs.hyprland.follows = "hyprland";  # unify with your existing hyprland input
  };
};

outputs = { self, nixpkgs, home-manager, hyprland, illogical-impulse, ... }@inputs:
  # pass illogical-impulse through specialArgs so home.nix can import its module
```

### Step 3: Import the module in home.nix and enable

```nix
# home.nix
{ config, pkgs, inputs, lib, ... }:

{
  imports = [
    inputs.hyprland.homeManagerModules.default
    inputs.illogical-impulse.homeManagerModules.default
  ];

  # Remove your old wayland.windowManager.hyprland block entirely.
  # The port takes over Hyprland configuration.

  illogical-impulse = {
    enable = true;
    hyprland = {
      package = inputs.hyprland.packages.${pkgs.system}.hyprland;
      xdgPortalPackage = pkgs.xdg-desktop-portal-hyprland;
      ozoneWayland.enable = true;
      monitor = [
        "HDMI-A-1,preferred,auto,1"
        "eDP-1,disable"
      ];
    };
    dotfiles = {
      kitty.enable = true;
      fish.enable = true;
    };
  };
}
```

**Critical:** The port's module sets `wayland.windowManager.hyprland` internally. If you also define it in `home.nix`, Nix will error with "option defined multiple times". Remove the old block completely.

### Step 4: Inject your custom config via `hypr/custom/`

end-4 sources these files last, so they override defaults:
- `~/.config/hypr/custom/env.conf`
- `~/.config/hypr/custom/execs.conf`
- `~/.config/hypr/custom/general.conf`
- `~/.config/hypr/custom/rules.conf`
- `~/.config/hypr/custom/keybinds.conf`

The port copies a default `custom/` directory from upstream dotfiles. To replace it with your own, use `lib.mkForce` in `home.nix`:

```nix
xdg.configFile."hypr/custom" = lib.mkForce {
  source = ./hypr-custom;  # local dir next to home.nix
  recursive = true;
};
```

Then create `/etc/nixos/hypr-custom/env.conf`, `rules.conf`, etc. with your settings (input method env vars, WeChat window rules, extra keybinds).

### Step 5: Build, fix bugs, switch

```bash
sudo nixos-rebuild switch --flake /etc/nixos#nixos
```

### Known bugs in the end-4 NixOS port (and fixes)

| Bug | Symptom | Fix |
|---|---|---|
| Undefined `system` in `packages.nix` | Build error `undefined variable 'system'` | Edit `modules/packages.nix`, change `"${system}"` to `"${pkgs.system}"` |
| Quickshell compile failure | `Qt6::WaylandClientPrivate not found` during CMake | Edit `modules/quickshell.nix`, replace `inputs.quickshell.packages.${pkgs.system}.default` with `pkgs.quickshell` (nixpkgs pre-built 0.2.1+) |
| Quickshell runtime QML import failures | Top-left flood of `Type X unavailable` errors; `module "Qt5Compat.GraphicalEffects" is not installed`; `module "QtPositioning" is not installed` | The nixpkgs `pkgs.quickshell` binary wrapper does not propagate all Qt6 QML paths needed by end-4. Add this to `home.nix` `home.sessionVariables`: `QML_IMPORT_PATH = lib.makeSearchPath "lib/qt-6/qml" (with pkgs.kdePackages; [ qtdeclarative qtpositioning qtquicktimeline qtmultimedia qtsensors qtvirtualkeyboard qtwayland qt5compat ]);` |
| Gammastep crash-loop spam | Notification spam `GeoClue2 provider is not installed!` every few seconds | Enable `services.geoclue2.enable = true;` in `configuration.nix` |

Because these bugs are in the community port (not in Nixpkgs), the most practical fix is to clone the port locally, patch it, and reference it via `path:` input:
```nix
illogical-impulse.url = "path:./end-4-nixos";
```

### Post-install notes

- end-4 replaces **waybar with Quickshell**. Your old waybar config is ignored.
- Keybindings change completely. end-4 uses Super+Enter for terminal, Super+Tab for Overview, Super+A for left sidebar, etc. Your `custom/keybinds.conf` can add backward-compatible binds.
- The user must **log out and back in** to see the new shell; a simple Hyprland reload is not enough because waybar→quickshell is a service swap.
- Backup the original `/etc/nixos/` before starting. The port makes large changes.

## Integrating Systemd User Services in Home-Manager

When you need a background service (e.g. a messaging gateway, file sync, or agent daemon) that runs as the user, define it inside the same home-manager module that manages Hyprland:

```nix
systemd.user.services.my-service = {
  Unit = {
    Description = "My background service";
    PartOf = [ "graphical-session.target" ];
    After = [ "graphical-session.target" "network-online.target" ];
  };
  Service = {
    Type = "simple";
    ExecStart = "${config.home.homeDirectory}/.local/bin/my-service";
    Restart = "on-failure";
    RestartSec = 5;
    Slice = "session.slice";
  };
  Install = {
    WantedBy = [ "default.target" ];
  };
};
```

Key points:
- `ExecStart` must be an absolute path. If the binary lives outside the Nix store (e.g. in `~/.local/bin` or a venv), use `${config.home.homeDirectory}` to construct the path.
- `PartOf = [ "graphical-session.target" ]` ensures the service stops when the graphical session ends.
- `Restart = "on-failure"` with `RestartSec` provides automatic recovery.

## Home-Manager Activation Failures

### "Existing file ... would be clobbered"
If `nixos-rebuild switch` reports that `home-manager-lingfeng.service` failed with a message like:
```
Existing file '/home/lingfeng/.config/systemd/user/default.target.wants/my-service.service' would be clobbered
```

This means a systemd user service file already exists at that path (likely created manually earlier) and home-manager refuses to overwrite it.

**Fix:**
```bash
rm -f ~/.config/systemd/user/default.target.wants/my-service.service
rm -f ~/.config/systemd/user/my-service.service
# Then re-run rebuild
sudo nixos-rebuild switch --flake ~/nix-config#nixos
```

### HOME environment variable pollution
If home-manager activation fails with:
```
HOME is "/home/lingfeng/.hermes/home", expected "/home/lingfeng"
```

Some tools or agent wrappers modify the `HOME` environment variable. The home-manager activation script sanity-checks `HOME` and aborts if it does not match the expected path.

**Fix:** Explicitly set `HOME` when running rebuild:
```bash
HOME=/home/lingfeng sudo nixos-rebuild switch --flake /home/lingfeng/nix-config#nixos
```

### Nix Flake "not tracked by Git"
If `nixos-rebuild switch` fails with:
```
error: Path '...' in the repository is not tracked by Git.
To make it visible to Nix, run: git -C "/path" add "file"
```

Nix flakes can only access files that are tracked by Git. Any newly created file (e.g. a new Hyprland keybind fragment) must be added before the flake can see it:
```bash
cd /home/lingfeng/nix-config
git add path/to/new-file
```

## Waybar Module Interactions (on-click, menus, pop-ups)

When the user clicks a Waybar icon (WiFi, Bluetooth, battery, etc.) and nothing happens, the cause is almost always a missing `on-click` binding in the Waybar config.

### Diagnosis
1. Find the actual Waybar config source (often `desktop/waybar/config.nix` or a home-manager module).
2. Check the module definition for `"on-click"`. Example for network:
   ```nix
   network = {
     "format-wifi" = "󰖩";
     # ... other fields ...
     # If "on-click" is missing, the click does nothing.
   };
   ```

### Fix: check upstream best practice first, then bind
Before defaulting to a launcher-based menu (fuzzel/rofi/dmenu), check if the user's rice upstream has a preferred native GUI tool. For end-4/illogical-impulse, the upstream Quickshell config uses:
```qml
property string network: "kcmshell6 kcm_networkmanagement"
```
This is a full Qt/KDE network settings GUI that scans WiFi, manages wired/VPN, etc.

**Preferred: KDE KCM Network Management (end-4 best practice)**
If the user is using end-4 or wants a native GUI instead of a launcher menu:
```nix
home.packages = [
  pkgs.kdePackages.kcmutils   # provides kcmshell6
  pkgs.kdePackages.plasma-nm  # provides kcm_networkmanagement module
];

# In waybar config:
network = waybarSourceConfig.network // {
  "on-click" = "${pkgs.kdePackages.kcmutils}/bin/kcmshell6 kcm_networkmanagement";
};
```

**Fallback: launcher-based menu tool**
If the user explicitly prefers a minimal launcher menu or the rice has no upstream preference, use `networkmanager_dmenu` (from nixpkgs). It natively supports fuzzel, rofi, wofi, tofi, bemenu, walker, and wmenu.
- It **auto-detects** installed launchers and auto-injects the correct arguments (e.g., `--dmenu --placeholder` for fuzzel, `-dmenu -p` for rofi).
- Configure the launcher explicitly in `~/.config/networkmanager-dmenu/config.ini`:
  ```ini
  [dmenu]
  dmenu_command = fuzzel
  ```
- In home-manager, generate this config via `xdg.configFile`:
  ```nix
  xdg.configFile."networkmanager-dmenu/config.ini".text = ''
    [dmenu]
    dmenu_command = ${pkgs.fuzzel}/bin/fuzzel
  '';
  ```
- Bind Waybar's `on-click` to the full store path:
  ```nix
  network = waybarSourceConfig.network // {
    "on-click" = "${pkgs.networkmanager_dmenu}/bin/networkmanager_dmenu";
  };
  ```

**Other common modules:**
- Bluetooth: `blueman-manager` or `bluetuith` (TUI); for a launcher menu, use a custom `bluetoothctl` + fuzzel script.
- Audio: `pavucontrol-qt` or `pavucontrol` (already bound in many configs).
- Power/session: `wlogout` bound to `on-click` for the power module.

### Finding the true config source (not /etc/nixos/)
If `/etc/nixos/configuration.nix` or `home.nix` contains a `throw` saying "Legacy ... is retired", the real config lives elsewhere (commonly `~/nix-config/`). Search there:
```bash
find /home/$USER/nix-config -name "*.nix" -type f | head -20
```

### Restart Waybar after config changes
Waybar does not hot-reload JSON config changes. After a home-manager rebuild, the service may need manual restart:
```bash
# If dbus env is available in the session:
systemctl --user restart waybar.service

# If running remotely (missing DBUS_SESSION_BUS_ADDRESS):
sudo -u $USER bash -c 'export DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/1000/bus; export XDG_RUNTIME_DIR=/run/user/1000; systemctl --user restart waybar.service'

# Or kill and let systemd restart it:
kill $(pgrep waybar) && systemctl --user start waybar.service
```

### Verify the home-manager profile link updated (critical)

After `nixos-rebuild switch`, the new home-manager generation is built and the systemd service runs its activation script, **but the nix profile symlink at `~/.local/state/nix/profiles/home-manager` may fail to update** (e.g., due to concurrent activation issues or stale gcroots). Running processes like waybar (started via systemd user service) resolve `PATH` through this symlink. If it still points to the old generation, newly installed binaries (e.g., `kcmshell6`, `networkmanager_dmenu`) will be **missing from the process's PATH** even though `nixos-rebuild` reported success.

**Check:**
```bash
# See which generation the profile currently points to
ls -la ~/.local/state/nix/profiles/home-manager

# Check if the binary exists in the active home-path
ls ~/.local/state/nix/profiles/home-manager/home-path/bin/kcmshell6

# Check which generation the systemd service actually activated
systemctl status home-manager-$USER.service | grep ExecStart
```

**Fix if stale:**
```bash
# Find the latest generation
ls -la ~/.local/state/nix/profiles/home-manager-*-link | tail -5

# Manually relink to the latest generation
ln -sfn /nix/store/...-home-manager-generation ~/.local/state/nix/profiles/home-manager-NEW-link
ln -sfn home-manager-NEW-link ~/.local/state/nix/profiles/home-manager

# Then restart waybar (or any affected user service)
systemctl --user restart waybar.service
```

**Always verify the running process sees the new binary:**
```bash
cat /proc/$(pgrep waybar)/environ | tr '\0' '\n' | grep "^PATH="
ls /proc/$(pgrep waybar)/root/home/lingfeng/.local/state/nix/profiles/home-manager/home-path/bin/ | grep kcmshell
```

### Diagnosing waybar on-click failures with a wrapper script

If the user reports that clicking a Waybar module does nothing, create a diagnostic wrapper script to capture the exact environment and errors:

```bash
# ~/.local/bin/waybar-click-debug.sh
#!/usr/bin/env bash
exec >> /tmp/waybar_click.log 2>&1
echo "=== $(date) ==="
echo "Command: $0"
echo "PATH: $PATH"
echo "DISPLAY: $DISPLAY"
echo "WAYLAND_DISPLAY: $WAYLAND_DISPLAY"
echo "XDG_RUNTIME_DIR: $XDG_RUNTIME_DIR"
echo "DBUS_SESSION_BUS_ADDRESS: $DBUS_SESSION_BUS_ADDRESS"
which kcmshell6 || echo "kcmshell6 NOT FOUND"
# Then run the actual command
/home/lingfeng/.local/state/nix/profiles/home-manager/home-path/bin/kcmshell6 kcm_networkmanagement
echo "Exit code: $?"
```

Bind Waybar `on-click` to this script instead of the direct command. After the user clicks, inspect `/tmp/waybar_click.log`.

**Alternative: verify the command works in waybar's actual environment:**
```bash
WAYBAR_PID=$(pgrep waybar)
# Run kcmshell6 with waybar's exact environment
env -i $(cat /proc/$WAYBAR_PID/environ | tr "\0" "\n" | grep -E "^(PATH|HOME|XDG_RUNTIME_DIR|WAYLAND_DISPLAY|DISPLAY|DBUS_SESSION_BUS_ADDRESS|USER|LANG|LC_)=" | xargs -I{} echo "{}" | tr "\n" " ") /nix/store/.../bin/kcmshell6 kcm_networkmanagement
```

If this works but the click does not, the issue is likely in Waybar's event handling (e.g., the module is inside a `group` that intercepts clicks, or the JSON config was not reloaded).

## TTY / PTY Issues with `foot -e` and Interactive Programs

When binding a Hyprland key to launch an interactive TUI program inside `foot` (e.g. an AI agent TUI, a REPL, or any tool that checks `isatty()` / `process.stdin.isTTY`), the program may immediately exit with a "no TTY" error even though `foot -e` appears to provide a terminal.

### Root cause
`foot -e` creates a PTY for the direct child process, but if that child is a shell script or interpreter that spawns deeper subprocesses (e.g. Python → Node.js), the TTY detection in the deepest process can fail because the PTY is not reliably inherited through the chain.

### Diagnosis
1. The keybind appears correct and Hyprland loads it (`hyprctl binds` shows it).
2. No window appears, or the window flashes and disappears.
3. Running the same command manually in an interactive terminal works fine.
4. The program logs show `no TTY` or `process.stdin.isTTY` is false.

### Fix: force a PTY with `script`
Wrap the command with `script -q -c "..." /dev/null`. The `script` command (from util-linux) explicitly allocates a pseudo-terminal, ensuring TTY detection succeeds for the entire command chain.

**Before (broken):**
```conf
bind = Super, Space, exec, foot --app-id=my-tui -e my-tui-command
```

**After (working):**
```conf
bind = Super, Space, exec, foot --app-id=my-tui -e script -q -c "my-tui-command" /dev/null
```

For a toggle-style binding (open if closed, close if open):
```conf
bind = Super, Space, exec, pkill -f "foot --app-id=my-tui" || foot --app-id=my-tui -e script -q -c "my-tui-command" /dev/null
```

Window rules to make it float and centered:
```conf
windowrule = match:class ^(my-tui)$, float on
windowrule = match:class ^(my-tui)$, center on
windowrule = match:class ^(my-tui)$, size (monitor_w*.70) (monitor_h*.75)
```

### Key verification steps
1. Check the actual class reported by Hyprland after launch:
   ```bash
   hyprctl clients -j | jq '.[] | select(.class == "my-tui") | {class, title, floating}'
   ```
2. If the class does not match the `match:class` rule, check what `foot --app-id` actually sets:
   ```bash
   foot --app-id=test-app -e sleep 30 &
   hyprctl clients -j | jq '.[] | select(.class == "test-app") | {class, initialClass}'
   ```
3. If `script` is not available, install it (it is part of `util-linux` and is usually present on NixOS).

## Pitfalls
- `$(slurp)` inside a Nix double-quoted string is fine (Nix only interpolates `${...}`), but the string is passed to a shell by Hyprland, so shell variable/command substitution happens at runtime.
- Do NOT attempt to chmod or override the read-only symlink in `~/.config/hypr/`; home-manager will overwrite it on next activation.
- If the user is unsure about syntax, apply with `hyprctl` first to verify before editing the Nix file and rebuilding.
- When recommending popular rices, always check deprecation status first. `prasanthrangan/hyprdots` is deprecated despite high star count.
