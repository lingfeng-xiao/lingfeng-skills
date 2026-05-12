---
name: hermes-provider-failover-quota-ops
description: Safely configure Hermes primary/fallback providers, avoid unsupported Codex model slugs, and use auth.json credential-pool state to drive auto-swap decisions when a provider is quota-exhausted.
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [hermes, provider, fallback, quota, codex, kimi, gateway, ops]
---

# Hermes Provider Failover + Quota Ops

Use this when Hermes needs resilient model failover across providers (especially `kimi-coding` and `openai-codex`) and the user wants to avoid repeated failed calls to a known-exhausted primary provider.

## Why this skill exists

Hermes' built-in fallback is **turn-scoped**:
- one turn can switch to fallback
- the next turn restores the primary provider first

That is good for transient errors, but **bad when the primary is already known to be quota-exhausted**, because Hermes will keep wasting the first attempt on the exhausted primary every new turn.

In that case, promote the healthy fallback provider to primary in `~/.hermes/config.yaml`, and keep the exhausted provider as fallback until it recovers.

## Critical safety rule

For model/provider configs that can break Hermes availability:

1. **Do not guess model slugs**
2. **Verify the exact provider-supported model name in the local Hermes codebase and/or auth/runtime behavior first**
3. **Read current config before editing**
4. **After editing, verify gateway health**

The user explicitly does not want speculative config edits on critical availability paths.

## Important findings

### 1. `openai-codex` with ChatGPT account does NOT support `codex-latest`

Observed failure:

```text
Error code: 400 - {'detail': "The 'codex-latest' model is not supported when using Codex with a ChatGPT account."}
```

For this environment, the correct fallback/primary Codex model was:

```yaml
provider: openai-codex
model: gpt-5.4
base_url: https://chatgpt.com/backend-api/codex
```

Do not use `codex-latest` here unless you have verified the account/runtime supports it.

### 2. `~/.hermes/auth.json` is a stronger source of truth than logs for quota state

Read:
- `providers.*`
- `credential_pool.<provider>[0].last_status`
- `credential_pool.<provider>[0].last_error_code`
- `credential_pool.<provider>[0].last_error_message`
- `credential_pool.<provider>[0].last_error_reset_at`

Example real signal:

```json
"credential_pool": {
  "kimi-coding": [{
    "last_status": "exhausted",
    "last_error_code": 403,
    "last_error_message": "You've reached your usage limit for this billing cycle. Your quota will be refreshed in the next cycle..."
  }]
}
```

If `last_status == "exhausted"`, treat the provider as unavailable until proven healthy.

### 3. Precise reset time is often unavailable

In this environment, provider errors exposed only vague recovery text such as:
- `next period`
- `next cycle`
- `The usage limit has been reached`

There was **no trustworthy precise `reset_at`** for the user-facing answer.

So do **not** invent a countdown.
Instead say:
- provider is exhausted
- error code/message
- exact recovery time is not available from provider response

## Safe configuration patterns

### A. Normal preferred state: Kimi primary, Codex fallback

```yaml
model:
  default: kimi-for-coding
  provider: kimi-coding
  base_url: https://api.kimi.com/coding/v1

fallback_providers:
  - provider: openai-codex
    model: gpt-5.4
    base_url: https://chatgpt.com/backend-api/codex
```

### B. When Kimi is known exhausted: Codex primary, Kimi fallback

```yaml
model:
  default: gpt-5.4
  provider: openai-codex
  base_url: https://chatgpt.com/backend-api/codex

fallback_providers:
  - provider: kimi-coding
    model: kimi-for-coding
    base_url: https://api.kimi.com/coding/v1
```

## Headless-safe workflow

Load and follow `hermes-gateway-headless-ops` too when touching the gateway.

### Phase 1: verify before editing

1. Read current config:
```bash
read ~/.hermes/config.yaml
```
2. Verify supported Codex models in Hermes source:
- `~/.hermes/hermes-agent/hermes_cli/codex_models.py`
- `~/.hermes/hermes-agent/hermes_cli/models.py`
3. Read runtime credential/quota state:
```bash
read ~/.hermes/auth.json
```
4. Check for known exhausted provider entries.

### Phase 2: edit config

Swap primary/fallback only after verifying the exact model slug.

### Phase 3: restart and verify

Use only short lifecycle commands:
```bash
hermes gateway restart
hermes gateway status
```

If `restart` leaves the user service stopped or in auto-restart failure, follow with:
```bash
hermes gateway start
hermes gateway status
```

Do not run `hermes gateway run` in headless ops.

## Recommended automation design

### Goal
Avoid retrying a known-exhausted primary every turn.

### Mechanism
Run a periodic script that:
1. reads `auth.json`
2. checks whether current primary is marked exhausted
3. if exhausted, rewrites `config.yaml` to promote fallback to primary
4. restarts gateway
5. while fallback is primary, periodically probes the original provider
6. when it recovers, restores the original primary

### Probe logic for Kimi
A lightweight probe can call:

```text
GET https://api.kimi.com/coding/v1/models
Authorization: Bearer $KIMI_API_KEY
```

Interpretation:
- `2xx` => available
- `402/403/429` with `usage limit` in body => still exhausted
- otherwise => unknown; avoid flapping

## User-facing reporting guidance

When the user asks for “额度情况”, prefer direct status over links.

Good answer structure:

```text
- 当前主模型: ...
- 当前备用模型: ...
- Kimi: 已耗尽 / 未见 exhausted 标记
- Codex: 已耗尽 / 未见 exhausted 标记
- 最近错误时间: ...
- 恢复信息: 服务端未返回精确恢复时间
```

Do not primarily answer with dashboard URLs. Links can be secondary.

## Monitoring and alert delivery pattern

### 1. Use two alert levels, not only exhausted/not-exhausted

A practical quota monitor should classify provider state into at least:
- `ok`
- `warning` — soft signals such as HTTP 429, `rate limit`, `too many requests`, or provider messages mentioning `quota` / `usage limit` / `credit` even when not yet marked exhausted
- `critical` — confirmed `last_status == "exhausted"`

This lets the user get early warning before full exhaustion.

Important limitation:
- in this environment, warning is **signal-based**, not a precise remaining-quota percentage
- do not invent "还剩 12%" unless the provider actually exposes trustworthy usage data

### 2. Reuse `auth.json` credential-pool state for alerts

For each provider, inspect:
- `last_status`
- `last_error_code`
- `last_error_message`
- `last_status_at`

Then derive a user-facing summary like:

```text
模型额度告警：warning|critical
- 当前主模型: ...
- 当前备用: ...
- Kimi: ...
- Codex: ...
- 建议: ...
```

### 3. Make recurring alerts truly silent on no-change

For cron-driven monitoring:
- only emit output when the computed status digest changes
- if nothing changed, print nothing at all
- avoid placeholder messages such as `(no output)` because they still create notification noise

### 4. Do not rely on `deliver=origin` for unattended cron alerts

Observed issue:
- a recurring quota-monitor cron job with `deliver=origin` had `last_delivery_error = "no delivery target resolved for deliver=origin"`

Safer pattern:
- explicitly target the user channels, e.g.
  - `weixin:<chat_id>`
  - `feishu:<chat_id>`
- if the user wants important notifications on multiple platforms, create one cron job per target rather than hoping `origin` resolves correctly

### 5. Verification checklist for recurring notifications

After creating/updating the cron jobs:
1. `cronjob list` — confirm `deliver` points to concrete targets
2. manually trigger a one-shot or `run` the job
3. wait for execution and re-check `last_status`
4. ensure `last_delivery_error` is `null`
5. optionally verify cron output files were created for the test run

## Pitfalls

1. **Do not use `codex-latest` blindly** for `openai-codex` with ChatGPT account auth.
2. Hermes turn-scoped fallback is not enough for known quota exhaustion.
3. Logs are useful, but `auth.json` credential-pool state is more reliable for current exhausted/not-exhausted status.
4. After config swap, always verify gateway status; `restart` may leave the service stopped and require `start`.
5. Never claim an exact reset countdown unless the provider actually returns one.

## Success criteria

A good outcome looks like:
- Hermes no longer wastes first attempts on a known-exhausted primary
- Current primary/fallback in config matches real provider health
- Gateway is running after the change
- User gets direct, concrete quota status instead of generic console links
- Exact recovery ETA is only shown when genuinely available
