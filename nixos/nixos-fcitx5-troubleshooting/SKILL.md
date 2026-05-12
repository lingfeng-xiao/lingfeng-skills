---
name: nixos-fcitx5-troubleshooting
description: >
  Systematically diagnose and fix fcitx5 input method issues on NixOS,
  especially missing input methods (pinyin, rime, etc.) and Wayland
  frontend misconfiguration.
triggers:
  - fcitx5 not working on NixOS
  - missing pinyin / rime / table input methods in fcitx5
  - fcitx5 addons not loading
  - NixOS fcitx5 Wayland input method broken
  - cannot type Chinese / Japanese / Korean in fcitx5 on NixOS
---

# NixOS fcitx5 Troubleshooting

## 1. Verify fcitx5 is running

```bash
pgrep -a fcitx5
systemctl --user status app-org.fcitx.Fcitx5@autostart.service
env | grep -E "IM_MODULE|XMODIFIERS"
```

## 2. Check what input methods are actually available

This is the **most important diagnostic step**.
```bash
dbus-send --print-reply --dest=org.fcitx.Fcitx5 /controller \
  org.fcitx.Fcitx.Controller1.AvailableInputMethods 2>/dev/null | grep string
```

If your configured input method (e.g. `pinyin`, `rime`) is **not** in the list,
the addon is missing from the active `fcitx5-with-addons` derivation.

## 3. Check which store path is actually running

Multiple `fcitx5-with-addons` derivations can coexist on the system.
The one in the current `$PATH` (or started by autostart) is what matters.

```bash
readlink -f $(which fcitx5)
ls $(dirname $(readlink -f $(which fcitx5)))/../lib/fcitx5 | grep -E "pinyin|rime|table"
ls $(dirname $(readlink -f $(which fcitx5)))/../share/fcitx5/addon | grep -E "pinyin|rime|table"
```

You can also find all coexisting derivations:
```bash
find /nix/store -maxdepth 1 -name '*fcitx5-with-addons*' -type d
```

If the running derivation lacks `libpinyin.so` / `pinyin.conf`, the addon is
not included in the build.

## 4. Root Cause: `fcitx5-with-addons` defaults to empty addons

NixOS's `fcitx5-with-addons` has `addons ? [ ]` by default.
**You MUST explicitly add language addons** in `configuration.nix`:

```nix
i18n.inputMethod = {
  enable = true;
  type = "fcitx5";
  fcitx5 = {
    waylandFrontend = true;
    addons = with pkgs; [ qt6Packages.fcitx5-chinese-addons ];
    # For Japanese: fcitx5-mozc
    # For Korean: fcitx5-hangul
    # For RIME: fcitx5-rime
    # NOTE: In nixpkgs 24.11+, fcitx5-chinese-addons was moved to
    # qt6Packages.fcitx5-chinese-addons. Using the bare name will error.
  };
};
```

## 5. Rebuild and restart

```bash
sudo nixos-rebuild switch
killall fcitx5 && fcitx5 -d
```

Or just relogin to pick up the new derivation via xdg-autostart.

## 6. Verify the fix

```bash
dbus-send --print-reply --dest=org.fcitx.Fcitx5 /controller \
  org.fcitx.Fcitx.Controller1.AvailableInputMethods 2>/dev/null | grep -i pinyin
```

## Pitfalls

- Do NOT manually set `GTK_IM_MODULE` / `QT_IM_MODULE` when using
  `waylandFrontend = true`. The NixOS module intentionally omits them;
  setting them in `home.sessionVariables` forces XIM and breaks native
  Wayland text-input-v3 protocol.

- Setting `fcitx5.addons = [ ]` or omitting it entirely builds a bare
  `fcitx5-with-addons` that only has keyboard layouts. The GUI configtool
  may still show pinyin/rime in the profile, but they won't load because
  the shared libraries are absent from the closure.

- Always verify against the **running** derivation, not just whatever
  `nix search` or `nixpkgs` source says. Multiple `fcitx5-with-addons`
  store paths can coexist; the one in `$PATH` is what matters.