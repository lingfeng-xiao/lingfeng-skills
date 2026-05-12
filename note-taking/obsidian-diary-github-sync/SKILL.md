---
name: obsidian-diary-github-sync
description: Set up an Obsidian diary vault with lowercase-safe naming, Git tracking, GitHub sync, and a diary workflow that stores original text, corrected text, evaluation, and guidance.
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [obsidian, github, diary, journaling, english-learning, notes]
---

# Obsidian Diary Vault + GitHub Sync

Use this when the user wants a lightweight Obsidian vault for journaling/diary work, especially when entries originate in chat and need structured archival plus GitHub backup.

## When to use
- User wants an Obsidian vault created from scratch
- User wants GitHub backup/sync for notes or diary entries
- User cares about strict naming conventions
- User wants a repeatable diary-entry workflow with fixed sections

## Important conventions learned
- Prefer **all lowercase** for every folder and filename
- Use **no spaces** and avoid unusual special characters
- If a parent directory also violates naming rules, rename that too
- For user-facing journaling workflows, saving should be **silent**; only confirm completion at the end

## Recommended path layout
Use lowercase-only paths such as:

```bash
~/documents/obsidian-vault/english-diary/
├── daily/
├── templates/
├── reviews/
├── readme.md
└── workflow.md
```

## Setup steps

### 1. Create or normalize the vault path
Use lowercase, no spaces:

```bash
mkdir -p ~/documents/obsidian-vault/english-diary/{daily,templates,reviews}
```

If earlier directories were created with spaces or capitals (for example `~/Documents/Obsidian Vault/English Diary`), rename them into normalized lowercase paths before continuing.

### 2. Set `OBSIDIAN_VAULT_PATH`
Write/update `~/.hermes/.env`:

```bash
OBSIDIAN_VAULT_PATH="/home/<user>/documents/obsidian-vault/english-diary"
```

### 3. Create base files
Recommended files:
- `readme.md`
- `workflow.md`
- `templates/daily-english-diary-template.md`

### 4. Diary template structure
Use this structure for each entry:

```md
# yyyy-mm-dd english diary

## metadata
- entry_date:
- written_at:
- style: daily-life

## original

## corrected

## evaluation
- overall:
- what_you_did_well:
- what_feels_unnatural:
- grammar_points:
- vocabulary_notes:
- tone_and_diary_feel:

## level_assessment
- estimated_level:
- evidence:
- current_strength:
- current_limit:

## learning_advice
- priority:
- why_this_matters:
- practice_suggestion:

## guidance
- today_focus:
- next_step:
- try_these_expressions:
  -
  -
  -

## my_revision_notes
-
```

## Diary workflow rules
For each diary entry, save these sections:
1. `original` — the user’s raw text
2. `corrected` — a natural daily-life rewrite
3. `evaluation` — richer commentary, not just corrections
4. `level_assessment` — a lightweight judgment of the user’s current English level based on the entry
5. `learning_advice` — concrete learning suggestions derived from this specific entry
6. `guidance` — next-step advice and reusable expressions

In addition to language correction, treat the diary itself as meaningful user context: absorb stable signals about the user's real life, priorities, tools, frustrations, and current state when those details are useful across sessions.

### Tone rules
- Keep it **daily-life** and natural
- Do **not** make it sound like an essay
- Do **not** over-polish
- Preserve the user’s mood and meaning

### Dating rule
If the user writes after midnight but has not slept yet, the entry belongs to the **previous day**. Save both:
- `entry_date`
- `written_at`

## Git setup
Inside the vault:

```bash
git init -b main
git config user.name "<name>"
git config user.email "<email>"
```

Use a `.gitignore` like:

```gitignore
.obsidian/workspace.json
.DS_Store
Thumbs.db
```

## GitHub sync setup
Preferred long-term remote is **SSH**:

```bash
git remote add origin git@github.com:<owner>/english-diary.git
```

### If a GitHub token is provided and the repo does not exist yet
1. Create the repo via GitHub API using the token
2. Temporarily set HTTPS remote with token only if needed for the first push
3. Push `main`
4. Immediately change remote back to SSH so the token is not left in git config

Pattern:

```bash
# temporary
https://<owner>:<token>@github.com/<owner>/english-diary.git

# final
git@github.com:<owner>/english-diary.git
```

## Verification
Check:

```bash
git remote -v
git status --short --branch
git ls-remote --heads origin main
```

Expected outcome:
- branch `main` tracks `origin/main`
- remote uses SSH
- vault path and files are all lowercase-safe

## User interaction rule
When handling diary entries after setup:
- perform file save + git commit/push silently
- do not narrate storage mechanics unless asked
- just provide the language feedback, then end with a short confirmation such as:

```text
这天的日记保存好了。
```

## Pitfalls
- `mkdir -p path/{a,b,c}` only expands braces in a shell that performs brace expansion; if passed through a quoted string or certain execution contexts, it can accidentally create a literal `{a,b,c}` directory. Verify the result and remove any accidental literal brace directory.
- A CLI config setter may serialize `off` incorrectly as boolean `False` in YAML-like settings; verify the actual loaded config after setting approval-related values.
- If the user says “all folders and files lowercase,” check parent directories too (`Documents` may need to become `documents`).
- If the user pastes a GitHub token in chat, recommend rotating/revoking it after setup, especially once SSH remote works.
