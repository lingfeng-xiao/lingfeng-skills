---
name: nixos-steam-gaming-proxy-optimization
description: Optimize Mihomo/Clash proxy configuration for Steam multiplayer gaming on NixOS — reduce latency, enable P2P direct connections, and handle cross-platform friends using different VPN tools.
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [NixOS, Mihomo, Steam, Gaming, Proxy, VPN, P2P]
    related_skills: [nixos-mihomo-proxy-switch]
---

# NixOS Steam 游戏联机代理优化

针对 NixOS + Mihomo (Clash.Meta) + Hyprland 环境下，Steam 游戏联机的代理优化。

## 核心问题

**你和朋友各自用不同的代理工具时，Steam 联机质量会很差。** 原因：
- 你用 mihomo (Linux)，朋友用雷神/UU 等加速器 (Windows)
- 两人出口节点不同 → Steam 匹配到不同地区服务器 → 被迫走中继 relay（延迟叠加）
- 杀戮尖塔这类游戏默认使用 Steam P2P 网络，如果两人不在同一出口，Steam 会启用 relay

**解法原则：让双方都走同一条隧道（同一节点）或都直连同一个地区。**

## 工作流程

### 1. 确认游戏进程名

游戏进程名不等于游戏目录名。通过 mihomo 日志确认：
```bash
journalctl --user -u mihomo -n 100 | grep -E "SlayTheSpire|游戏名"
```
日志格式：`[UDP] 198.18.0.1:xxxxx(SlayTheSpire2, uid=1000) --> 155.133.xxx:27017`
→ 进程名是 `SlayTheSpire2`

杀软/加速器进程也这样确认。

### 2. 分析当前流量路径

```bash
# 查看游戏流量的实际走向
journalctl --user -u mihomo -n 200 | grep -E "SlayTheSpire|steamserver|27017|Match"

# 查看游戏匹配的代理组
curl -s http://127.0.0.1:9090/proxies | python3 -c "
import json,sys
d = json.load(sys.stdin)
# 找包含游戏节点的组
for k,v in d['proxies'].items():
    if isinstance(v,dict) and 'all' in v:
        all_nodes = v.get('all',[])
        if any('香港' in n or '日本' in n or '游戏' in n for n in all_nodes):
            print(k, '-> now:', v.get('now'), 'type:', v.get('type'))
"
```

### 3. Steam 游戏流量直连方案（推荐）

如果和朋友都直连同一个地区 Steam 服务器（香港/东京），延迟最低。

在 `~/.config/mihomo/config.yaml` 的 `PROCESS-NAME` 规则区添加：
```yaml
 - PROCESS-NAME,SlayTheSpire2,DIRECT
```

TUN 模式下 `PROCESS-NAME` 规则会拦截该进程的 **所有 TCP + UDP 流量**，无需关心端口和域名。

重启生效：
```bash
systemctl --user restart mihomo
```

验证：
```bash
sleep 3 && journalctl --user -u mihomo -n 30 | grep -E "SlayTheSpire|DIRECT"
# 应该看到游戏流量匹配 DIRECT
```

### 4. 同节点方案（朋友也用 mihomo 时）

如果朋友也愿意换成 mihomo，双方连接到同一个节点（如同为香港节点）：

```bash
# 锁节点
curl -s -X PUT "http://127.0.0.1:9090/proxies/🔰节点选择" \
  -H "Content-Type: application/json" \
  -d '{"name":"🇭🇰 香港5h"}' > /dev/null 2>&1

# 确认
curl -s http://127.0.0.1:9090/proxies/🔰节点选择 | python3 -c \
  "import json,sys; d=json.load(sys.stdin); print('🔰节点选择 now:', d.get('now'))"
```

### 5. 诊断游戏流量匹配路径

Steam 游戏流量的典型日志：
```
[UDP] 198.18.0.1:38157(SlayTheSpire2) --> 155.133.244.52:27017 match Match using 🐟境外网站[🇭🇰 香港7h]
```

说明：
- `Match` = 被通用规则匹配（非域名/GeoIP）
- `155.133.x.x` = Steam 服务器 IP 段
- 流量走了 🐟境外网站 组

如果看到 `DIRECT`：
```
[TCP] 198.18.0.1:35533 --> cmp1-hkg1.steamserver.net:27018 match GeoSite(steam@cn) using 🧱国内网址[DIRECT]
```
→ Steam 服务器被识别为中国站点（steam@cn），已直连

## 常见游戏进程名参考

| 游戏 | 进程名 |
|------|--------|
| 杀戮尖塔2 | `SlayTheSpire2` |
| 绝区零 | 待确认 |
| 其他 | 通过日志 `journalctl --user -u mihomo -n 500 | grep game` 查找 |

## 注意事项

1. **Steam 游戏流量端口**：UDP 27015/27017/27018/27100/27131/27132 等，TCP 443/27036 等。
   依赖域名/端口分流不可靠（Steam 服务器 IP 段多且变化），`PROCESS-NAME` 规则最可靠。

2. **Steam @cn vs steam**：订阅分流规则中 `GEOSITE,steam@cn` 匹配的是中国节点段，
   `GEOSITE,steam` 或 `DOMAIN-SUFFIX,steamcommunity.com` 匹配全部 Steam 域名。
   确认你的规则里这两个的顺序和优先级。

3. **TUN 模式是必须的**：没有 TUN 模式，PROCESS-NAME 规则只能拦截主动连接的 TCP，
   游戏 UDP 流量会逃逸。确认 `tun.enable: true` 在 config.yaml 中。

4. **朋友用国内加速器**：雷神/UU 加速器在中国是直连优化的，
   你这边也直连（DIRECT）同一地区 Steam 服务器时，双方都在同一地区，可以建立 P2P。
