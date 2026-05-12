---
name: nixos-home-file-desktop-entry
description: 在 NixOS home-manager 中创建用户桌面入口 (.desktop file)，解决应用菜单找不到已装应用的问题
---

# NixOS home-manager: 创建用户桌面入口 (.desktop file)

## 场景
系统已通过 `programs.steam.enable = true` 等方式安装了应用，但应用菜单找不到。需要通过 home-manager 将系统级的 `.desktop` 文件链接到用户目录。

## 方法

### ✅ 正确做法：使用 `.text` 写入内容
```nix
home.file = {
  ".local/share/applications/steam.desktop".text = ''
    [Desktop Entry]
    Name=Steam
    Exec=steam %U
    Icon=steam
    Terminal=false
    Type=Application
    Categories=Network;FileTransfer;Game;
  '';
};
```

### ❌ 错误做法：使用 `.source` 引用绝对路径
```nix
# 这样在 flakes pure evaluation mode 下会报错：
# "access to absolute path '/run/current-system/...' is forbidden in pure evaluation mode"
home.file = {
  ".local/share/applications/steam.desktop".source = /run/current-system/sw/share/applications/steam.desktop;
};
```

## 原因
 flakes 构建时使用纯评估模式 (pure evaluation)，不允许引用当前运行系统的绝对路径。

## 生效
```bash
sudo nixos-rebuild switch --flake /etc/nixos
```

## 验证
```bash
ls -la ~/.local/share/applications/steam.desktop
cat ~/.local/share/applications/steam.desktop
```

## 相关经验
- 系统级 `.desktop` 文件通常在 `/run/current-system/sw/share/applications/`
- 可以 `cat /run/current-system/sw/share/applications/<app>.desktop` 查看完整内容
- 如果应用通过 home.packages 安装，桌面入口通常自动可用（不需要手动加）
