---
name: configure-mihomo-proxy
description: Configure and verify the server mihomo proxy for AI tooling. Use when Codex needs to route OpenAI/ChatGPT/Codex traffic through mihomo, repair server Codex or Claude proxy access, sync proxy settings into Hermes, update mihomo rules, install Codex/Claude proxy wrappers, or diagnose proxy failures for /home/lingfeng on ssh jd.
---

# Configure Mihomo Proxy

Use this skill for the `ssh jd` server. Prefer running the bundled script instead of hand-editing proxy files.

## Operating Rules

- Do not print secrets, API keys, tokens, subscription URLs, or full proxy node definitions.
- Treat `/home/claw/.config/mihomo/config.yaml` as production proxy config. Always create a timestamped backup before editing.
- Keep proxy exposure local: use `127.0.0.1:7890`, not `0.0.0.0`.
- Preserve existing Kimi/Hermes provider config; only add proxy routing and environment variables.
- If verification fails after changing mihomo, restore the generated backup or select another known-good proxy group.

## Quick Workflow

1. Check current status:
   ```bash
   python3 ~/.codex/skills/configure-mihomo-proxy/scripts/configure_mihomo_proxy.py status
   ```
2. Apply the standard server configuration:
   ```bash
   sudo python3 ~/.codex/skills/configure-mihomo-proxy/scripts/configure_mihomo_proxy.py apply
   ```
3. Verify network and tool wiring:
   ```bash
   python3 ~/.codex/skills/configure-mihomo-proxy/scripts/configure_mihomo_proxy.py verify
   ```
4. For a real Codex smoke test, run:
   ```bash
   cd /home/lingfeng/atlas
   printf 'Reply OK only.\n' | timeout 180s codex exec --skip-git-repo-check --json -m gpt-5.4-mini -c 'model_reasoning_effort="low"' -
   ```

## What Apply Does

- Adds high-priority mihomo rules for `chatgpt.com`, `openai.com`, `oaistatic.com`, `oaiusercontent.com`, and `auth0.com` to the configured AI-safe proxy group.
- Restarts `mihomo.service` after writing config.
- Installs proxy wrappers for `/usr/local/bin/codex` and `/usr/local/bin/claude` while preserving real binaries as `codex-real` and `claude-real`.
- Adds proxy environment variables to Claude settings.
- Adds proxy variables to `/home/lingfeng/.hermes/.env`.
- Adds systemd drop-ins for Hermes gateway and Hermes web UI so services inherit the proxy.

## Useful References

Read `references/server-paths.md` when paths, service names, or backup locations matter.
