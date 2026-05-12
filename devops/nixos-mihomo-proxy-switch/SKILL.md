---
name: nixos-mihomo-proxy-switch
description: Diagnose and switch Mihomo (Clash.Meta) proxy nodes on NixOS for stable access to specific sites like GitHub, Google, etc.
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [NixOS, Mihomo, Clash, Proxy, VPN, Node-Switch]
    related_skills: [nixos-mihomo-client-vpn]
---

# NixOS Mihomo 代理节点切换 Skill

针对 NixOS + Mihomo (Clash.Meta) 环境，诊断代理连通性问题并切换到最稳定的节点。

## 环境假设

- Mihomo 配置文件: `~/.config/mihomo/config.yaml`
- systemd user service: `mihomo.service`
- 监听端口: `mixed-port: 7890` (HTTP/SOCKS5 混合代理)
- 无 external-controller 时需要先添加

## 工作流程

### 1. 诊断当前状态

```bash
# 检查 mihomo 是否运行
systemctl --user status mihomo
pgrep -a mihomo

# 查看当前活跃节点 (从日志推断)
journalctl --user -u mihomo -n 30 | grep -E "github|google|Match"

# 通过代理测试目标站点连通性
curl -s -o /dev/null -w "%{http_code} %{time_total}s" --max-time 15 \
  --proxy http://127.0.0.1:7890 https://github.com
```

### 2. 启用 external-controller (如未配置)

如果 config.yaml 中没有 `external-controller`，必须先添加才能动态切换节点：

```bash
# 在 mixed-port 下方添加
sed -i '/^mixed-port: /a external-controller: 127.0.0.1:9090' ~/.config/mihomo/config.yaml
systemctl --user restart mihomo
```

### 3. 列出可用节点

```bash
# 获取代理组信息
curl -s http://127.0.0.1:9090/proxies | python3 -m json.tool

# 获取特定组 (如 🌍国外媒体)
curl -s http://127.0.0.1:9090/proxies/🌍国外媒体 | python3 -m json.tool
```

### 4. 批量测试节点

使用 API 逐个切换节点并测试目标站点：

```bash
test_node() {
  local group="$1"   # e.g. 🌍国外媒体
  local node="$2"
  local target="${3:-https://github.com}"
  
  curl -s -X PUT "http://127.0.0.1:9090/proxies/$group" \
    -H "Content-Type: application/json" -d "{\"name\":\"$node\"}" > /dev/null 2>&1
  sleep 1
  curl -s -o /dev/null -w "%{http_code} %{time_total}s" --max-time 10 \
    --proxy http://127.0.0.1:7890 "$target" 2>&1
}

# 示例
test_node "🌍国外媒体" "🇺🇸 美国01h-0.5倍率" "https://github.com"
```

### 5. 选择最优节点

根据测试结果选择：
- HTTP 200 + 时间最短
- 避免名称含 "不保证可用" 的节点作为长期选择（可临时使用）
- 优先选择地理位置近的节点（新加坡/日本/韩国/美国西海岸）

### 6. 持久化配置

API 切换在重启后会丢失。推荐两种持久化方案：

#### 方案 A: 修改 url-test 测试目标

将 `♻️自动选择` 的测试 URL 改为实际要访问的站点：

```yaml
# config.yaml
- name: ♻️自动选择
  type: url-test
  url: https://github.com      # 从 cloudflare 改为目标站点
  interval: 300                # 从 86400 改为 5 分钟
```

#### 方案 B: 固定默认节点

修改 `select` 类型组的 proxies 顺序，将目标节点放在第一位：

```yaml
- name: 🌍国外媒体
  type: select
  proxies:
    - 🇺🇸 美国01h-0.5倍率   # 放在第一位作为默认
    - 🔰节点选择
    - ...
```

修改后重启：
```bash
systemctl --user restart mihomo
```

## 常用 API 参考

| 操作 | curl 命令 |
|------|----------|
| 查看所有代理 | `GET /proxies` |
| 查看组详情 | `GET /proxies/{group}` |
| 切换节点 | `PUT /proxies/{group}` body: `{"name":"node"}` |
| 测试延迟 | `GET /proxies/{name}/delay?url=...&timeout=5000` |

## 注意事项

1. **订阅覆盖**: 如果 config.yaml 是订阅自动生成的，修改会被覆盖。建议：
   - 使用订阅转换工具的 `custom` 模板功能
   - 或在订阅更新脚本后自动追加修改

2. **TUN 模式**: 本环境使用 TUN 模式 (`tun.enable: true`)，curl 需显式指定 `--proxy http://127.0.0.1:7890` 才能测试特定节点。系统其他流量走 TUN 自动分流。

3. **日志查看**: `journalctl --user -u mihomo -f` 可实时查看流量匹配和节点选择

4. **多目标测试**: 如果用户说 "Google 不稳定"，将测试 URL 改为 `https://www.google.com`；说 "Claude 不稳定" 改为 `https://claude.ai`
