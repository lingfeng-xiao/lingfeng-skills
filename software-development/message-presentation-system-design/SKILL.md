---
name: message-presentation-system-design
description: Design a product-grade global message presentation system for chatbots/agents without overloading SOUL or overengineering the first version.
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [messaging, ux, product-design, presentation, notifications, architecture]
---

# Message Presentation System Design

Use this when designing or refactoring how an agent presents outbound messages across platforms (chat replies, notifications, reminders, alerts, reports, teaching layouts).

## When to use
- The user wants a unified reply style system across platforms
- Current styles are ad hoc, ugly, or inconsistent
- The conversation is drifting toward putting style rules into `SOUL.md`
- The user wants a product/engineering-grade solution, not prompt-only tweaks
- Notifications/reminders/alerts need to be included in the same system

## Core principles
1. **Do not put presentation rules in `SOUL.md`**
   - Soul should own persona, tone, values, response tendency
   - Presentation system should own scene selection, structure, icons, tables, images, splitting, renderer behavior

2. **Do not start with overengineering**
   - Prefer a small MVP that can ship and evolve
   - The goal is a closed loop that is implementable, not a perfect grand framework on day one

3. **Do not solve this with skills alone**
   - Runtime behavior should be enforced in code
   - Skills should support QA/review/evolution, not act as the primary runtime style engine

## Recommended architecture
Use a **hybrid** approach:

### A. Spec docs
Keep a short written spec for:
- scenes
- style families
- notify/reminder/alert structure
- platform rendering principles

### B. Light code constraints
Use code for the minimum runtime guarantees:
- classify scene
- select style family
- enforce notification structure
- render per platform

### C. One support skill first
Start with **one QA/review skill** (for example `message-style-qa`) rather than multiple skills. Split later only if needed.

## MVP framing
Start with only **4 scenes**:
- `chat`
- `teaching`
- `notify`
- `report`

Start with only **3 style families**:
- `simple`
- `structured`
- `rich`

Start with only these **basic blocks**:
- `title`
- `summary`
- `section`
- `bullet_list`
- `status`
- `next_step`
- `compare`
- `image`

Avoid introducing a large component framework in v1.

## Notify model (MVP)
Unify notification / reminder / alert / status under one initial `notify` model with level:
- `info`
- `success`
- `reminder`
- `warning`
- `critical`

Every notify output should answer:
1. What happened?
2. Why does it matter?
3. Does the user need to act?
4. If yes, what is the next step?

This gives consistency without requiring an overly detailed taxonomy on day one.

## Suggested rollout
### v1
- 4 scenes: chat / teaching / notify / report
- 3 styles: simple / structured / rich
- unified notify structure
- implement on the most important platforms first
- one QA skill

### v1.1
- refine image/table usage rules
- split teaching subcases if needed
- improve severity distinctions in notify

### v1.2
- consider separating reminder vs alert
- add more components only after real usage pressure
- consider a stronger planner only if current rules become too limiting

## Anti-patterns
Avoid these:
- burying style logic in `SOUL.md`
- relying entirely on prompt wording like “be more visual”
- creating many style families before validating the first few
- creating many skills before the runtime model is stable
- building a heavy planner/renderer framework before a minimal working system exists

## Good output shape for planning conversations
When proposing the design, structure the answer as:
1. Goal
2. Scope
3. Simplified MVP model
4. Runtime/code vs skill vs soul responsibilities
5. Rollout phases
6. Recommended next step

## What to recommend by default
If asked whether this should be a skill, multiple skills, code constraints, or something else:
- Recommend **spec + light code constraints + one QA skill** for v1
- Recommend expanding into more skills or more abstraction only after real usage validates the need
