---
name: obsidian-vault-initialization
description: Initialize a new Obsidian vault with structured directories, note templates, and pre-configured Git sync via the Obsidian Git plugin.
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [obsidian, notes, vault, git, github, sync, templates]
---

# Obsidian Vault Initialization

Use this when the user wants to create a new Obsidian vault with organized structure, templates, and GitHub auto-sync ready to go.

## When to use
- User wants a new Obsidian vault for a specific purpose (studying, work, project tracking, etc.)
- User wants Git backup/sync for an Obsidian vault
- User wants pre-configured templates and directory structure

## Vault path convention

Prefer **all lowercase** with **no spaces** for every folder and filename:

```bash
~/documents/obsidian-vault/<vault-name>/
```

Example for exam prep:
```bash
~/documents/obsidian-vault/kaoyan/
```

## Step 1: Install Obsidian (NixOS + home-manager)

Add to the home-manager configuration:

```nix
# In modules/system/lf.nix — add the option
notes.obsidian = mkOption {
  type = types.bool;
  default = false;
};

# In modules/home/apps/user.nix — install the package
++ lib.optionals cfg.apps.notes.obsidian [ pkgs.obsidian ];

# In hosts/nixos/default.nix — enable it
apps.notes.obsidian = true;
```

Then rebuild:
```bash
cd /etc/nixos  # or ~/nix-config
sudo nixos-rebuild switch --flake .#nixos
```

**Note**: `obsidian` is an Electron app. The first rebuild may need to download
Electron (~80 MB) and can take 5–15 minutes depending on network speed.
Use `background=true` with `notify_on_complete` rather than blocking polls.

## Step 2: Create directory structure

Prefer **all lowercase** with **no spaces**:

```bash
mkdir -p ~/documents/obsidian-vault/<vault-name>/{00-inbox,01-subject-a,02-subject-b,daily,templates,attachments}
```

## Step 3: Create .gitignore BEFORE git init

```bash
cd ~/documents/obsidian-vault/<vault-name>
cat > .gitignore <<'EOF'
.obsidian/workspace.json
.obsidian/workspace-mobile.json
.obsidian/app.json
.obsidian/appearance.json
.obsidian/core-plugins.json
.obsidian/graph.json
.obsidian/plugins/obsidian-git/data.json.bak
.DS_Store
Thumbs.db
*.tmp
EOF
```

## Step 4: Initialize git

```bash
git init -b main
git add .
git commit -m "init: vault initialization"
```

## Step 5: Pre-install Obsidian Git plugin

### 5.1 Download plugin files

```bash
VERSION=$(curl -s "https://api.github.com/repos/Vinzent03/obsidian-git/releases/latest" | grep '"tag_name"' | cut -d'"' -f4)
mkdir -p .obsidian/plugins/obsidian-git
cd .obsidian/plugins/obsidian-git
curl -sL -o main.js "https://github.com/Vinzent03/obsidian-git/releases/download/${VERSION}/main.js"
curl -sL -o manifest.json "https://github.com/Vinzent03/obsidian-git/releases/download/${VERSION}/manifest.json"
curl -sL -o styles.css "https://github.com/Vinzent03/obsidian-git/releases/download/${VERSION}/styles.css"
```

### 5.2 Enable and configure

```bash
cd ~/documents/obsidian-vault/<vault-name>
echo '["obsidian-git"]' > .obsidian/community-plugins.json
```

Create `.obsidian/plugins/obsidian-git/data.json` with auto-sync settings
(30-min interval, 10-sec debounce after file change, pull-on-boot, merge strategy).

## Step 6: Create starter templates and README

Create `templates/daily-review.md`, `templates/subject-note.md`, `templates/error-log.md`,
and `readme.md` describing the vault workflow.

## Step 7: Commit plugin configuration

```bash
git add .
git commit -m "feat: add obsidian-git plugin and templates"
```

## Step 8: GitHub remote setup (MCP way)

If the user already has `github-mcp-server-codex` configured (e.g. via codex),
enable the `repos` toolset and use `create_repository`:

```bash
# via mcporter (or native MCP after Hermes restart)
mcporter call --stdio 'github-mcp-server-codex --dynamic-toolsets --toolsets=default,repos stdio' \
  create_repository --args '{"name":"<repo-name>","private":true}'
```

Then configure git remote and push:

```bash
git remote add origin git@github.com:<user>/<repo>.git
git branch -M main
git push -u origin main
```

## Verification checklist

- [ ] `which obsidian` returns a path
- [ ] Vault directory exists with lowercase, no-space paths
- [ ] `.gitignore` created **before** first `git commit`
- [ ] `.obsidian/plugins/obsidian-git/` contains `main.js`, `manifest.json`, `styles.css`
- [ ] `.obsidian/community-plugins.json` lists `"obsidian-git"`
- [ ] `.obsidian/plugins/obsidian-git/data.json` has auto-sync enabled
- [ ] Git repo initialized with at least 2 commits
- [ ] GitHub remote configured with SSH
- [ ] Templates exist for common note types

## Pitfalls

1. **Build time**: Obsidian (Electron) rebuild can take 5–15 min. Do not block with short timeouts.
2. **Plugin version drift**: `data.json` config keys may change between major plugin versions.
3. **Community plugins require trust**: On first launch, Obsidian asks to trust community plugins.
4. **Git identity**: Obsidian Git uses the system's git config (`user.name` / `user.email`).
5. **SSH key permissions**: Private key must be `0600`.
6. **Workspace sync conflicts**: Always exclude `workspace.json`, `app.json`, `appearance.json`, `core-plugins.json` from git.
7. **.gitignore timing**: Create `.gitignore` BEFORE `git init && git add .`, otherwise generated files leak into the first commit.
8. **MCP toolset enablement**: `github-mcp-server-codex` requires explicitly enabling the `repos` toolset before calling `create_repository`.
