---
name: baota-panel-headless-ops
title: Baota Panel (宝塔面板) Headless Operations
description: Retrieve login credentials, reset passwords, and perform common administrative tasks on Baota Panel via CLI when GUI access is unavailable.
tags: [baota, bt-panel, linux, server-admin, credentials]
---

# Baota Panel Headless Operations

## Retrieving Login Credentials

When `bt default` masks the password (shows `********`), the actual credentials are stored in panel data files.

### Step-by-step

1. **Try `bt default` first** (may show masked password after initial setup):
   ```bash
   sudo bt default
   ```
   - Note the `username` and panel URL/port.
   - If password is masked, proceed to step 2.

2. **Read the actual password from `a_pass.pl`**:
   ```bash
   sudo cat /www/server/panel/data/a_pass.pl
   ```
   - This file contains the current plaintext password.

3. **Read the custom admin path from `admin_path.pl`**:
   ```bash
   sudo cat /www/server/panel/data/admin_path.pl
   ```
   - Append this to the panel URL (e.g., `https://IP:PORT/8c9f32fd`).

4. **Do NOT rely solely on the SQLite database**:
   ```bash
   sudo python3 -c "import sqlite3; conn = sqlite3.connect('/www/server/panel/data/default.db'); c = conn.cursor(); c.execute('SELECT username,password FROM users'); print(c.fetchall())"
   ```
   - The `default.db` often contains stale initial credentials (`admin` / `21232f297a57a5a743894a0e4a801fc3`).
   - The active username shown by `bt default` may differ from the DB record.

### Pitfalls
- **Permission denied**: All panel data files require root. Always use `sudo`.
- **Masked password**: `bt default` only reveals the initial password before the first login. After that, it masks the password—use `a_pass.pl` instead.
- **Port access**: If the panel URL uses a non-standard port (e.g., `24148`), ensure the server's security group/firewall allows inbound traffic on that port.

## Resetting Password

If you need to change the password:
```bash
sudo bt 5
```
Follow the interactive prompts.

## Common bt Command References

| Command | Action |
|---------|--------|
| `bt` | Enter Baota CLI menu |
| `bt default` | Show panel URL, username, password |
| `bt 5` | Modify panel password |
| `bt 10` | View panel logs |
| `bt 11` | Clear panel cache |
| `bt 12` | Cancel domain binding |
| `bt 13` | Cancel IP access restriction |
| `bt 14` | View panel info |
| `bt 16` | Repair panel |
| `bt 22` | Cancel SSL |
| `bt 23` | Turn off SSL |

## Key File Locations

| File | Purpose |
|------|---------|
| `/www/server/panel/data/a_pass.pl` | Current plaintext password |
| `/www/server/panel/data/admin_path.pl` | Custom secure login path suffix |
| `/www/server/panel/data/default.db` | SQLite DB (often stale; do not trust for current creds) |
| `/www/server/panel/data/port.pl` | Panel port number |
| `/www/server/panel/data/domain.conf` | Bound domain config |
| `/www/server/panel/data/ipv6.pl` | IPv6 status |
