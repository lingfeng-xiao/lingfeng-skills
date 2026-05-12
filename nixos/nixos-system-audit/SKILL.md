---
name: nixos-system-audit
description: Systematic security and best-practice audit for NixOS + Home Manager configurations. Produces a prioritized gap report with concrete remediation steps.
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [nixos, audit, security, hardening, review]
    related_skills: [nixos-home-manager-package-install, nixos-mihomo-client-vpn]
---

# NixOS System Audit Skill

Use this skill when the user asks for a review, audit, or gap analysis of their NixOS configuration against best practices.

## Trigger conditions

- User asks to "analyze", "audit", "review", or find "gaps" / "shortcomings" in their NixOS setup.
- User wants to know what is missing or suboptimal in their configuration.
- Pre-upgrade or post-install health check.

## Core workflow

**Phase 1: Read configuration files**

Always read these files first (read-only):
- `/etc/nixos/configuration.nix`
- `/etc/nixos/flake.nix`
- `/etc/nixos/home.nix` (if using HM via flake)
- `~/.hermes/config.yaml` (if Hermes Agent is in scope)

**Phase 2: System-level security probes**

Run these commands (all read-only / non-mutating):

```bash
# Disk encryption
lsblk -f

# Firewall status
sudo systemctl status firewall --no-pager
sudo iptables -L -n | head -20

# Listening ports
sudo ss -tlnp

# SSH hardening
sudo sshd -T | grep -E "^(permitrootlogin|passwordauthentication|port|x11forwarding)"

# Fail2ban
sudo fail2ban-client status 2>/dev/null || echo "fail2ban not running"

# Nix maintenance
nix-collect-garbage -d --dry-run 2>&1 | tail -5
grep -E "gc|optimise" /etc/nixos/configuration.nix || echo "no gc config"

# Git tracking of config
cd /etc/nixos && git status 2>/dev/null || echo "not a git repo"
```

**Phase 3: Dotfiles and services inspection**

```bash
# Non-HM-managed dotfiles
ls -la ~/.config/kitty/ ~/.config/nvim/ 2>/dev/null

# SSH keys presence
ls -la ~/.ssh/

# Sensitive data scan
grep -rE "sk-[a-zA-Z0-9]{20,}|api[_-]?key|token" ~/.hermes/ 2>/dev/null | grep -v ".db" | grep -v "models_dev_cache" | head -20

# Service status checks
systemctl --user status mihomo 2>/dev/null || systemctl status mihomo 2>/dev/null
ps aux | grep -E "mihomo|flclash" | grep -v grep
```

**Phase 4: Best-practice gap analysis**

Score each item as High/Medium/Low/None. The six audit dimensions:

1. **NixOS System Security** — disk encryption, firewall, SSH hardening, fail2ban, auditd
2. **Home Manager Environment** — git/ssh config, PATH duplication, dotfiles under HM vs manual, program configs
3. **Desktop Ecosystem** (if Hyprland/Wayland) — lockscreen, idle, bar, notifications, wallpaper, hotplug, brightness/volume
4. **Agent/Tooling Security** (if Hermes) — API key storage, gateway binding, approvals, PII redaction
5. **Secrets Management** — agenix/sops-nix usage, plaintext credential scan
6. **Ops & Recovery** — config in git, backups, snapshots, auto-maintenance

**Phase 5: Deliverable**

Produce a report with:
- Executive summary (count of H/M/L issues)
- Each finding: current state, risk, concrete remediation (exact nix code or command)
- Prioritized action checklist (P0/P1/P2/P3)
- List of things that are already done well (positive reinforcement)

## Critical checks (never skip)

| Check | Why it matters |
|-------|----------------|
| `lsblk -f` for LUKS | Unencrypted disk = data exposure on theft |
| `sshd -T` for PasswordAuthentication | Password login = brute force risk |
| `~/.ssh/` key presence | No keys implies password dependency |
| `nix-collect-garbage --dry-run` | Indicates lack of auto-GC |
| `/etc/nixos` git status | No VCS = no rollback |
| `grep` for API keys in ~/.hermes/ | Plaintext keys = credential theft |
| Multiple service instances (e.g. mihomo) | Port conflicts, resource waste, security confusion |

## Report template

Structure the final output as:

```
# NixOS System Configuration Audit Report

## Executive Summary
X high, Y medium, Z low priority issues found.

## High Priority
### H1: [Title]
- Status: ...
- Risk: ...
- Fix: ... (exact nix or command)

## Medium Priority
...

## Low Priority
...

## Already Good
- ...

## Action Checklist
| Priority | Action | ETA |
```

## Pitfalls

- **stateVersion**: Do NOT suggest changing `system.stateVersion` or `home.stateVersion`. Only confirm whether it matches the install-time NixOS version. If user says "use system version", note it and move on.
- **Firewall**: NixOS enables firewall by default, but custom `allowedTCPPorts` may be scattered across modules (e.g. `programs.steam.remotePlay.openFirewall`). Always inspect `iptables -L` even if `networking.firewall` is not explicitly in `configuration.nix`.
- **Duplicate PATH**: Home Manager users often define PATH in `home.sessionVariables`, `home.sessionPath`, and inside WM `env` blocks simultaneously. Flag this.
- **.hermes/.env**: Hermes stores credentials in `~/.hermes/.env` and `auth.json`. Check both. Even if `config.yaml` shows empty `api_key: ''`, the real key may be in `.env`.
- **Show, don't just save**: The user strongly prefers audit results displayed directly in chat. Do NOT only save to `.hermes/plans/` without showing the content. If a plan file is required by skill instructions, show the full content immediately after saving.
