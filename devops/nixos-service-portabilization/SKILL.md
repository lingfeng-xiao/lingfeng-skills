---
name: nixos-service-portabilization
title: NixOS Service Portabilization
description: Convert NixOS/systemd-bound local services into pure Node.js, cross-platform, migratable projects with zero external dependencies.
triggers:
  - User wants to migrate a NixOS-local service to a server
  - User mentions systemd is not portable
  - User needs disaster recovery / server migration capability
  - User wants to remove NixOS-specific hardcoded paths
  - User wants to run service on non-NixOS machines
  - "server expired, need to migrate back"
  - "make it portable"
  - "remove systemd dependency"
---

# NixOS Service Portabilization

## Goal
Transform a NixOS-local, systemd-managed service into a self-contained, cross-platform Node.js project that can run on any Linux/macOS/WSL machine with only Node.js installed.

## Context
NixOS services typically have these portability traps:
- **systemd timers/services** — only work on Linux with systemd
- **Nix store paths** — hardcoded `/nix/store/...` paths break on non-NixOS
- **NixOS packages** — services like Ollama managed via `home.packages` + `systemd.user.services`
- **No version control** — code scattered in home directory without Git

## Steps

### 1. Audit System Bindings
Search for NixOS-specific dependencies in the codebase:
```bash
grep -r "nix/store" . 2>/dev/null
grep -r "systemctl" . 2>/dev/null
grep -r "ollama serve" . 2>/dev/null
```

Common binding points:
- `find /nix/store -maxdepth 1 -name '*sqlite-vec*'` in JS files
- `systemd.user.services.*` in `~/nix-config/modules/home/*.nix`
- External services (Ollama, PostgreSQL, Redis) declared in NixOS config

### 2. Replace systemd with Pure Node.js Scheduler

Create `scheduler.js` that uses `setTimeout`/`setInterval` for cron-like scheduling:

```javascript
#!/usr/bin/env node
const { spawn } = require('child_process');
const fs = require('fs');
const path = require('path');

function schedule(name, cronExpr, taskFn) {
  // Parse "0 3 * * *" → daily at 03:00
  // Parse "0 8 * * 1" → weekly Monday at 08:00
  const [min, hour, dom, month, dow] = cronExpr.split(/\s+/).map(Number);
  
  function getNext() {
    const now = new Date();
    let next = new Date(now);
    next.setHours(hour, min, 0, 0);
    if (!isNaN(dow)) {
      const daysUntil = (dow - next.getDay() + 7) % 7;
      next.setDate(next.getDate() + daysUntil);
      if (next <= now) next.setDate(next.getDate() + 7);
    } else {
      if (next <= now) next.setDate(next.getDate() + 1);
    }
    return next;
  }
  
  function loop() {
    const next = getNext();
    setTimeout(() => {
      taskFn().catch(e => console.error(e)).finally(loop);
    }, next - Date.now());
  }
  loop();
}
```

Start with: `nohup node scheduler.js > /dev/null 2>&1 &`

### 3. Create Cross-Platform Adapter

Write `lib/platform.js` to handle platform-specific resources:

```javascript
const { execSync } = require('child_process');
const fs = require('fs');
const path = require('path');

function getResourcePath(name, nixPattern, nixFallback) {
  // 1. Check bundled ./lib/ or ./
  const bundled = path.join(__dirname, '..', name);
  if (fs.existsSync(bundled)) return bundled;
  
  // 2. Check NixOS store
  try {
    const out = execSync(`find /nix/store -maxdepth 1 -name "${nixPattern}" ! -name "*.drv" | head -1`).toString().trim();
    if (out) {
      const p = path.join(out, nixFallback);
      if (fs.existsSync(p)) return p;
    }
  } catch (e) {}
  
  // 3. Check system paths
  const systemPaths = [
    `/usr/lib/${name}`,
    `/usr/local/lib/${name}`,
    `/opt/${name}`,
  ];
  for (const p of systemPaths) {
    if (fs.existsSync(p)) return p;
  }
  
  return null;
}
```

### 4. Batch Replace Hardcoded Paths

**Do NOT rely on regex batch replacement.** Files often have slightly different formatting (different variable names, comment styles, error handling). Regex substitution frequently fails silently or partially.

**Recommended approach: per-file `patch` tool**

For each file (e.g., `daemon.js`, `init.js`, `sediment.js`, `recall.js`, `batch-sediment.js`, `backfill-vectors.js`), use the `patch` tool with exact `old_string` / `new_string`:

```javascript
// Old pattern (remove this entire block):
function loadSqliteVec(database) {
  const fs = require('fs');
  const { execSync } = require('child_process');
  let vecPath = process.env.SQLITE_VEC_PATH;
  if (!vecPath || !fs.existsSync(vecPath)) {
    try {
      const out = execSync('find /nix/store -maxdepth 1 -name "*sqlite-vec-0.1.6" ! -name "*.drv" | head -1').toString().trim();
      if (out) vecPath = `${out}/lib/vec0.so`;
    } catch (e) {}
  }
  if (!vecPath || !fs.existsSync(vecPath)) {
    vecPath = '/nix/store/.../lib/vec0.so';  // hardcoded fallback
  }
  if (fs.existsSync(vecPath)) {
    database.loadExtension(vecPath);
  } else {
    console.error('sqlite-vec extension not found.');
  }
}
loadSqliteVec(db);

// New pattern (replace with):
const { loadSqliteVec } = require('./lib/platform.js');
if (!loadSqliteVec(db)) {
  console.warn('⚠️  sqlite-vec not found. Vector features unavailable (FTS5 still works).');
}
```

Use `search_files` to find all files containing `sqlite-vec` or `/nix/store`, then patch each individually. Verify each patch succeeds before moving to the next.

### 5. Remove External Service Dependencies

If the service depends on Ollama/PostgreSQL/Redis:
- Switch to a pure-local fallback (e.g., FTS5 instead of vector embeddings)
- Make the external service optional via `.env` configuration
- Comment out the external service in `.env`, set `DEFAULT_BACKEND=fts5`

Example `.env`:
```
# Pure local fallback - zero external dependencies
DEFAULT_BACKEND=fts5

# Optional external backends (enable when available)
# OLLAMA_URL=http://localhost:11434
# KIMI_API_KEY=sk-xxx
```

### 6. Clean NixOS Configuration

Edit `~/nix-config/modules/home/<service>.nix`:
- Remove all `systemd.user.services.*`
- Remove all `systemd.user.timers.*`
- Remove external service packages (e.g., `ollama`)
- Keep only the shared library package if still useful (e.g., `sqlite-vec`)
- Add a comment explaining the service is now self-managed

Then rebuild NixOS. In interactive sessions:
```bash
cd ~/nix-config && sudo nixos-rebuild switch --flake .
```

In non-interactive / automated contexts (e.g., from a script), pipe the password:
```bash
cd ~/nix-config && echo "$SUDO_PASSWORD" | sudo -S nixos-rebuild switch --flake .
```
(Note: only use this in trusted, local automation where the password is already known.)

### 7. Write Migration Scripts

**`deploy.sh`** — sync to remote server:
```bash
#!/bin/bash
TARGET="${1:-user@server}"
rsync -az --delete \
  --exclude='node_modules' --exclude='*.log' --exclude='*.pid' \
  --exclude='*.wal' --exclude='*.shm' --exclude='lingfeng.db' \
  ./ "${TARGET}:~/.hermes/memory/"
ssh "${TARGET}" 'bash -s' < ./setup.sh
```

**`setup.sh`** — run on target machine:
```bash
#!/bin/bash
set -e
cd "$(dirname "$0")"

echo "Setting up..."

# Check Node.js
if ! command -v node &> /dev/null; then
  echo "Node.js not found. Please install Node.js 18+."
  exit 1
fi
NODE_VER=$(node --version | cut -d'v' -f2 | cut -d'.' -f1)
if [ "$NODE_VER" -lt 18 ]; then
  echo "Node.js $(node --version) too old. Need 18+."
  exit 1
fi

# Install dependencies
npm install --production 2>/dev/null || npm install

# Optional: download native extensions for non-NixOS
if [ ! -f "./vec0.so" ] && [ ! -d "/nix/store" ]; then
  ARCH=$(uname -m)
  case "$ARCH" in
    x86_64)
      URL="https://github.com/asg017/sqlite-vec/releases/download/v0.1.6/sqlite-vec-0.1.6-linux-x86_64.tar.gz"
      ;;
    aarch64)
      URL="https://github.com/asg017/sqlite-vec/releases/download/v0.1.6/sqlite-vec-0.1.6-linux-aarch64.tar.gz"
      ;;
    *)
      echo "Unknown arch $ARCH, skipping sqlite-vec (FTS5 still works)"
      URL=""
      ;;
  esac

  if [ -n "$URL" ]; then
    curl -sL "$URL" | tar -xz -O "vec0.so" > vec0.so.tmp && mv vec0.so.tmp vec0.so || {
      echo "Failed to download sqlite-vec. FTS5 mode will work fine."
      rm -f vec0.so.tmp
    }
  fi
fi

chmod +x *.js
```

### 8. Initialize Git Repository

```bash
cd <project-dir>
git init

# Write .gitignore
cat > .gitignore << 'EOF'
node_modules/
package-lock.json
.env
.env.local
*.log
*.pid
*.wal
*.shm
lingfeng.db
.DS_Store
Thumbs.db
EOF

# Write package.json with scripts
# Write README.md
# Commit
git add -A
git commit -m "feat: portable architecture"
```

### 9. Push to GitHub

**Option A: Manual (user creates repo)**
User creates empty repo on GitHub, then:
```bash
git remote add origin git@github.com:<user>/<repo>.git
git push -u origin main
```

**Option B: Automated (user provides GitHub PAT)**
If user provides a GitHub Personal Access Token, automate creation:
```bash
# Create repo via GitHub API
REPO_NAME="my-service"
PAT="ghp_xxx"  # from user

curl -s -X POST "https://api.github.com/user/repos" \
  -H "Authorization: token $PAT" \
  -H "Accept: application/vnd.github.v3+json" \
  -d "{\"name\":\"$REPO_NAME\",\"private\":true}"

# Add remote and push
git remote add origin "https://$PAT@github.com/<user>/$REPO_NAME.git"
git push -u origin main
```

**Option C: Use `gh` CLI (if available)**
```bash
gh repo create <user>/<repo> --private --source=. --push
```

## Pitfalls

| Trap | Solution |
|------|----------|
| `better-sqlite3` native module fails on target | Run `npm rebuild` or `npm install` on target machine |
| `sqlite-vec` .so not found on Ubuntu/Debian | Download from GitHub releases in `setup.sh` |
| `.env` with secrets committed | Add `.env` to `.gitignore`, provide `.env.example` |
| Database file `lingfeng.db` committed | Add to `.gitignore`, sync via `rsync` or backup script |
| Old systemd services still running | `systemctl --user stop <service>` and rebuild NixOS |
| `gh auth login` fails in headless | Must use device flow or web browser; cannot fully automate |
| Ollama still running after removal | `systemctl --user stop ollama` or `pkill ollama` |

## Verification Checklist

- [ ] `node daemon.js stats` works without errors
- [ ] `node scheduler.js` starts and logs next execution times
- [ ] No `/nix/store` references remain in JS files
- [ ] `.env` has `DEFAULT_BACKEND=fts5` or local fallback
- [ ] NixOS rebuild succeeds with no systemd services for this project
- [ ] `deploy.sh` and `setup.sh` are executable (`chmod +x`)
- [ ] Git repository initialized with proper `.gitignore`
