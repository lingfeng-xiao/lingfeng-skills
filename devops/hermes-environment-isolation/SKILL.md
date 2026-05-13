---
name: hermes-environment-isolation
description: Separate Hermes runtime data, custom system code, and versioned skills into isolated layers — enabling clean reinstalls without data loss
tags: [hermes, backup, migration, data-isolation, git, nixos]
---

# Hermes Environment Isolation

Split Hermes into three layers so the runtime can be wiped/reinstalled without losing data or custom system code.

## Architecture

| Layer | Path | Purpose |
|---|---|---|
| **Data** | `~/.hermes-data/` | Runtime data: sessions, state.db, checkpoints, memories, logs, cache |
| **System** | `~/lingfeng-system/` | Custom code: LPMO, gateway-ha, config, install scripts |
| **Skills** | `~/.hermes/skills/` | Versioned skills (git repo, pushed to GitHub) |
| **Hermes** | `~/.hermes/` | Symlinks to Data layer; Hermes runtime reads/writes through symlinks |

## Procedure

### 1. Migrate Data Layer

```bash
# Create data directory
mkdir -p ~/.hermes-data/{sessions,checkpoints,memories,english-diary,weixin,logs,cache,lpmo}

# Copy data (NOT move — keep originals until verified)
cp -r ~/.hermes/sessions/*     ~/.hermes-data/sessions/
cp    ~/.hermes/state.db       ~/.hermes-data/
cp -r ~/.hermes/checkpoints/*  ~/.hermes-data/checkpoints/
cp -r ~/.hermes/memories/*     ~/.hermes-data/memories/
cp -r ~/.hermes/english-diary/* ~/.hermes-data/english-diary/
cp -r ~/.hermes/weixin/*       ~/.hermes-data/weixin/
cp -r ~/.hermes/logs/*         ~/.hermes-data/logs/
cp -r ~/.hermes/cache/*        ~/.hermes-data/cache/
```

### 2. Create Symlinks (keep Hermes compatible)

```bash
cd ~/.hermes
mv sessions sessions.old && ln -s ~/.hermes-data/sessions sessions
mv state.db state.db.old && ln -s ~/.hermes-data/state.db state.db
# ... repeat for checkpoints, memories, english-diary, weixin, logs, cache
```

### 3. Verify Services Still Work

```bash
systemctl --user is-active hermes-gateway
systemctl --user is-active hermes-gateway-ha
```

Both must show `active` before proceeding.

### 4. Create System Isolation Layer

```bash
mkdir -p ~/lingfeng-system/{lpmo,skills,gateway-ha,scripts,config}
cp -r ~/.hermes/memory/*       ~/lingfeng-system/lpmo/
cp -r ~/.hermes/gateway-ha/*   ~/lingfeng-system/gateway-ha/ 2>/dev/null || \
cp -r ~/.hermes/memory/gateway-ha/* ~/lingfeng-system/gateway-ha/

# Link skills (still lives in ~/.hermes/skills for Hermes compat)
ln -sf ~/.hermes/skills ~/lingfeng-system/skills
```

### 5. Version Skills with Git

```bash
cd ~/.hermes/skills
git init
git config user.email "lingfeng@local"
git config user.name "Lingfeng"

# Create .gitignore for temp files
cat > .gitignore << 'EOF'
__pycache__/
*.pyc
node_modules/
*.log
.env
*.key
*.pem
EOF

git add -A
git commit -m "feat: init skills repo"
```

### 6. Push to GitHub

**Pitfall**: On headless NixOS, HTTPS push fails with X11 askpass error.

```bash
# This FAILS on headless NixOS:
# git push https://github.com/user/repo.git
# Error: unable to read askpass response from '/nix/store/.../x11-ssh-askpass'

# Fix: use SSH instead
git remote add origin git@github.com:lingfeng-xiao/lingfeng-skills.git
git push -u origin main
```

Requires `~/.ssh/id_ed25519` (or other key) to be configured with GitHub.

### 7. Cleanup Old Backups

Only after verifying Gateway and HA Monitor are still active:

```bash
rm -rf ~/.hermes/sessions.old ~/.hermes/state.db.old \
  ~/.hermes/checkpoints.old ~/.hermes/memories.old \
  ~/.hermes/english-diary.old ~/.hermes/weixin.old \
  ~/.hermes/logs.old ~/.hermes/cache.old
```

## Recovery (Reinstall Scenario)

```bash
# 1. Reinstall Hermes
# 2. Clone skills
git clone git@github.com:lingfeng-xiao/lingfeng-skills.git ~/.hermes/skills

# 3. Run install script to link system layer
~/lingfeng-system/scripts/install.sh

# 4. Ensure Hermes config points Data paths to ~/.hermes-data/
```

## Key Pitfalls

| Pitfall | Prevention |
|---|---|
| Gateway crashes after symlink | Copy first, symlink second; verify before cleanup |
| HTTPS git push fails headless | Always use SSH (`git@github.com:...`) on headless NixOS |
| Skills not found after reinstall | Skills MUST stay at `~/.hermes/skills/` — link from there, not move |
| Data path confusion | Only sessions/checkpoints/logs/cache are Data; skills are System |
