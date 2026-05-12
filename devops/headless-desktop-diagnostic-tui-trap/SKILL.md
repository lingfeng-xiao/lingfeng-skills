---
name: headless-desktop-diagnostic-tui-trap
description: |
  When remotely diagnosing Linux desktop environments (Hyprland, Sway, etc.) via terminal/SSH,
  avoid the trap of launching interactive TUI programs (fuzzel, rofi, dmenu, fzf) that open
  graphical windows and block for input. Learn to recognize when "phantom" popups are actually
  your own diagnostic commands, and how to safely terminate them without triggering retry loops.
triggers:
  - Diagnosing GUI/desktop issues on a remote or AI-agent-managed Linux system
  - Seeing "mystery popups" or "windows that won't close" during remote debugging
  - Using terminal tools to test launchers, menus, or interactive CLI tools on a desktop session
  - Working with NixOS + Hyprland/Sway where dmenu/fuzzel/rofi are common
related_skills:
  - nixos-hyprland-config-compatibility-debug
  - safe-process-and-service-cleanup
---

# Headless Desktop Diagnostic: The Interactive TUI Trap

## The Problem

When you run an interactive TUI program via `terminal()` or SSH on a machine with an active graphical session, the program **will open a real window** on the user's screen and **block forever** waiting for input.

Common traps:
- `echo "a\nb" | fuzzel --dmenu`  → opens a dmenu window, blocks for selection
- `rofi -show drun`                → opens rofi launcher, blocks
- `fzf`                            → opens fzf TUI, blocks
- `vim`, `less`, `top`             → may fail or behave oddly without a real TTY

If you run multiple diagnostic commands involving these tools, you leave **multiple stacked windows** on the user's screen. The user sees "a box that keeps popping up" — but it's actually your own commands.

## Why `kill -9` Makes It Worse

If the system (or the AI agent framework) has automatic retry logic for failed tool calls, killing the process with `SIGKILL` causes a non-zero exit code. The system detects the failure and **retries the same command**, spawning a new instance.

**Result:** You kill one popup, another immediately replaces it. It feels like a "virus" or infinite loop.

## Detection: Is It Your Own Trap?

Check for these signs:

1. **Process tree shows your command:**
   ```bash
   ps aux | grep -E "(fuzzel|rofi|dmenu|fzf)"
   ```
   Look for command lines containing strings YOU typed (e.g., `test1`, `test2`).

2. **Parent PID traces back to the agent:**
   ```bash
   ps -o pid,ppid,args -p <PID>
   ```
   If the parent is `claude`, `hermes`, `python`, or a shell snapshot (`/home/user/.claude/shell-snapshots/...`), it's your own command.

3. **Window/Layer inspection:**
   ```bash
   # Hyprland
   hyprctl layers
   hyprctl clients
   
   # Sway
   swaymsg -t get_tree
   ```
   Look for layers with namespace `launcher` or similar.

4. **Journal shows repeated spawns:**
   ```bash
   journalctl --user -n 100 | grep -E "(fuzzel|rofi|dmenu)"
   ```

## Safe Cleanup

### Method 1: Let It Exit Naturally (Best)

Send the expected input so the program exits with code 0:

```bash
# Use wtype (Wayland) or xdotool (X11) to send Enter/Escape
wtype -k Return        # selects first item, exits 0
wtype -k Escape        # cancels, may exit non-zero — use with caution
```

**Caveat:** The window must have focus. For layer-shell clients (fuzzel dmenu mode), focus may not work via standard window managers.

### Method 2: Kill the Entire Process Chain

Kill fuzzel **and** all parent shells in one shot, then verify no retry occurs:

```bash
# Kill all related processes (including shells that launched them)
pkill -9 -f "fuzzel --match-mode"
pkill -9 -f "echo -e .*fuzzel"

# Wait and verify
sleep 2
pgrep -x fuzzel | wc -l   # should be 0
```

If the count keeps going back up, you have a **retry loop**.

### Method 3: Break the Retry Loop

If the agent framework is auto-retrying the failed command:

1. **Stop executing ANY commands that reference the tool.** Even `grep fuzzel` in `ps` is safe, but don't run new instances.
2. **Identify and satisfy the pending tool call.** Find the original command the agent is retrying and let it complete naturally.
3. **If the tool call is stuck in the agent's queue:** You may need to acknowledge to the user that the diagnostic command is stuck, and ask them to manually dismiss the window (press Escape or Enter).

## Prevention Rules

1. **Never use interactive TUI tools for remote diagnostics.**
   - ❌ `echo "a\nb" | fuzzel --dmenu`
   - ❌ `rofi -show drun`
   - ❌ `fzf < file.txt`
   - ✅ `cat file.txt | head`  
   - ✅ `which fuzzel && fuzzel --version`  
   - ✅ `command -v fuzzel >/dev/null && echo "installed"`

2. **If you must test a launcher, use a non-interactive check:**
   ```bash
   # Check binary exists and is executable
   test -x "$(which fuzzel)" && echo "OK" || echo "MISSING"
   
   # Check config syntax without launching
   fuzzel --check-config 2>&1 || true
   ```

3. **Always use `timeout` for any potentially blocking command:**
   ```bash
   timeout 2 fuzzel --dmenu < /dev/null || true
   ```
   This ensures the command exits after 2 seconds even if it blocks.

4. **Verify process count before and after:**
   ```bash
   BEFORE=$(pgrep -x fuzzel | wc -l)
   # ... run your diagnostic ...
   AFTER=$(pgrep -x fuzzel | wc -l)
   ```
   If `AFTER > BEFORE`, you leaked a process.

## Special Case: NixOS + Hyprland + Fuzzel

On NixOS with end-4/illogical-impulse or similar rices:
- `fuzzel` is often used as the app launcher replacement for `rofi`
- It may be launched by keybinds, by quickshell components, or by systemd services
- Its dmenu mode (`--dmenu`) creates a **layer-shell surface**, not a regular XDG window
  - Does NOT appear in `hyprctl clients` (use `hyprctl layers` instead)
  - Does NOT have a regular `class` or `title` for `hyprctl dispatch focuswindow`
  - PID may show as `-1` in `hyprctl layers` if the process died uncleanly

## Verification Checklist

After cleanup, run this full verification:

```bash
echo "=== Processes ==="
pgrep -a fuzzel || echo "No fuzzel processes"

echo "=== Layers ==="
hyprctl layers 2>/dev/null | grep -c "namespace" || echo "0 layers"

echo "=== Windows ==="
hyprctl clients 2>/dev/null | grep -c "class:" || echo "0 windows"

echo "=== Recent Journal ==="
journalctl --user --since "1 minute ago" --no-pager 2>/dev/null | grep -c "fuzzel" || echo "0 journal entries"
```

All counts should be stable at 0 (or only pre-existing baseline values).