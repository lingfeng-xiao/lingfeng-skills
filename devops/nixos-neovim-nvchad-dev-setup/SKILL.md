---
name: "nixos-neovim-nvchad-dev-setup"
title: "Set up Neovim + NvChad + LSP on NixOS"
description: "Configure Neovim with NvChad starter, language servers (TypeScript, Python, Java), formatters, and run keymaps on NixOS via declarative system packages"
triggers:
  - "install neovim nixos"
  - "setup nvchad"
  - "configure neovim lsp"
  - "nvim typescript python java"
  - "neovim 开发环境"
  - "配置 nvchad"
---

# Neovim + NvChad + LSP on NixOS

## Context
User wants a complete Neovim development environment on NixOS with NvChad starter, LSP support, formatting, and code running. Prefer system-level declarative tool installation over Mason (which can have FHS issues on NixOS).

## Prerequisites
- NixOS with `/etc/nixos/configuration.nix`
- NvChad starter already cloned to `~/.config/nvim` (or install it first)

## Steps

### 1. Install dev toolchains via NixOS system config

Add to `environment.systemPackages` in `/etc/nixos/configuration.nix`:

```nix
environment.systemPackages = with pkgs; [
  # Core
  neovim git gcc nodejs unzip

  # TypeScript / JavaScript
  typescript
  typescript-language-server
  prettier

  # Python
  pyright
  ruff

  # Java
  jdk
  jdt-language-server
  google-java-format

  # Telescope / utils
  ripgrep fd
];
```

> **CRITICAL**: `nodePackages.*` has been removed from recent nixpkgs. Use top-level names like `typescript-language-server` and `prettier`, NOT `nodePackages.typescript-language-server`.

Run `sudo nixos-rebuild switch`.

### 2. Configure LSP servers (`~/.config/nvim/lua/configs/lspconfig.lua`)

NvChad starter uses Neovim 0.11+'s `vim.lsp.enable()` API.

```lua
require("nvchad.configs.lspconfig").defaults()

local servers = { "html", "cssls", "ts_ls", "pyright" }
vim.lsp.enable(servers)

-- jdtls needs a root_dir fallback for single-file mode
local util = require("lspconfig.util")
vim.lsp.config("jdtls", {
  root_dir = function(bufnr, on_dir)
    local fname = vim.api.nvim_buf_get_name(bufnr)
    local root = util.root_pattern("pom.xml", "build.gradle", "build.gradle.kts", ".git")(fname)
    on_dir(root or vim.fn.getcwd())
  end,
})
vim.lsp.enable("jdtls")
```

### 3. Configure formatting (`~/.config/nvim/lua/configs/conform.lua`)

```lua
local options = {
  formatters_by_ft = {
    lua = { "stylua" },
    javascript = { "prettier" },
    typescript = { "prettier" },
    javascriptreact = { "prettier" },
    typescriptreact = { "prettier" },
    python = { "ruff_format" },
    java = { "google-java-format" },
  },
  format_on_save = {
    timeout_ms = 500,
    lsp_fallback = true,
  },
}
return options
```

### 4. Update plugins (`~/.config/nvim/lua/plugins/init.lua`)

```lua
return {
  {
    "stevearc/conform.nvim",
    event = "BufWritePre",
    opts = require "configs.conform",
  },
  {
    "neovim/nvim-lspconfig",
    config = function()
      require "configs.lspconfig"
    end,
  },
  {
    "nvim-treesitter/nvim-treesitter",
    opts = {
      ensure_installed = {
        "vim", "lua", "vimdoc",
        "html", "css",
        "javascript", "typescript", "tsx",
        "python", "java",
      },
    },
  },
}
```

### 5. Add run keymaps (`~/.config/nvim/lua/mappings.lua`)

```lua
require "nvchad.mappings"
local map = vim.keymap.set

map("n", "<leader>rp", function()
  vim.cmd("vsplit | terminal python3 " .. vim.fn.expand("%:p"))
end, { desc = "Run Python file" })

map("n", "<leader>rt", function()
  vim.cmd("vsplit | terminal npx ts-node " .. vim.fn.expand("%:p"))
end, { desc = "Run TypeScript file" })

map("n", "<leader>rj", function()
  vim.cmd("vsplit | terminal java " .. vim.fn.expand("%:p"))
end, { desc = "Run Java file" })
```

### 6. Sync plugins

```bash
nvim --headless "+Lazy! sync" +qa
```

## Verification

Test LSP in headless mode:
```bash
nvim --headless -c "lua require('lspconfig')" -c "edit test.py" -c "sleep 3" \
  -c "lua local cs=vim.lsp.get_clients({bufnr=0}); print(#cs..' clients'); for _,c in ipairs(cs) do print(c.name) end" \
  -c "qa!"
```

Expected: `1 clients` + `pyright` (or `ts_ls`, `jdtls` for other filetypes).

## Pitfalls

- **nodePackages removed**: Recent nixpkgs removed the `nodePackages` namespace. Use `typescript-language-server`, `prettier` directly.
- **Mason on NixOS**: Mason-downloaded binaries often fail on NixOS due to missing FHS paths. Prefer system packages for LSP servers and formatters.
- **vim.lsp.enable() requires lspconfig loaded first**: `vim.lsp.config.ts_ls` is nil until `require('lspconfig')` runs. In normal interactive use this happens automatically; in headless tests you must preload it.
- **jdtls root_dir**: Without a fallback, jdtls won't start for single `.java` files outside a Maven/Gradle project. Always add `root or vim.fn.getcwd()` fallback.
- **treesitter parsers**: `ensure_installed` works but parsers compile on first open. Ensure `gcc` is in system packages.

## Customization

To add another language:
1. Install its LSP/formatter via NixOS `environment.systemPackages`
2. Add server name to `servers` table in `lspconfig.lua`
3. Add formatter to `formatters_by_ft` in `conform.lua`
4. Add filetype/treesitter parser to `ensure_installed`