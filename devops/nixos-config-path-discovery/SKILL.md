---
name: nixos-config-path-discovery
description: Discover the real NixOS + home-manager flake configuration path when /etc/nixos contains legacy shims or compatibility entrypoints.
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [nixos, home-manager, flakes, configuration]
---

# NixOS Configuration Path Discovery

Use this when `/etc/nixos/home.nix` or `/etc/nixos/configuration.nix` turns out to be a legacy shim (throw statement) rather than the actual configuration.

## When to use
- `/etc/nixos/home.nix` contains `throw ''` with text like "Legacy ... is retired"
- `/etc/nixos/configuration.nix` redirects to another path
- The user mentions their config lives under `~/nix-config` or similar

## Detection

Read the files under `/etc/nixos/`:

```bash
cat /etc/nixos/home.nix
cat /etc/nixos/configuration.nix
cat /etc/nixos/flake.nix
```

If you see patterns like:
- `throw ''\nLegacy /etc/nixos/home.nix is retired.\nUse the system flake entrypoint or the source repo directly:`
- `inputs.nix-config.url = "path:/home/lingfeng/nix-config";`

Then the real config lives elsewhere.

## Finding the real path

### Method 1: Read the flake.nix shim

```bash
cat /etc/nixos/flake.nix
```

Look for:
```nix
inputs.nix-config.url = "path:/home/<user>/nix-config";
```

### Method 2: Search for flake.nix in home directory

```bash
find /home -maxdepth 2 -name "flake.nix" -type f 2>/dev/null
```

### Method 3: Check common locations

Common real config paths:
- `~/nix-config`
- `~/.config/nixos`
- `~/dotfiles/nixos`

## Rebuild command

When the real config is at `~/nix-config`:

```bash
cd ~/nix-config && sudo nixos-rebuild switch --flake .#nixos
```

The hostname in `--flake .#<hostname>` comes from `nixosConfigurations.<name>` in flake.nix.

## Home-manager location in custom module systems

Some users structure their config with a custom option system. After finding the real config directory, look for:

```
<config-dir>/modules/system/lf.nix          # system-level options
<config-dir>/modules/home/apps/user.nix     # home.packages wiring
<config-dir>/hosts/nixos/default.nix        # host-specific enable flags
```

In this pattern:
1. Add the option flag in the system options file (e.g. `lf.apps.notes.obsidian`)
2. Wire the package in the home module (conditional `home.packages` entry)
3. Enable the flag in the host config

## Pitfalls

1. **Do not assume /etc/nixos/ is the source of truth** — always read the files first.
2. **Legacy shims may still work for rebuild** — `/etc/nixos/flake.nix` may be a valid compatibility entrypoint that delegates to the real config.
3. **Check file ownership** — files under `/etc/nixos/` may be owned by root, requiring `sudo` to read.
