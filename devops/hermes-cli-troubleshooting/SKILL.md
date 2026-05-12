---
title: Hermes CLI Troubleshooting
name: hermes-cli-troubleshooting
description: Systematically diagnose and fix Hermes CLI agent hangs, stalls, and unresponsiveness.
triggers:
  - hermes hangs
  - hermes freezes
  - hermes stuck
  - hermes no response
  - hermes terminal timeout
  - hermes tool timeout
  - hermes CLI dead
---

# Hermes CLI Troubleshooting

## Goal
Systematically diagnose why the Hermes CLI agent appears to "hang" or become unresponsive during operation, then apply targeted fixes.

## Common Symptoms
- Hermes starts a tool call and never returns (terminal still accepts Ctrl+C)
- Long pauses during `terminal`, `execute_code`, or `browser` operations
- Agent appears "dead" but process is still running
- Multiple hermes processes visible in `ps`

## Diagnostic Steps

### 1. Check System Resources
```bash
free -h
df -h /
```
Rule out OOM (out-of-memory) or disk-full hangs.

### 2. Inspect Hermes Processes
```bash
ps aux | grep -i hermes | grep -v grep
```
**Watch for:**
- Multiple CLI instances running simultaneously (they share `state.db` and log files)
- Gateway process status (`gateway run --replace`)
- Zombie or defunct child processes

### 3. Check Recent Logs
```bash
# Errors and warnings
tail -n 100 ~/.hermes/logs/errors.log

# General activity
tail -n 100 ~/.hermes/logs/agent.log
```
**Key patterns to find:**
- `OSError: [Errno 5] Input/output error` → Terminal/PTY disconnect (common with SSH/tmux)
- `KeyboardInterrupt` → User pressed Ctrl+C during hung operation
- `content_filter` errors → API rejected request, may cause retry loops
- `TimeoutError` or `asyncio.timeout` → Explicit timeout fired

### 4. Inspect Process State
```bash
# For each hermes PID
cat /proc/<PID>/status | grep -E "(Threads|State|VmRSS)"
ls -la /proc/<PID>/fd/
```
**Watch for:**
- `Threads` count abnormally high → Possible thread leak
- `State: D` (uninterruptible sleep) → Likely I/O or NFS hang
- Multiple processes holding `state.db` open → Lock contention

### 5. Review Configuration Timeouts
```bash
cat ~/.hermes/config.yaml | grep -E "timeout|persistent_shell"
```
**Default values that commonly cause "hang" perception:**

| Config Key | Default | Recommended |
|------------|---------|-------------|
| `terminal.timeout` | 180 | 30-60 |
| `code_execution.timeout` | 300 | 60-120 |
| `gateway_timeout` | 1800 | 300-600 |
| `browser.command_timeout` | 30 | 20-30 |
| `auxiliary.web_extract.timeout` | 360 | 60-120 |

**Important:** `persistent_shell: true` means shell state accumulates across commands. A previous command that spawned a background job or modified the environment can affect later commands.

## Common Root Causes & Fixes

### Root Cause A: Timeout Too Long
**Symptom:** Tool runs for minutes before failing. User perceives "freeze".
**Fix:** Shorten timeouts in `~/.hermes/config.yaml`:
```yaml
terminal:
  timeout: 60
code_execution:
  timeout: 120
agent:
  gateway_timeout: 600
```
**Restart hermes** after changing config.

### Root Cause B: Multiple CLI Instances
**Symptom:** Intermittent lag; SQLite lock contention on `state.db`.
**Fix:** Identify and kill extra instances:
```bash
ps aux | grep "venv/bin/hermes" | grep -v grep
# Keep only the one you need; kill others
kill <PID>
```

### Root Cause C: Terminal I/O Error (SSH/tmux)
**Symptom:** Log shows `OSError: [Errno 5] Input/output error` from `prompt_toolkit`.
**Fix:**
- If running via SSH, use `tmux` or `screen` to survive disconnects
- If using tmux, avoid aggressive terminal resizing during operation

### Root Cause D: Hung Background Process in Persistent Shell
**Symptom:** Commands that used to work suddenly hang; shell state polluted.
**Fix:**
- Restart hermes to get a fresh persistent shell
- Or set `persistent_shell: false` in config to get clean shells per command

## Quick Recovery (When Currently Hung)

1. **Ctrl+C** — Cancels the current tool call; hermes resumes conversation without losing context
2. **Ctrl+\** (SIGQUIT) — Force-quit if Ctrl+C doesn't work
3. **Kill and restart** — Last resort; conversation state is preserved in `state.db`

## Prevention Checklist
- [ ] `terminal.timeout` ≤ 60s
- [ ] `code_execution.timeout` ≤ 120s
- [ ] Only one CLI instance running at a time
- [ ] Use `tmux` if running over SSH
- [ ] Review `errors.log` weekly for patterns

## Pitfalls
- **DO NOT** manually edit `state.db` or `shared_preferences.json` — this breaks startup invariants
- **DO NOT** kill the Gateway process unless you intend to restart it — it handles background cron jobs
- Timeout changes require a **full hermes restart** to take effect