---
name: "nixos-oh-my-zsh-setup"
title: "Configure Oh My Zsh on NixOS"
description: "Set up Oh My Zsh with zsh-autosuggestions and syntax highlighting on NixOS via system-level declarative configuration"
triggers:
  - "configure oh my zsh"
  - "setup oh-my-zsh"
  - "install oh my zsh nixos"
  - "配置 oh-my-zsh"
  - "zsh 配置"
---

# Oh My Zsh on NixOS

## Context
User wants oh-my-zsh configured on NixOS. Prefer system-level declarative configuration via `/etc/nixos/configuration.nix`. Only fall back to user-level manual install if system config is unavailable.

## Steps

1. **Inspect environment**: Check current shell (`echo $SHELL`), whether zsh/git are installed, and if home-manager exists.
2. **Check home-manager**: Look for `~/.config/home-manager/home.nix` or `~/.config/nixpkgs/home.nix`.
3. **System configuration** (preferred if no home-manager):
   - Read `/etc/nixos/configuration.nix` to understand structure (imports, users, existing packages).
   - Set the user's shell: `users.users.<username>.shell = pkgs.zsh;`
   - Add the `programs.zsh` block:
     ```nix
     programs.zsh = {
       enable = true;
       autosuggestions.enable = true;
       syntaxHighlighting.enable = true;
       ohMyZsh = {
         enable = true;
         theme = "robbyrussell";
         plugins = [ "git" "sudo" "z" "command-not-found" ];
       };
     };
     ```
   - Add `git` to `environment.systemPackages` if not present.
   - Run `sudo nixos-rebuild switch`.
4. **User-level fallback** (if system config is unavailable):
   - Use `nix-shell -p zsh git curl` to get temporary tools.
   - Run the official install script: `sh -c "$(curl -fsSL https://raw.githubusercontent.com/ohmyzsh/ohmyzsh/master/tools/install.sh)"`
   - Configure `~/.zshrc` manually.
   - User must run `chsh -s $(which zsh)` separately (requires sudo).
5. **Conflict resolution** (after OMZ install on NixOS with `programs.zsh`):
   - NixOS's `programs.zsh.ohMyZsh.enable = true` does NOT install OMZ; it uses a minimal OMZ from nixpkgs that lacks `zsh-autosuggestions` and `zsh-syntax-highlighting`.
   - OMZ's `oh-my-zsh.sh` overwrites `fpath`, breaking NixOS plugin loading.
   - **Manual fix**: In `~/.zshrc`, after `source $ZSH/oh-my-zsh.sh`, restore NixOS `fpath` and source NixOS-managed plugins:
     ```zsh
     plugins=(git sudo z command-not-found)
     source $ZSH/oh-my-zsh.sh
     # Restore NixOS fpath (OMZ overwrites it)
     for p in ${=NIX_PROFILES}; do
         fpath=($p/share/zsh/site-functions $p/share/zsh/$ZSH_VERSION/functions $p/share/zsh/vendor-completions $fpath)
     done
     autoload -U compinit && compinit
     # Source NixOS-managed plugins (store paths from /etc/zshrc)
     source /nix/store/CR7F9FMB.../share/zsh-autosuggestions/zsh-autosuggestions.zsh
     export ZSH_AUTOSUGGEST_HIGHLIGHT_STYLE="fg=8"
     export ZSH_AUTOSUGGEST_STRATEGY=(history)
     source /nix/store/0X13ZRQ.../share/zsh-syntax-highlighting/zsh-syntax-highlighting.zsh
     ZSH_HIGHLIGHT_HIGHLIGHTERS=(main)
     eval "$(dircolors -b)"
     ```
   - The store paths change after `nixos-rebuild switch`; update them accordingly, or symlink to a stable path.

## 工程化方案 (home-manager 统一管理)

在有 home-manager 的 NixOS 系统上，正确做法是由 home-manager 全权管理 zsh，**不要手动安装 OMZ**。

### 架构说明

- **NixOS 配置层** (`configuration.nix`): 只保留 `programs.zsh.enable = true` 和 `users.users.<name>.shell = pkgs.zsh`（满足 NixOS 断言检查）
- **Home-manager 配置层** (`home.nix`): 配置 `programs.zsh` 的所有子选项（oh-my-zsh、autosuggestion、syntaxHighlighting）
- **OMZ 安装方式**: home-manager 通过 `programs.zsh.oh-my-zsh.enable = true` 将 OMZ 作为 nix store 包引用（`${pkgs.oh-my-zsh}/share/oh-my-zsh`），**不需要也不应该**手动运行 OMZ 安装脚本
- **插件管理**: `autosuggestion` 和 `syntaxHighlighting` 是 home-manager 的独立子选项，与 oh-my-zsh 的 plugins 互不冲突

### home.nix 配置示例

```nix
programs.zsh = {
  enable = true;
  enableCompletion = true;
  defaultKeymap = "emacs";

  oh-my-zsh = {
    enable = true;
    theme = "robbyrussell";
    plugins = [
      "git" "sudo" "z" "command-not-found" "autojump"
    ];
  };

  autosuggestion = {
    enable = true;
    strategy = [ "history" ];
  };

  syntaxHighlighting = {
    enable = true;
    highlighters = [ "main" ];
  };
};

# autojump 供 OMZ 的 z 插件使用
home.packages = with pkgs; [ autojump ];
```

### configuration.nix 最小配置

```nix
users.users.<name> = {
  shell = pkgs.zsh;
  # ...
};

programs.zsh.enable = true;  # 只保留这一行，具体配置在 home.nix
```

### 关键陷阱

- NixOS 的 `programs.zsh` 和 home-manager 的 `programs.zsh` 会冲突。两选一：用 home-manager 接管 zsh，删除 `configuration.nix` 中的 `programs.zsh` block（只保留 `enable = true`）
- OMZ 安装脚本（`sh -c "$(curl -fsSL .../install.sh)"`）在 NixOS 上**不应该**运行，它会创建 `~/.oh-my-zsh` 目录，与 home-manager 的 nix store 路径冲突
- `programs.zsh.autosuggestion.strategy` 是列表类型：`strategy = [ "history" ]`，不是 `implementation`
- OMZ 的 `z` 插件需要 `autojump` 包，否则命令找不到

## Pitfalls

- The `patch` tool refuses to write to `/etc/nixos/configuration.nix` (sensitive path). Use `sudo sed -i` or `sudo tee` instead.
- `zsh-autosuggestions` and `zsh-syntax-highlighting` should be enabled via `programs.zsh.autosuggestions.enable` and `programs.zsh.syntaxHighlighting.enable`, not as oh-my-zsh plugins.
- External oh-my-zsh plugins (outside the main oh-my-zsh repo) need special handling via `programs.zsh.ohMyZsh.customPkgs` or manual `~/.zshrc` additions.
- Popular themes: `robbyrussell` (default), `agnoster`, `powerlevel10k` (requires extra package).
- NixOS's OMZ (nixpkgs) does NOT include autosuggestions/syntax-highlighting — these come from separate nixpkgs packages and are sourced via `/etc/zshrc` (run `sudo nixos-rebuild switch` to regenerate store paths).
- Use `${=NIX_PROFILES}` (with `=`) for word splitting, NOT `${(z)NIX_PROFILES}` — the `(z)` flag does not work in `~/.zshrc` context.