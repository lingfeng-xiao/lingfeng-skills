---
name: configure-hermes-feishu-streaming
description: Configure and verify Hermes Gateway streaming replies and richer Feishu message UX without affecting other platforms.
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [hermes, gateway, feishu, streaming, rich-text]
---

# Configure Hermes Feishu Streaming

Use this when the user wants Hermes replies in Feishu/Lark to stream progressively, be less noisy, and prefer richer formatting.

## What this config controls

Hermes has two different knobs that matter:

1. **Per-platform display override** under `display.platforms.feishu`
   - `streaming: true` enables streaming for Feishu specifically
   - `tool_progress: off` suppresses noisy tool-progress messages in Feishu
2. **Top-level gateway streaming config** under `streaming`
   - `transport: edit`
   - `edit_interval`
   - `buffer_threshold`
   - `cursor`

Important: the effective Feishu behavior is the combination of both. A good default is to enable Feishu streaming via `display.platforms.feishu.streaming` while keeping the global top-level `streaming.enabled: false` so other platforms are unaffected.

## Recommended config

Edit `~/.hermes/config.yaml` to include:

```yaml
display:
  platforms:
    feishu:
      streaming: true
      tool_progress: off

streaming:
  enabled: false
  transport: edit
  edit_interval: 0.8
  buffer_threshold: 24
  cursor: ''
```

Notes:
- `tool_progress: off` makes Feishu feel cleaner while keeping streaming enabled.
- `edit_interval: 0.8` is a good balance between responsiveness and edit-rate safety.
- `buffer_threshold: 24` makes edits happen sooner so replies feel more live.
- `cursor: ''` removes the blinking/trailing cursor for a cleaner look.

## Verification steps

### 1. Confirm config values

From the Hermes repo root:

```bash
python - <<'PY'
from hermes_cli.config import load_config
from gateway.display_config import get_effective_display
from gateway.config import load_gateway_config

cfg = load_config()
print('display.platforms.feishu =', ((cfg.get('display') or {}).get('platforms') or {}).get('feishu'))
print('effective_feishu_display =', get_effective_display(cfg, 'feishu'))
gw = load_gateway_config()
print('gateway.streaming =', gw.streaming.to_dict())
PY
```

Expected shape:
- `display.platforms.feishu` includes `streaming=True` and `tool_progress='off'`
- `gateway.streaming` shows `transport='edit'`, tuned interval/threshold, and empty cursor

### 2. Restart gateway

Headless-safe lifecycle command:

```bash
hermes gateway restart
```

Then check:

```bash
hermes gateway status
```

If status says `Gateway draining for restart (1 active agent)`, the restart request succeeded but Hermes is waiting for the active conversation to finish. Re-check after the current turn ends.

### 3. Verify Feishu reconnected

Look for successful connection lines in logs or status output, e.g.:
- `Connected in websocket mode (feishu)`
- `✓ feishu connected`

## Rich text expectations

Current Feishu adapter behavior:
- Normal replies prefer Feishu `post` rich-text payloads
- If Feishu rejects the `post` payload, Hermes falls back to plain `text`
- Interactive approvals already use Feishu `interactive` cards
- Streaming works through message editing (`edit_message`)

So if a user wants richer Feishu messages, the practical guidance is:
- Prefer normal replies that can render as `post`
- Use icons and structure in content
- Reserve interactive cards for workflows that genuinely need buttons or stateful UI

## Useful code locations

- `gateway/platforms/feishu.py` — send/edit behavior, post fallback, interactive cards
- `gateway/run.py` — stream consumer wiring and per-platform streaming gate
- `gateway/display_config.py` — `display.platforms.<platform>` resolution
- `gateway/config.py` — top-level `streaming` config schema

## Session isolation behavior

Feishu session boundaries are controlled by `gateway/session.py:build_session_key`.

| Feishu scene | Session key pattern | Isolation |
|---|---|---|
| DM (p2p) | `agent:main:feishu:dm:{chat_id}` | One session per DM chat. **No `thread_id` in DMs**, so all messages share a single context. |
| Group (regular) | `agent:main:feishu:group:{chat_id}:{user_id}` | Per-user isolation when `group_sessions_per_user=True` (default). |
| Group thread/topic | `agent:main:feishu:group:{chat_id}:{thread_id}` | Per-thread isolation. Shared across all users in that thread unless `thread_sessions_per_user=True`. |

Practical implication: **parallel multi-topic sessions in a Feishu DM are impossible** because Feishu does not populate `message.thread_id` in p2p chats. The adapter reads `thread_id=getattr(message, "thread_id", None) or None` at `feishu.py:2180`, but the field is only present in group-topic mode.

If a user asks for concurrent topics, the options are:
1. Use multiple group chats (each group = isolated session).
2. Use a single group chat with Feishu "topic mode" enabled (each topic = isolated thread session).
3. Manually tag messages (e.g. `#topic-a`) and manage context switching in prompts — not true session isolation.

## Pitfalls

1. Do not confuse `display.streaming` with gateway `streaming.enabled`.
   - The key that matters for Feishu-only enablement is `display.platforms.feishu.streaming`.
2. Restart may appear incomplete during an active chat because gateway drains existing work first.
3. If the user cares about presentation quality, also avoid leading blank lines and overly plain text.
4. Feishu supports richer rendering, but not every message can safely be forced into a card. Use cards selectively.
5. When debugging session isolation issues, check `build_session_key` in `gateway/session.py` and the platform adapter's `thread_id` extraction logic — not just the config file.
6. **Do not trust in-chat "mock previews" of Feishu styles.** A normal assistant reply in the current conversation may still go out as plain text even if the adapter has style marker support. Writing `[[style-a]]` (or describing the style in plain text) inside a regular chat response is not a reliable verification method.
7. **Verify rich-text styles through the actual adapter/API path.** If the goal is to confirm that `interactive` / `post` payloads really render in Feishu, send a real message through `FeishuAdapter._send_raw_message(...)` or the gateway send pipeline and confirm the API response/message IDs. Use the visible chat result as the final source of truth.

## Verifying custom style payloads

When testing new Feishu reply styles (for example interactive card vs post vs compact quote):

1. Confirm the style hooks exist in `gateway/platforms/feishu.py`.
   - Example markers / builders:
     - `_STYLE_A_MARKER`, `_STYLE_B_MARKER`, `_STYLE_C_MARKER`
     - `_build_style_a_payload()`, `_build_style_b_payload()`, `_build_style_c_payload()`
     - `FeishuAdapter._build_outbound_payload()`
2. Do **not** rely on the current assistant message body to trigger those styles.
3. Send a real test message through the adapter, e.g. instantiate `FeishuAdapter(PlatformConfig(enabled=True))`, load `FEISHU_*` credentials from `~/.hermes/.env`, build the payload with the helper function, then call:
   - `await adapter._send_raw_message(chat_id=..., msg_type='interactive'|'post', payload=..., reply_to=None, metadata={...})`
4. Treat `success=true`, response `code=0`, and returned `message_id` as transport verification; then visually inspect the Feishu chat to judge the rendering.
5. Only after that should you ask the user to choose between styles.

## Success criteria

A good outcome looks like this:
- Feishu replies stream progressively by editing one message
- Tool-progress chatter is suppressed in Feishu
- Message updates feel responsive but not spammy
- Replies are visually richer when Feishu accepts `post` formatting
- Other platforms are unaffected unless explicitly configured
