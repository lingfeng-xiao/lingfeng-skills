---
name: nixos-hermes-desktop-notifications
description: Configure desktop notifications for Hermes Agent tasks on NixOS + Hyprland + foot terminal. Covers single-shot task notifications, interactive TUI bell hints, and Gateway messaging.
triggers:
  - User wants notifications when Hermes completes tasks
  - NixOS + Hyprland + foot terminal setup
  - hermes-notify wrapper
version: 1.0.0
---

# NixOS Hermes 桌面通知集成

## 目标

让用户在 Hermes 单次任务或交互式 TUI 中，完成任务后能收到桌面通知（弹窗 + 声音 + 窗口 urgent），即使切到了其他 workspace。

## 系统前提

- NixOS + home-manager
- Hyprland (Wayland)
- foot 终端
- swaync (或 dunst/mako) 通知守护进程
- PipeWire (`pw-play`)
- Hermes 安装在 `~/.hermes/hermes-agent/venv/`

## 方案 1：单次任务通知（最可靠）

适用于明确、独立的任务，不需要追问。

### NixOS 配置

```nix
# modules/home/shell.nix 或类似位置
let
  hermesNotify = pkgs.writeShellApplication {
    name = "hermes-notify";
    runtimeInputs = [ pkgs.libnotify pkgs.pipewire ];
    text = ''
      TITLE=''${1:-"Hermes 任务"}
      shift || true
      
      notify-send "🚀 $TITLE" "开始执行..." -a "Hermes" -t 3000
      # 关键：非交互式环境必须设置 HERMES_TUI=0，否则 Ink TUI 会报错
      HERMES_TUI=0 ${config.home.homeDirectory}/.hermes/hermes-agent/venv/bin/hermes "$@"
      CODE=$?
      
      if [ $CODE -eq 0 ]; then
        notify-send "✨ $TITLE" "任务完成！" -a "Hermes"
        printf '\a'
      else
        notify-send "⚠️ $TITLE" "失败 (exit $CODE)" -a "Hermes" -i dialog-warning
        printf '\a'
      fi
      
      exit $CODE
    '';
  };
in {
  home.packages = [ hermesNotify ];
  
  programs.zsh.shellAliases = {
    hn = "hermes-notify";
  };
}
```

### 用法

```bash
hn "分析代码" chat -q "分析 ~/project 并输出报告"
```

效果：完成后有 notify-send 弹窗 + pw-play 声音 + foot urgent（通过 `\a` 触发）。

## 方案 2：交互式 TUI 的 bell 提示（已知局限）

适用于实时对话，但用户偶尔切走。**这是交互式 TUI 不改源码能做到的极限。**

### 为什么交互式 TUI 无法自动弹窗

Hermes 的 agent loop 架构决定了：当 assistant 给出纯文本回复（无 tool_calls）时，会话立即结束。即使通过 skill 强制要求 AI 在最终回复中附带 terminal 调用来发通知，AI 也不会可靠执行——它会认为任务已完成，无需额外操作。

**实际验证**：`notify-on-complete` skill 被创建并测试，确认 AI 无法在最终回复后可靠地自我触发通知。这是架构限制，不是配置问题。

### Hermes 配置

在 Hermes 配置文件的 display 区域设置：
```yaml
display:
  bell_on_complete: true
```

### foot 配置

```ini
# ~/nix-config/desktop/theme/foot/foot.ini
[bell]
urgent=yes
notify=no
```

效果：每次 hermes 回复完成后发送 `\a`，foot 触发 Hyprland urgent，waybar 上 foot 图标闪烁。
**局限：只在 waybar 上闪，切 workspace 后完全看不见，没有弹窗，没有声音。**

## 方案 3：Gateway 消息平台（最干净）

Hermes Gateway 已配置飞书/Discord/Telegram 时，每条回复本身就是消息通知。

### 查看 Gateway 状态

```bash
hermes gateway status
```

## 不推荐的方案

| 方案 | 为什么不推荐 |
|------|-------------|
| 改 hermes 源码 | NixOS 上维护麻烦，更新会冲突 |
| Skill 强制 AI 发通知 | AI 行为不可控，不可靠 |
| `bell_on_complete` 单独使用 | 没有弹窗，切 workspace 无效 |

## 决策树

```
需要切走 + 任务明确独立 → 方案 1: hn 单次模式
需要切走 + 要追问多轮   → 方案 3: Gateway 消息平台
守在屏幕前偶尔切走     → 方案 2: bell_on_complete
```

## 已知陷阱

1. **`hermes chat -q` 默认会启动 TUI（Ink）**：非交互式环境会报错 `Raw mode is not supported`。wrapper 中必须设置 `HERMES_TUI=0`。
2. **home-manager 重建时可能因现有 systemd service 文件冲突而失败**：删除冲突文件后重试。
3. **foot 的 `bell=urgent` 默认已启用**，显式配置更保险。
4. **单次模式不能追问**：复杂任务通常需要多轮修改，单次模式只适合目标明确的独立任务。
