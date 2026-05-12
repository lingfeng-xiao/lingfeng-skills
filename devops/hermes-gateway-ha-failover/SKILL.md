---
name: hermes-gateway-ha-failover
description: Hermes Gateway 主备故障切换架构 — 本地主节点 + 远程冷备，单账号 iLink 约束下的自动 failover 与手动 failback
version: 1.0.0
author: Hermes Agent
metadata:
  hermes:
    tags: [gateway, ha, failover, weixin, ilink, systemd]
---

# Hermes Gateway HA Failover

## 适用场景

- 本地机器（NixOS/Desktop）运行 Hermes Gateway 处理微信
- 远程服务器（Ubuntu/Headless）作为备份节点
- **只有一个微信账号** — 无法双开
- 要求：本地挂了自动切到服务器，本地恢复后手动切回

## 核心约束（iLink / Hermes）

| 约束 | 影响 |
|------|------|
| **One poller per token** | 同一微信 token 不能同时有两个活跃连接 |
| **35s long-poll** | iLink 长轮询超时约 35 秒 |
| **Session linger 5-10min** | TCP 断开后 iLink session 仍保留 5-10 分钟 |
| **errcode=-14** | iLink session 过期需重新 `gateway setup` 扫码 |
| **禁止前台 `gateway run`** | Headless 环境只能用 systemd 短命令 |

## 架构：单账号冷切换（Route B）

```
Local (MASTER)                 Remote (STANDBY)
┌────────────────────┐      ┌────────────────────┐
│ Gateway (微信+飞书)        │      │ Gateway (飞书运行)            │
│ Health Daemon → systemd    │      │ 微信 token 已同步但未启用     │
│ 每 30s 检测                │      │ 等待接管指令                  │
└────────────────────┘      └────────────────────┘
```

## 实施步骤

### 1. 探测两端现状

```bash
# 本地
systemctl --user status hermes-gateway --no-pager
ls ~/.hermes/weixin/accounts/
cat ~/.hermes/weixin/accounts/*.json | grep user_id

# 远程
ssh {remote} "systemctl --user status hermes-gateway --no-pager"
ssh {remote} "ls ~/.hermes/weixin/accounts/ 2>/dev/null || echo 'no weixin'"
ssh {remote} "cat ~/.hermes/weixin/accounts/*.json 2>/dev/null | grep user_id"
ssh {remote} "journalctl --user -u hermes-gateway -n 5 --no-pager 2>&1 | grep -i weixin"
```

**关键发现判断**：
- 远程已有同 `user_id` 的 token 文件 → 曾经登录过，可能 session 过期
  - ⚠️ 注意：远程 token 的 `hash` 可能与本地不同（如 `d134acc9c271` vs `551d0d27a43a`），说明是历史 session。必须同步最新的 token 文件
- 远程无 token → 需要同步本地 token 过去
- 远程日志含 "Session expired" → failover 后可能需要重新扫码
- 检查 `~/.hermes/pairing/weixin-approved.json` — 包含已批准的 user_id，若缺失则需重新扫码授权

### 2. 同步微信 Token

**同步所有相关文件** (不仅仅是 .json)：
```bash
rsync -az ~/.hermes/weixin/accounts/{hash}@im.bot* {remote}:~/.hermes/weixin/accounts/
```

Token 文件包含（三个一组）：
- `{hash}@im.bot.json` — token + base_url + user_id + saved_at
- `{hash}@im.bot.sync.json` — 同步状态
- `{hash}@im.bot.context-tokens.json` — context tokens

**实战发现**：如果远程已有旧 token（不同 hash），需要确保覆盖或同步最新版。否则 failover 时远程可能使用过期 token 导致连接失败。

### 3. 确保远程 systemd + linger

```bash
ssh {remote} "sudo loginctl enable-linger {username}"
ssh {remote} "hermes gateway install"   # 若未安装
ssh {remote} "systemctl --user daemon-reload"
```

### 4. 部署 Health Daemon（本地）

目录：`~/.hermes/memory/gateway-ha/`

**config.json**:
```json
{
  "local": {
    "gateway_service": "hermes-gateway",
    "check_interval_sec": 30,
    "consecutive_failures": 3,
    "restart_attempts": 2,
    "restart_cooldown_sec": 10
  },
  "remote": {
    "host": "jd",
    "ssh_port": 2222,
    "gateway_service": "hermes-gateway",
    "ilink_timeout_sec": 420
  },
  "notification": {
    "enabled": true,
    "command": "notify-send"
  }
}
```

**health-local.js** 核心逻辑：
```javascript
// 状态机：MASTER / STANDBY
if (state.mode === 'MASTER') {
  if (isGatewayActive()) {
    // 健康，重置失败计数
    state.failCount = 0;
    return;
  }
  
  // 不健康
  state.failCount++;
  
  // 先尝试本地 restart
  if (state.failCount < CONSECUTIVE_FAILURES) {
    if (restartLocal()) return;
  }
  
  // 连续失败超限 → Failover
  stopLocal();
  setTimeout(() => {
    startRemote();      // SSH restart remote
    state.mode = 'STANDBY';
  }, ILINK_TIMEOUT_MS); // 7 分钟
}
```

**systemd service** (`~/.config/systemd/user/hermes-gateway-ha.service`):
```ini
[Unit]
Description=Hermes Gateway HA Monitor
After=hermes-gateway.service

[Service]
Type=simple
ExecStart=%h/.hermes/memory/gateway-ha/health-local.js --daemon
Restart=always
RestartSec=10

[Install]
WantedBy=default.target
```

启用：
```bash
systemctl --user daemon-reload
systemctl --user enable --now hermes-gateway-ha
```

### 5. Failback 脚本（手动）

```bash
node ~/.hermes/memory/gateway-ha/failback.js
```

逻辑：
1. SSH 停止远程 Gateway
2. 等待 7 分钟（iLink 超时）
3. 启动本地 Gateway
4. 状态 → MASTER

**实战调试技巧**：
- 初始脚本可能没有周期性打印日志，需要手动添加检测日志：`console.log(`Check: gateway active=${healthy}, failCount=${state.failCount}`)`
- State 文件（`.ha-state.json`）只在第一次状态变化时创建，启动时不会创建
- 使用 `journalctl --user -u hermes-gateway-ha -f` 实时观察

### 6. 验证

```bash
# 查看 HA monitor 日志
journalctl --user -u hermes-gateway-ha -f

# 模拟故障（测试时）
systemctl --user stop hermes-gateway
# 等待 3 次检测（90s）+ 7 分钟超时
# 观察远程是否自动启动
```

## 路由决策树

```
是否有小号？
    ├── 是 → Route A: 双并行（主备同时在线，瞬时切换）
    └── 否 → Route B: 单账号冷切换（本地挂了才启动远程，7分钟延迟）
```

## 风险与应对

| 风险 | 概率 | 应对 |
|------|------|------|
| iLink session 过期 | 中 | Failover 后可能需要远程执行 `hermes gateway setup` 重新扫码 |
| Token 绑定设备/IP | 低 | 复制 token 文件通常可跨设备使用 |
| 7 分钟窗口内消息丢失 | 高 | 冷切换固有成本，微信消息不会丢失但 AI 无法实时响应 |
| 两端同时判定对方故障 | 低 | 状态文件明确区分 MASTER/STANDBY，不会双启 |

## 相关 Skill

- `hermes-gateway-headless-ops` — 无头服务器短命令管理
- `hermes-gateway-weixin-troubleshooting` — 微信平台故障排查
