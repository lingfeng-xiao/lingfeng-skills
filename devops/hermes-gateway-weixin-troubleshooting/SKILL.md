---
name: hermes-gateway-weixin-troubleshooting
description: Diagnose and optimize WeChat (Weixin) channel performance and configuration issues in Hermes Gateway. Covers post-setup authorization, message latency analysis, pairing mode pitfalls, and NixOS declarative management considerations.
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [hermes, gateway, weixin, wechat, troubleshooting, performance, nixos]
---

# Hermes Gateway WeChat (Weixin) Troubleshooting

Common pitfalls and performance issues after configuring Weixin channel in Hermes Gateway, and how to diagnose/fix them.

## The "Setup Complete But No Reply" Trap

**Symptom:** User runs `hermes gateway setup`, scans QR code, sees success message, sends a message — but gets no reply.

**Root cause:** Setup wizard defaults to `WEIXIN_DM_POLICY=pairing`, which requires explicit approval before the bot responds to any user.

**Diagnosis steps:**

1. Check gateway error logs for `Unauthorized user` entries:
   ```bash
   tail ~/.hermes/logs/errors.log
   ```

2. Check pairing status:
   ```bash
   hermes pairing list
   ```

3. Verify current DM policy in environment config.

**Fix (choose one):**

1. **Approve the user** (keeps pairing mode):
   ```bash
   hermes pairing approve
   ```

2. **Open DMs** (less secure, faster for personal use):
   ```bash
   hermes config set platforms.weixin.extra.dm_policy open
   ```

3. **Set global allow-all flag** (not recommended for multi-platform setups):
   Use `hermes config set` or edit env configuration appropriately.

**Verification after fix:** Restart gateway and send a test message from WeChat.

---

## Message Reply Latency Analysis

WeChat messages can feel slow due to multiple stacked delays. Distinguish **infrastructure latency** (cannot be reduced) from **model/tool latency** (can be optimized).

### Infrastructure Latency (Cannot Eliminate)

| Source | Delay | Why |
|--------|-------|-----|
| WeChat long-poll | 0–35 sec (avg ~17.5 sec) | iLink API uses 35-second HTTP long-poll. Gateway holds connection until message arrives or timeout. |
| iLink API round-trip | 200–800 ms | Server processing + network to Tencent CDN |
| Typing indicator API | 1–2 sec | Weixin adapter fetches typing_ticket before every reply |

**Key insight:** If total latency is 20–40 seconds, the long-poll is the dominant factor. This is expected behavior, not a bug.

### Model & Tool Latency (Can Optimize)

| Source | Typical Delay | Optimization |
|--------|---------------|--------------|
| Model reasoning (medium) | 2–5 sec | Set agent reasoning_effort to minimal |
| Tool call chain | 1–3 sec per call | Disable unnecessary toolsets; reset sessions to truncate context |
| Context compression (long sessions) | 2–5 sec | Sessions with many messages trigger compression |
| Smart model routing disabled | All queries use full model | Enable smart_model_routing for simple questions |

**Quick diagnosis:** Analyze recent session files to check message count and tool call frequency. High tool-call counts indicate excessive file/terminal operations, which balloon context and slow replies.

---

## Configuration Optimizations

### 1. Reduce Reasoning Effort
```yaml
agent:
  reasoning_effort: minimal
```

### 2. Enable Smart Model Routing
Routes simple queries to a faster/cheaper model:
```yaml
smart_model_routing:
  enabled: true
  max_simple_chars: 160
  max_simple_words: 28
  cheap_model:
    provider: openrouter
    model: google/gemini-flash-1.5
```
Requires OpenRouter API key configured.

### 3. Truncate Long Sessions
Gateway sessions accumulate tool results indefinitely. Every tool call appends its output to context, so token usage grows exponentially.

- **Manual reset:** Type `/reset` in any chat to start fresh.
- **Auto-reset via cron:** Schedule periodic session resets.
- **Idle reset (config):** Set session_reset.idle_minutes in config.

### 4. Disable Unnecessary Toolsets for Gateway
Gateway sessions rarely need browser, vision, or code_execution. Reduce tool count to shrink prompts:
```bash
hermes tools disable browser
hermes tools disable vision
hermes tools disable code_execution
# Then /reset in the gateway session
```

---

## NixOS Declarative Management Note

**Do NOT run `hermes gateway install` on NixOS.** This creates imperative systemd user services under home config, which conflicts with NixOS declarative philosophy.

**Preferred approach:** Define the gateway service in home-manager via `systemd.user.services`:

```nix
{ config, ... }:
{
  systemd.user.services.hermes-gateway = {
    Unit = {
      Description = "Hermes Gateway";
      After = [ "network.target" ];
    };
    Service = {
      Type = "simple";
      ExecStart = "${config.home.homeDirectory}/.hermes/hermes-agent/venv/bin/hermes gateway";
      Restart = "on-failure";
      RestartSec = "5";
    };
    Install = { WantedBy = [ "default.target" ]; };
  };
}
```

Then rebuild with standard NixOS rebuild command.

---

## Terminal QR Code Rendering

During `hermes gateway setup`, the Weixin adapter prints both an ASCII QR code and a scannable URL. The URL is printed above the ASCII QR. If the ASCII QR code is garbled in chat interfaces, open the URL in a desktop browser and scan from there.

---

## Common Errors

| Error | Meaning | Fix |
|-------|---------|-----|
| `Unauthorized user: ... on weixin` | DM policy is pairing/allowlist and sender not approved | `hermes pairing approve` or change DM policy to open |
| `Weixin startup failed: aiohttp and cryptography are required` | Missing Python deps | `pip install aiohttp cryptography` |
| `Weixin startup failed: WEIXIN_TOKEN is required` | QR login expired or not completed | Re-run `hermes gateway setup` |
| `Another local Hermes gateway is already using this Weixin token` | Only one poller per token allowed | Stop the other gateway instance |
| `Session expired (errcode=-14)` | iLink login session expired | Re-run `hermes gateway setup` |
| `iLink POST ... HTTP 4xx/5xx` | iLink API error | Check token validity and network connectivity |
