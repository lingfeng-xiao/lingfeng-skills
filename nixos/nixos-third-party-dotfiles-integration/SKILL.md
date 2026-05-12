---
name: nixos-third-party-dotfiles-integration
description: |
  Integrate a third-party Hyprland/home-manager dotfiles repository (e.g. end-4/dots-hyprland)
  into a NixOS flake-based system, including common pitfalls like outdated forks,
  home-manager xdg config file conflicts, missing QML modules, and Qt import paths.
trigger: |
  When the user wants to install a popular Hyprland rice or third-party dotfiles on NixOS,
  especially one that uses home-manager modules, quickshell/ags, and Qt QML components.
---

# NixOS Third-Party Dotfiles Integration

## Overview

This skill covers the complete workflow for integrating a third-party dotfiles repository
(typically a popular Hyprland rice like end-4/dots-hyprland) into a NixOS flake-based
configuration.

## Step 1: Research & Select the Right Source

1. Find the most popular upstream (e.g. GitHub stars)
2. Check for an existing NixOS port (`*-nixos` community repo)
3. **Critical**: Check the port's locked dotfiles version vs upstream latest
   - Ports often reference an outdated fork (`?ref=tmp`)
   - Compare commit dates via GitHub API
   - If >3 months behind, switch to upstream latest to avoid 100+ config errors
4. Add the port as a local path flake input: `path:./repo-name`
5. Pass upstream dotfiles as a separate flake input with `flake = false`
6. **Check for git submodules**: If upstream uses submodules (e.g. `rounded-polygon-qmljs`),
   Nix flakes default will NOT fetch them into the source tree. Even `fetchSubmodules = true`
   on a `flake = false` input may leave submodule directories empty in the store.
   
   **Two approaches to fix submodules:**
   
   **Approach A (flake input override)** — Override the port's sub-input in your main flake:
   ```nix
   illogical-impulse = {
     url = "path:./end-4-nixos";
     inputs.nixpkgs.follows = "nixpkgs";
     inputs.hyprland.follows = "hyprland";
     inputs.illogical-impulse-dotfiles = {
       type = "git";
       url = "https://github.com/end-4/dots-hyprland";
       submodules = true;
       flake = false;
     };
   };
   ```
   - You must use `type = "git"` with `url = "https://..."` — `github:` URL type rejects `submodules = true`
   - **Warning**: `path:` type flake inputs have tricky override semantics. The override
     above may not be inherited by the sub-flake in all cases. After `nix flake update`,
     always verify with `nix flake metadata` that the lock actually points where you expect:
     ```bash
     nix flake metadata | grep illogical-impulse-dotfiles
     # Should show: github:end-4/dots-hyprland or git+https://github.com/end-4/dots-hyprland
     # NOT: github:xBLACKICEx/dots-hyprland
     ```
   - Even when `submodules = true` appears in the lock, the submodule files may be stored
     in a *separate* store path and NOT merged into the main source directory. Check with:
     ```bash
     ls $(nix eval --raw '.#inputs.illogical-impulse.inputs.illogical-impulse-dotfiles.outPath')/dots/.config/quickshell/ii/modules/common/widgets/shapes/
     ```
   
   **Approach B (manual merge in derivation)** — More reliable, works regardless of flake semantics:
   ```nix
   let
     shapesSubmodule = pkgs.fetchFromGitHub {
       owner = "end-4";
       repo = "rounded-polygon-qmljs";
       rev = "e31ec4cb4ebf6a46b267f5c42eabf6874916fa16";  # pin to upstream submodule commit
       hash = "sha256-p1Ia0oQCWnik2saVMgv7IABkaJV43PoY7uuwXjXlc+Q=";
     };
     quickshellConfig = pkgs.runCommandLocal "quickshell-config" {} ''
       cp -r ${illogical-impulse-dotfiles}/dots/.config/quickshell $out
       chmod -R u+w $out
       mkdir -p $out/ii/modules/common/widgets/shapes
       cp -r ${shapesSubmodule}/* $out/ii/modules/common/widgets/shapes/
     '';
   in
   {
     xdg.configFile."quickshell".source = quickshellConfig;
   }
   ```
   This bypasses all flake submodule behavior and guarantees the files are physically present.

## Step 2: Fix Common Port Bugs Before First Build

Community ports often have bit-rot. Two bugs encountered in practice with the
end-4 NixOS port:

**Bug A: Undefined variable `system`**
In `modules/packages.nix`, the port may reference `inputs.nur.legacyPackages."${system}"`
where `system` is not in scope. Fix:
```bash
sed -i 's/"\${system}"\.repos/"\${pkgs.system}"\.repos/g' modules/packages.nix
```

**Bug B: Quickshell source build fails**
The port may reference `inputs.quickshell.packages.${pkgs.system}.default` which
builds from upstream git and often fails due to missing Qt private headers
(e.g. `Qt6::WaylandClientPrivate` not found). The fix is to use the nixpkgs
pre-built binary instead:
```nix
# In modules/quickshell.nix
pkgs.quickshell  # nixpkgs 0.2.1+ typically works
```
instead of `inputs.quickshell.packages.${pkgs.system}.default`.

## Step 3: Fix Path Structure Changes

Upsteam repos often change directory structure. Common fix:
- Old: `.config/hypr/...`
- New: `dots/.config/hypr/...`

Batch-fix in the port's `.nix` files:
```bash
sed -i 's|\.config/|dots/.config/|g' modules/*.nix
```

## Step 3: Handle Missing QML Types in nixpkgs Quickshell

nixpkgs `quickshell` is often older than what the upstream dotfiles requires.
Missing types encountered in practice:
- `Quickshell.Services.Polkit` (nixpkgs build excludes Polkit plugin)
- `IdleInhibitor` from `Quickshell.Wayland`

**Solution**: Patch the QML files at build time using `runCommandLocal`:

```nix
let
  quickshellConfig = pkgs.runCommandLocal "quickshell-config" {} ''
    cp -r ${upstream-dotfiles}/dots/.config/quickshell $out
    chmod -R u+w $out

    # Stub PolkitService
    cat > $out/ii/services/PolkitService.qml << 'QML'
    pragma Singleton
    import QtQuick
    import Quickshell
    Singleton {
        id: root
        property var agent: null
        property bool active: false
        property var flow: null
        property bool interactionAvailable: false
        property string cleanMessage: ""
        property string cleanPrompt: "Password"
        function cancel() {}
        function submit(string) { root.interactionAvailable = false }
    }
    QML

    # Stub Idle (remove IdleInhibitor)
    cat > $out/ii/services/Idle.qml << 'QML'
    pragma Singleton
    import QtQuick
    import Quickshell
    Singleton {
        id: root
        property bool inhibit: false
        function toggleInhibit(active = null) {
            root.inhibit = active !== null ? active : !root.inhibit;
        }
    }
    QML
  '';
in
{
  xdg.configFile."quickshell".source = quickshellConfig;
}
```

**Why this works**: home-manager's `xdg.configFile."dir".source` creates a symlink.
`xdg.configFile."dir/file".text` cannot override files inside a symlink target.
`runCommandLocal` creates a real directory copy in the Nix store with patches applied.

## Step 4: Set Qt QML Import Paths

Quickshell needs `QML_IMPORT_PATH` to find Qt5Compat, QtPositioning, Kirigami, etc.

```nix
home.sessionVariables = {
  QML_IMPORT_PATH = lib.mkForce (lib.makeSearchPath "lib/qt-6/qml" (with pkgs.kdePackages; [
    qtdeclarative
    qtpositioning
    qtquicktimeline
    qtmultimedia
    qtsensors
    qtvirtualkeyboard
    qtwayland
    qt5compat
    kirigami.unwrapped   # CRITICAL: NOT just kirigami — see Kirigami Wrapper Pitfall below
  ]));
};
```

**Why `lib.mkForce`**: If you use `home-manager.nixosModules.home-manager` with `qt.enable = true`,
the Qt platform integration module sets its own `QML_IMPORT_PATH` via `hm-session-vars.sh`.
Without `lib.mkForce`, Nix will error with "conflicting definition values" or silently use
the Qt module's version that lacks Kirigami.

**Kirigami Wrapper Pitfall** (`kdePackages.kirigami`):
In nixpkgs, `kdePackages.kirigami` is a **wrapper derivation** (`kirigami-wrapped`) that contains
NO QML files — only `nix-support/propagated-build-inputs`. The actual QML lives in the underlying
unwrapped output.
- Wrong: `${pkgs.kdePackages.kirigami}/lib/qt-6/qml` → empty or missing, causes `module "org.kde.kirigami" is not installed`
- Correct: `${pkgs.kdePackages.kirigami.unwrapped}/lib/qt-6/qml`

If `.unwrapped` is not exposed in your nixpkgs version, find the unwrapped store path via:
```bash
# Find the drv that actually builds kirigami
nix-store -q --deriver $(readlink -f $(which qmlscene) | xargs -I{} dirname {})/../lib/qt-6/qml/org/kde/kirigami 2>/dev/null || \
  nix-store -q --deriver /nix/store/38mx04f5zqdslciyh99fizgiw7s2bvfw-kirigami-6.25.0
# Then get its outputs
nix-store -q --outputs /nix/store/...-kirigami-6.25.0.drv
```
Or simply hardcode the unwrapped path as a fallback in your config and replace it with `.unwrapped`
once you confirm the attribute exists.

**Note**: `QML_IMPORT_PATH` may not appear in `systemctl --user show-environment`
because home-manager writes it to `hm-session-vars.sh` (shell profile), not `environment.d`.
The `qs` binary launched from a terminal inherits it; for autostart, ensure the shell
profile is sourced or set it in `environment.systemVariables` in `configuration.nix`.

**When using home-manager as a NixOS module**: Changes to `home.sessionVariables` only
propagate to `/etc/profiles/per-user/$USER/etc/profile.d/hm-session-vars.sh` after a
full `sudo nixos-rebuild switch --flake /etc/nixos`. Running just `home-manager switch`
or `result/activate` from a standalone build is insufficient because the system profile
must be regenerated.

## Step 5: Fix Hyprland Version Incompatibilities

**Critical check FIRST**: Before writing any compatibility patches, verify whether
the upstream dotfiles have ALREADY been updated for your Hyprland version.

```bash
# Check what syntax the upstream rules.conf actually uses
storepath=$(nix eval --raw '.#nixosConfigurations.<hostname>.config.home-manager.users.<user>.xdg.configFile."hypr/hyprland/rules.conf".source')
grep -c "windowrulev2" "$storepath"  # If 0, upstream already uses new syntax
grep -c "match:class" "$storepath"   # If >0, upstream is 0.54.0+ ready
```

If upstream already uses `match:class` (Hyprland 0.54.0+ syntax), **do NOT**
create a `hyprland-compat/general.conf`. Your "compatibility patch" will:
- Silently discard upstream's carefully maintained config
- Potentially re-introduce OLD syntax that 0.54.0 rejects
- Create subtle mismatches between your general.conf and upstream's other configs

Only create compatibility patches when upstream is CONFIRMED to be outdated:
1. Check `hyprctl configerrors` after rebuild
2. Create a minimal `hyprland-compat/general.conf` that strips ONLY the failing options
3. Override upstream's config with `xdg.configFile."hypr/hyprland/general.conf" = lib.mkForce { source = ./hyprland-compat/general.conf; }`

Common removed options in Hyprland 0.54.0+:
- `decoration:shadow:ignore_window = true`
- `misc:vfr = 1`

**Pitfall**: `lib.mkForce` on `xdg.configFile."hypr/hyprland/general.conf"` completely
replaces upstream's file. If upstream has already fixed compatibility, your override
reverts those fixes and re-introduces errors.

## Step 6: Preserve User Customizations

Place custom configs in `/etc/nixos/hypr-custom/` and force-override:
```nix
xdg.configFile."hypr/custom" = lib.mkForce {
  source = ./hypr-custom;
  recursive = true;
};
```

This preserves: keybinds, monitor config, window rules, execs, env vars.

**Why `recursive = true` and `lib.mkForce`**: The port module likely sets
`xdg.configFile."hypr/custom".source = ...` (a directory). You cannot
simultaneously define a directory and files inside it (e.g.
`xdg.configFile."hypr/custom/env.conf".text`). Nix will error with a path
collision. You must override the *entire directory* with `lib.mkForce`.

Keep the custom files minimal — they are sourced by the upstream config
via `source=~/.config/hypr/custom/*.conf`.

## Step 7: Verify Quickshell Can Start

After rebuild and switch:
1. Check `pgrep -a quickshell` — should show the process
2. If not running, test manually: `qs -c ii` (or the config name used)
3. Common startup failure: `module "qs.modules.common.widgets.shapes" is not installed`
   → This means git submodules were NOT fetched (see Step 1, item 6)
4. Check shapes dir: `ls ~/.config/quickshell/ii/modules/common/widgets/shapes/`
   Should contain `.js` and `.qml` files, not be empty.

## Step 8: Debug "Rebuild Succeeds But Desktop Is Broken"

A common and confusing scenario: `nixos-rebuild switch` completes, `nix flake check`
passes, but the desktop is unusable or full of errors. This means **evaluation is fine,
but runtime config files are wrong.**

### Debugging methodology

1. **Confirm evaluation health**
   ```bash
   nix flake check --no-build
   ```
   If this passes, the problem is not Nix syntax — it's the content of generated configs.

2. **Inspect actual config files being deployed**
   ```bash
   # Find what nix store path a config file comes from
   nix eval --raw '.#nixosConfigurations.<host>.config.home-manager.users.<user>.xdg.configFile."hypr/hyprland/rules.conf".source'
   
   # Read it directly from the store (read-only, safe)
   cat /nix/store/...-source/dots/.config/hypr/hyprland/rules.conf
   ```

3. **Check for silent `lib.mkForce` overwrites**
   Search the user's `home.nix` for `mkForce`:
   ```bash
   grep -n "mkForce" /etc/nixos/home.nix
   ```
   Each `mkForce` silently discards whatever the upstream module declared for that
   same path. Common problematic overrides:
   - `xdg.configFile."hypr/hyprland/general.conf"` — discards upstream's general config
   - `xdg.configFile."hypr/custom"` — discards upstream's default custom files
   
   **Before forcing, verify upstream's version is actually broken.** See Step 5.

4. **Check Hyprland config errors**
   ```bash
   hyprctl configerrors
   ```
   If this returns 200+ errors, the upstream dotfiles are likely outdated for your
   Hyprland version. But if it returns 0 errors, your `lib.mkForce` overrides may
   be the source of problems.

5. **Check for conflicting monitor declarations**
   If both the upstream module sets `wayland.windowManager.hyprland.settings.monitor`
   AND a force-overridden `general.conf` contains `monitor=...`, the latter wins.
   This may accidentally disable a display that the module's `settings.monitor`
   carefully configured.

### Common root causes

| Symptom | Likely Cause |
|---------|-------------|
| `nix flake check` passes, desktop blank/crashed | Upstream configs already fixed for new Hyprland, but user's `hyprland-compat/` overrides reverted them |
| 200+ `configerrors` on first login | Upstream dotfiles outdated for Hyprland version; need compatibility patches (Step 5) |
| Quickshell widgets missing / panel empty | Git submodules not fetched; `shapes/` directory empty |
| Custom keybinds don't work | `lib.mkForce` on `hypr/custom` discarded upstream's default submap setup |
| Only some end-4 features work | Partial override — some upstream configs loaded, others force-replaced |

## Pitfalls

1. **Do NOT downgrade Hyprland** — user preference is forward-compatible solutions
2. **Do NOT manually modify SQLite/shared_prefs** of GUI apps — user strongly dislikes
3. **home-manager backup conflicts**: if switching from symlink `xdg.configFile` to
   `recursive = true`, delete the old symlink first or backup will fail on read-only store files
4. **Empty upstream directories**: some upstream modules may reference directories that
   are empty in the repo (e.g. `shapes/`). This is an upstream bug, not a NixOS issue.
5. **`qsConfig` environment variable missing**: If Hyprland execs.conf uses `qs -c $qsConfig`,
   this variable MUST be defined in `environment.sessionVariables` in configuration.nix.
   Otherwise Hyprland will pass an empty string to `-c` flag and Quickshell will fail to start.
   Fix: add `environment.sessionVariables.qsConfig = "ii";` to configuration.nix.
6. **Quickshell config symlink confusion**: On NixOS with dots-hyprland port, `~/.config/quickshell`
   is typically a symlink to a nix store path (immutable). User customizations should go in
   `~/.config/illogical-impulse/config.json` (for ii theme) — this is the user's editable config.
   The bar configuration lives in `config.json` under the `"bar"` key.

## Debugging Bar (Quickshell) Issues

The "bar" in end-4's dots-hyprland is NOT waybar — it's **Quickshell's panel system** (ii theme).
Bar debugging steps:

1. **Identify the bar process**:
   ```bash
   ps aux | grep -E 'quickshell|qs' | grep -v grep
   # Should show: quickshell -c ii
   ```

2. **Find user-editable config** (not the nix store symlink):
   ```bash
   # ~/.config/quickshell is symlinked to nix store (immutable)
   # User config is in:
   cat ~/.config/illogical-impulse/config.json | python3 -c "import json,sys; print(json.dumps(json.load(sys.stdin()).get('bar', {}), indent=2))"
   ```

3. **Check bar config options** (from `~/.config/illogical-impulse/config.json`):
   ```json
   "bar": {
     "autoHide": { "enable": false, ... },
     "bottom": false,        // true = bottom, false = top
     "cornerStyle": 0,       // 0=Hug, 1=Float, 2=Rect
     "showBackground": true,
     "workspaces": { "shown": 10, ... },
     "weather": { "enable": false, ... }
   }
   ```

4. **Check generated colors** (if bar looks wrong color):
   ```bash
   cat ~/.local/state/quickshell/user/generated/colors.json
   # If background is light (e.g. #fff7fb), matugen generated light theme from wallpaper
   ```

5. **Reload Quickshell** after config changes:
   - Open Quickshell settings: `Super+I`
   - Or reload via sidebar: `Super+N` → click "Reload Quickshell"

6. **Common bar issues**:
   - Bar not visible: Check `GlobalStates.barOpen` is true in states.json
   - Wrong position: Edit `"bar.bottom"` in config.json
   - Style broken: Check `"bar.cornerStyle"` and `"bar.showBackground"`
   - Weather not working: Set `"bar.weather.enable": true` in config.json

## Verification Checklist

- [ ] `sudo nixos-rebuild switch` completes without error
- [ ] `nix flake check --no-build` passes
- [ ] `nix flake metadata` confirms dotfiles input points to expected upstream (not outdated fork)
- [ ] `hyprctl configerrors` reports 0 errors
- [ ] `hyprctl reload` returns `ok`
- [ ] `qs -c ii` (or appropriate config) launches without "module X is not installed"
- [ ] Quickshell shapes dir is non-empty: `ls ~/.config/quickshell/ii/modules/common/widgets/shapes/`
- [ ] Kirigami is accessible: `ls ~/.config/quickshell/...` does NOT error on `org.kde.kirigami`
  - If `module "org.kde.kirigami" is not installed`, verify `QML_IMPORT_PATH` contains
    `${pkgs.kdePackages.kirigami.unwrapped}/lib/qt-6/qml` (not the wrapped derivation)
  - Verify with: `echo "$QML_IMPORT_PATH" | tr ':' '\n' | grep kirigami`
- [ ] Custom keybinds still work
- [ ] Input method (fcitx5) still functional
- [ ] No `lib.mkForce` overrides that discard upstream configs without verification (Step 5, Step 8)