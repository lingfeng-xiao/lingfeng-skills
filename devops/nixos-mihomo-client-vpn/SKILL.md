---
name: nixos-mihomo-client-vpn
description: Deploy mihomo (Clash.Meta) as a headless transparent proxy client on NixOS + Hyprland/Wayland. Replaces FLClash or other GUI clients. Sets up TUN mode, DNS hijack, systemd user service, and NixOS capabilities.
---

# NixOS Mihomo Client VPN

Deploy mihomo as a headless system-wide transparent proxy on NixOS with TUN mode. No GUI needed.

## When to Use

- User wants to replace FLClash/ClashVerge GUI with a headless solution
- NixOS desktop (Hyprland, GNOME, KDE, etc.) needs global transparent proxy
- TUN mode not working due to permission issues
- DNS pollution causing sites to fail even though proxy port responds

## Core Architecture

```
All apps → TUN device (Meta) → mihomo → proxy nodes
DNS queries → 127.0.0.1:53 (mihomo) → fake-ip → TUN → proxy
```

## Prerequisites

- Valid Clash-format YAML config with proxies and rules
- NixOS with flakes enabled
- User in `networkmanager` group

## NixOS System Configuration

Add to `configuration.nix`:

```nix
# 1. Install mihomo
environment.systemPackages = with pkgs; [ mihomo ];

# 2. Grant TUN + bind-port capabilities
security.wrappers.mihomo = {
  setuid = false;
  setgid = false;
  owner = "root";
  group = "root";
  capabilities = "cap_net_admin,cap_net_bind_service+ep";
  source = "${pkgs.mihomo}/bin/mihomo";
};

# 3. Insert local DNS before router DNS (fallback preserved)
networking.networkmanager.insertNameservers = [ "127.0.0.1" ];
```

Rebuild:
```bash
sudo nixos-rebuild switch --flake /etc/nixos#nixos
```

If cache downloads fail due to proxy issues, rebuild through the proxy port:
```bash
sudo http_proxy=http://127.0.0.1:7890 https_proxy=http://127.0.0.1:7890 nixos-rebuild switch --flake /etc/nixos#nixos
```

## Mihomo Config

Place at `~/.config/mihomo/config.yaml`. Start from existing Clash config, then add/modify:

```yaml
mixed-port: 7890
allow-lan: false
mode: rule
log-level: info

tun:
  enable: true
  stack: mixed          # system stack has unreliable DNS hijack
  dns-hijack:
    - "any:53"
  auto-route: true
  auto-redirect: true
  auto-detect-interface: true
  strict-route: true    # critical: forces DNS into TUN

dns:
  enable: true
  listen: 127.0.0.1:53  # serve DNS locally; requires cap_net_bind_service
  ipv6: false
  enhanced-mode: fake-ip
  fake-ip-range: 198.18.0.1/16
  default-nameserver: [223.5.5.5, 119.29.29.29]
  nameserver: ['https://doh.pub/dns-query', 'https://dns.alidns.com/dns-query']
  # ... rest of existing DNS config

# Keep existing proxies, proxy-groups, rules from Clash config
```

## Systemd User Service

`~/.config/systemd/user/mihomo.service`:

```ini
[Unit]
Description=Mihomo proxy daemon
After=network.target

[Service]
Type=simple
ExecStart=/run/wrappers/bin/mihomo -d /home/%u/.config/mihomo
Restart=on-failure
RestartSec=5

[Install]
WantedBy=default.target
```

Enable and start:
```bash
systemctl --user daemon-reload
systemctl --user enable mihomo
systemctl --user start mihomo
```

## Verification Checklist

1. **Process running**: `systemctl --user status mihomo`
2. **TUN device exists**: `ip addr show | grep Meta`
3. **Port 7890 listening**: `ss -tlnp | grep 7890`
4. **DNS listening**: `ss -ulnp | grep "127.0.0.1:53"`
5. **resolv.conf has local first**: `cat /etc/resolv.conf` → `nameserver 127.0.0.1`
6. **Google works**: `curl -I https://www.google.com`
7. **No DNS pollution**: `curl -v http://www.google.com` should resolve to `198.18.x.x` fake-ip range, not real polluted IPs

## Pitfalls & Lessons Learned

| Problem | Cause | Fix |
|---------|-------|-----|
| TUN device not created | Missing `cap_net_admin` | `security.wrappers.mihomo` with capability |
| DNS still polluted | `dns-hijack` alone unreliable; DNS bypasses TUN | Add `strict-route: true` + `dns.listen: 127.0.0.1:53` |
| mihomo can't bind port 53 | Privileged port | Add `cap_net_bind_service` to wrapper |
| `system` stack DNS leak | system stack doesn't intercept glibc DNS properly | Use `stack: mixed` or `gvisor` |
| NixOS rebuild fails | Can't reach cache | `sudo http_proxy=http://127.0.0.1:7890 nixos-rebuild switch ...` |

## Switching Proxies (No GUI)

Mihomo REST API on `127.0.0.1:9091`:

```bash
# List proxies
curl -s http://127.0.0.1:9091/proxies | python3 -m json.tool | less

# Switch selector node
curl -X PUT http://127.0.0.1:9091/proxies/节点选择 \
  -H "Content-Type: application/json" \
  -d '{"name":"🇯🇵 日本1-VIP88"}'
```

## Troubleshooting Node Issues

### Diagnose which node is actually being used

```bash
journalctl --user -u mihomo -n 30
```

Look for log lines like:
```
[TCP] 198.18.0.1:12345 --> github.com:443 match GeoSite(github) using 🌍国外媒体[🇭🇰 香港4h]
```

The `[🇭🇰 香港4h]` part shows the **final resolved node**, not the group selection. If this node is broken for your target site, switch it.

### Test nodes for a specific site (e.g. GitHub)

If no `external-controller` is configured, add it temporarily:

```yaml
# In ~/.config/mihomo/config.yaml, near the top
external-controller: 127.0.0.1:9090
```

Restart mihomo, then test each candidate node:

```bash
# Switch a selector group to a specific node
curl -s -X PUT http://127.0.0.1:9090/proxies/🌍国外媒体 \
  -H "Content-Type: application/json" \
  -d '{"name":"🇺🇸 美国01h-0.5倍率"}'

# Test target site through the proxy
curl -s -o /dev/null -w "%{http_code} %{time_total}s" \
  --max-time 10 --proxy http://127.0.0.1:7890 https://github.com
```

Repeat for several nodes. Pick the one with the fastest, most reliable responses.

### Fix auto-select picking the wrong node

Subscription configs often set `♻️自动选择` (url-test) to test against `https://cp.cloudflare.com` with an interval of `86400` (24 hours). This causes two problems:

1. **Wrong target**: A node fast to Cloudflare may be completely broken for GitHub, AI APIs, or streaming.
2. **No recovery**: A 24-hour interval means a bad node stays selected all day.

Fix by editing `~/.config/mihomo/config.yaml`:

```yaml
  - name: ♻️自动选择
    type: url-test
    url: https://github.com          # Test the actual site you care about
    interval: 300                     # Re-test every 5 minutes
    tolerance: 50                     # Optional: only switch if delta > 50ms
    proxies:
      - ...
```

Then restart mihomo. Auto-select will now pick the best node **for your actual traffic** and recover quickly if a node degrades.

**Note:** If you need multiple sites to perform well (GitHub, YouTube, AI APIs), consider creating **separate url-test groups** for each target URL, rather than relying on a single Cloudflare test.

### When to hardcode vs auto-select

| Scenario | Recommendation |
|----------|---------------|
| General browsing | `♻️自动选择` with `https://www.google.com` |
| GitHub / Git operations | `♻️自动选择` with `https://github.com` |
| AI APIs (OpenAI, Anthropic) | Dedicated `url-test` with `https://api.openai.com` or hardcode a known-good US node |
| Streaming | Dedicated `url-test` with the streaming service URL |
| Node marked "不保证可用" | Do not hardcode; let url-test validate it continuously |

## Migrating from FLClash

1. Copy FLClash profile: `cp ~/.local/share/com.follow.clash/profiles/*.yaml ~/.config/mihomo/config.yaml`
2. Add `tun` and `dns.listen` blocks as shown above
3. Stop FLClash: `pkill -f FlClash`
4. Start mihomo service
5. Optionally remove flclash from `home.nix` and rebuild
