---
name: hermes-gateway-headless-ops
description: 在无头服务器（headless）环境下管理 Hermes Gateway 的约束驱动工作流 — 不运行前台常驻命令，只用短命令诊断，通过 systemd 用户服务管理生命周期
version: 1.0.0
author: Hermes Agent Setup
license: MIT
metadata:
  hermes:
    tags: [gateway, ops, headless, systemd]
---

# Hermes Gateway Headless Ops

## 核心约束

1. **禁止运行前台常驻命令**：`hermes gateway run` 绝对禁止
2. **只使用短命令**：`gateway status` / `stop` / `start` / `restart`
3. **两阶段执行**：先文件修复，再服务验证，阶段间输出结果
4. **不得自行安装**：如果服务未安装，停止并报告，不尝试 `gateway run` 顶上

## 生命周期命令（优先级顺序）

### 第一步：检查状态
```bash
hermes -p {profile} gateway status
```
- 输出 `Gateway is not running` → 进行下一步
- 输出 `running` → 无需操作

### 第二步：尝试 restart
```bash
hermes -p {profile} gateway restart
```
- 如果成功 → 验证完成
- 如果失败（如 linger 未启用）→ 进行下一步

### 第三步：stop + start
```bash
hermes -p {profile} gateway stop
hermes -p {profile} gateway start
```
- 如果 `start` 失败，报 `Unit hermes-gateway-{profile}.service not found` → 说明从未安装

### 第四步：报告用户需手工执行
服务未安装时，报告以下内容让用户自行执行：
```bash
# 1. 启用 linger（一次性）
sudo loginctl enable-linger {username}

# 2. 安装服务
hermes -p {profile} gateway install

# 3. 启动
hermes -p {profile} gateway start
```

## 服务未安装的诊断流程

```
gateway status
    ↓
✗ Gateway is not running
    ↓
gateway restart
    ↓
⚠ Cannot restart — linger is not enabled
    ↓
gateway stop  (确保干净)
    ↓
gateway start
    ↓
✗ Unit hermes-gateway-{profile}.service not found
    ↓
→ 服务从未安装，报告用户手工执行 install
```

## 常见错误对照

| 错误信息 | 含义 | 处理 |
|---------|------|------|
| `Gateway is not running` | 服务未运行 | 执行 restart 或 start |
| `Cannot restart gateway as a service — linger is not enabled` | linger 未开，无法管理用户服务 | 用户执行 `sudo loginctl enable-linger` |
| `Unit hermes-gateway-{profile}.service not found` | 服务未安装 | 用户执行 `gateway install` |
| `✗ Stopped gateway for this profile` | stop 成功 | 继续 start |
| `Failed to start: ... returned non-zero` | start 失败 | 检查服务是否安装 |
| `sudo: hermes: command not found` | 用 sudo 执行时 PATH 不包含 venv 中的 `hermes` | 改用绝对路径，例如 `sudo /path/to/venv/bin/hermes gateway uninstall --system` |

## 双服务清理（保留 user service）

当 `hermes gateway status` 提示 **Both user and system gateway services are installed** 时：

1. 先确认 user service 正在运行：
```bash
hermes gateway status
systemctl --user status hermes-gateway --no-pager
```
2. 卸载 system service，保留 user service：
```bash
sudo /absolute/path/to/venv/bin/hermes gateway uninstall --system
```
3. 再次验证：
```bash
hermes gateway status
systemctl --user show hermes-gateway --property=ActiveEnterTimestamp,ExecMainPID --no-pager
systemctl status hermes-gateway --no-pager || true
```
4. 成功标志：
   - `✓ User gateway service is running`
   - system 级 `systemctl status hermes-gateway` 返回 `Unit hermes-gateway.service could not be found.`

注意：不要为了解决双服务问题去运行前台 `hermes gateway run`。仍然坚持只用短命令和 systemd 生命周期管理。

## 两阶段执行模板

### 阶段 A：文件修复
- 只做文件编辑、key 轮换、文档修正
- 禁止启动任何进程
- 完成后输出修改文件清单

### 阶段 B：短命令验证
- 只执行 `status` / `restart` / `stop` / `start`
- 如果服务未安装，报告并停止
- 给出用户需手工执行的命令

### 模板报告格式

```
## 阶段 A 结果
修改的文件 | 新 key 脱敏值 | 文档修正情况

## 阶段 B 结果
Gateway 状态 | 未能启动原因 | 用户下一步命令
```

## 已废弃 profile 说明

如果历史文档中出现 `boss-chat` profile，将其视为废弃配置，不应继续修复或安装。优先清理残留文件与过时引用，并以当前默认 gateway 配置为准。
