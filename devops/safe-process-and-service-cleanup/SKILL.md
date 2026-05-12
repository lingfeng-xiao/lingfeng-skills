---
name: safe-process-and-service-cleanup
description: Safely remove unwanted Linux processes, services, and installed artifacts without accidentally killing your own cleanup command.
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [linux, process, cleanup, systemd, apt, ops]
---

# Safe Process and Service Cleanup

Use this when the user wants one or more processes fully removed along with related services, packages, and on-disk artifacts.

## When to use

- The user identifies unwanted long-running processes by PID or executable path
- You need to remove both user-space daemons and system services
- You need to clean files after killing processes
- You need to avoid self-inflicted termination during process matching

## Core workflow

### 1. Confirm what each process is
Use short inspection commands first:

```bash
ps -p <pid1>,<pid2> -o pid,ppid,user,args --cols 240
readlink -f /proc/<pid>/cwd
tr '\0' ' ' < /proc/<pid>/cmdline
systemctl status <service> --no-pager | head
systemctl --user list-units --type=service --all --no-pager | grep -Ei '<name>' || true
systemctl list-units --type=service --all --no-pager | grep -Ei '<name>' || true
```

Also inspect likely install paths and directory sizes:

```bash
du -sh /path/a /path/b 2>/dev/null
```

### 2. Separate user processes from system services
Handle them in this order:

1. User-space processes and their home-directory artifacts
2. systemd unit disable/remove
3. Package purge and privileged data cleanup
4. Final verification

This reduces surprises and keeps failures localized.

### 3. Kill user processes safely
**Important pitfall:** do **not** casually use `pkill -f 'pattern'` when the pattern also appears in the cleanup command string. It can kill the shell running your command and abort the cleanup.

Preferred order:

```bash
kill -9 <exact_pid1> <exact_pid2> || true
```

If more descendants exist, re-check with `ps` and only then kill exact remaining PIDs.

Avoid broad `pkill -f` unless the pattern cannot match the current command line.

### 4. Remove user-space artifacts
After the process is confirmed dead:

```bash
rm -rf /home/<user>/.app-dir /home/<user>/runtime-dir /home/<user>/project-dir
```

### 5. Disable and remove systemd services
For system services:

```bash
sudo systemctl disable --now <service>.service
sudo rm -f /etc/systemd/system/<service>.service
sudo systemctl daemon-reload
```

For package-managed services (example: MySQL), disable first, then purge packages.

### 6. Purge packages and data
Example pattern:

```bash
sudo apt-get -y purge <pkg1> <pkg2> ...
sudo rm -rf /var/lib/<name> /etc/<name> /var/log/<name> /var/log/<name>*
sudo systemctl daemon-reload
```

Expect `debconf` warnings in non-interactive shells during purge; they are usually harmless if the purge succeeds.

### 7. Verify cleanup
Always verify all three layers:

```bash
ps -ef | grep -E '<pattern1>|<pattern2>' | grep -v grep || true
systemctl status <service> --no-pager 2>/dev/null | head -n 8 || true
for p in /path/a /path/b /path/c; do [ -e "$p" ] && echo EXISTS:$p || echo REMOVED:$p; done
```

## Proven findings from experience

- `pkill -f` can match the cleanup command itself and kill the running shell; prefer exact PIDs.
- Long destructive cleanups are safer when broken into small steps with verification after each step.
- A service can already be inactive while a related runtime process or install directory still remains; check both process table and filesystem.
- For MySQL removal, purge packages **and** explicitly remove `/var/lib/mysql` and `/etc/mysql` if the user wants complete cleanup.

## Reporting format

Good final report structure:

1. What was removed (processes, services, packages, directories)
2. What was verified gone
3. Optional next cleanup step such as `sudo apt autoremove`

## Success criteria

- Target processes are no longer running
- Related services are stopped/disabled or removed
- Requested directories/data are gone
- Verification confirms no obvious residual process or service remains
