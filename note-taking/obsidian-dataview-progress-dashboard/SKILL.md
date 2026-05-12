---
name: obsidian-dataview-progress-dashboard
description: |
  Build a learning progress dashboard in Obsidian using Dataview + Templater.
  Tracks completion, quality metrics, time logs, and bottleneck alerts automatically.
  Works headlessly (no GUI needed for plugin installation).
install: |
  # Plugins are installed manually into .obsidian/plugins/ (see setup steps below)
  # No external dependencies required beyond Obsidian itself.
usage: |
  # 1. Install Dataview + Templater plugins (see setup)
  # 2. Copy the dashboard template to your vault
  # 3. Create daily logs using the provided frontmatter templates
  # 4. Open the dashboard — all metrics auto-calculate
author: lingfeng
---

# Obsidian Dataview Progress Dashboard

A systematic way to track learning progress in Obsidian using **Dataview** queries and **YAML frontmatter**. Designed for long-term study projects (e.g., postgraduate exam prep, language learning, skill acquisition).

## What it provides

1. **Auto-calculating dashboard**: Completion rates, averages, trends — all computed from your daily notes
2. **Bottleneck tracking**: Mark stuck items in any note; dashboard auto-collects them
3. **Time heatmap**: Daily time allocation across modules
4. **Module-based structure**: Each learning stage has its own log type with tailored fields
5. **Headless plugin install**: Works on servers without Obsidian GUI access

## When to use

- You need to track progress across multiple stages/modules over weeks/months
- You want quantitative feedback (accuracy %, time spent, completion rate)
- You study from video courses and need to link notes to progress
- You prefer Obsidian over spreadsheets for study tracking

## Architecture

```
vault/
├── subject/
│   ├── 📊 Dashboard.md          ← Dataview queries aggregate everything
│   ├── stage-1-vocab/
│   ├── stage-2-grammar/
│   ├── stage-3-practice/
│   └── daily/
└── templates/
    ├── dashboard.md
    ├── vocab-log.md
    ├── grammar-log.md
    └── daily-log.md
```

## Plugin setup (headless / no GUI)

Obsidian's community plugins usually require GUI clicks to install. For headless environments:

```bash
VAULT="/path/to/your/vault"

# 1. Dataview
mkdir -p "$VAULT/.obsidian/plugins/dataview"
TAG=$(curl -sL https://api.github.com/repos/blacksmithgu/obsidian-dataview/releases/latest | \
  python3 -c "import sys,json; print(json.load(sys.stdin)['tag_name'])")
curl -sL "https://github.com/blacksmithgu/obsidian-dataview/releases/download/$TAG/main.js" \
  -o "$VAULT/.obsidian/plugins/dataview/main.js"
curl -sL "https://raw.githubusercontent.com/blacksmithgu/obsidian-dataview/$TAG/manifest.json" \
  -o "$VAULT/.obsidian/plugins/dataview/manifest.json"

# 2. Templater
mkdir -p "$VAULT/.obsidian/plugins/templater-obsidian"
TAG=$(curl -sL https://api.github.com/repos/SilentVoid13/Templater/releases/latest | \
  python3 -c "import sys,json; print(json.load(sys.stdin)['tag_name'])")
curl -sL "https://github.com/SilentVoid13/Templater/releases/download/$TAG/main.js" \
  -o "$VAULT/.obsidian/plugins/templater-obsidian/main.js"
curl -sL "https://raw.githubusercontent.com/SilentVoid13/Templater/$TAG/manifest.json" \
  -o "$VAULT/.obsidian/plugins/templater-obsidian/manifest.json"

# 3. Enable plugins
cat > "$VAULT/.obsidian/community-plugins.json" << 'EOF'
[
  "dataview",
  "templater-obsidian"
]
EOF
```

## Core design pattern

### 1. Frontmatter schema per log type

Each learning session is a separate note with typed frontmatter:

**Vocab log:**
```yaml
---
type: vocab-log
date: 2026-05-05
round: 1
words_total: 100
words_known: 72
words_new: 28
time_minutes: 42
method: 检测式记忆
status: completed
bottleneck:
---
```

**Grammar log:**
```yaml
---
type: grammar-log
date: 2026-05-05
lesson: 第1节
topic: 语法框架
completion: 100
understanding: 80
status: completed
bottleneck:
---
```

**Daily log:**
```yaml
---
type: daily-log
date: 2026-05-05
total_minutes: 42
vocab_minutes: 42
grammar_minutes: 0
zhenti_minutes: 0
status: completed
mood: 不错
---
```

### 2. Dataview query patterns

**Table of recent logs:**
```dataviewjs
dv.table(
  ["Date", "Round", "Total", "Known", "New", "Time"],
  dv.pages('"subject/stage-1-vocab"')
    .where(p => p.type == "vocab-log")
    .sort(p => p.date, "desc")
    .limit(10)
    .map(p => [
      p.date, p.round, p.words_total,
      p.words_known, p.words_new,
      p.time_minutes + "min"
    ])
)
```

**Aggregated metrics:**
```dataview
TABLE WITHOUT ID
  sum(words_total) as "Total Words",
  sum(words_new) as "Total New",
  round(sum(words_new) / sum(words_total) * 100, 1) + "%" as "New Rate"
FROM "subject/stage-1-vocab"
WHERE type = "vocab-log"
```

**Bottleneck collection:**
```dataviewjs
dv.table(
  ["Type", "Bottleneck", "Date"],
  dv.pages('"subject"')
    .where(p => p.bottleneck && p.bottleneck != "")
    .sort(p => p.date, "desc")
    .limit(5)
    .map(p => [
      p.type?.replace("-log", ""),
      p.bottleneck,
      p.date
    ])
)
```

### 3. Dashboard structure

The dashboard is a single Markdown file with:
- **Overview section**: Inline Dataview queries for key numbers
- **Per-stage sections**: Tables for each learning module
- **Bottleneck alerts**: Auto-collected blockers
- **Time tracking**: Recent daily logs
- **Quick actions**: Links to create new logs

## Advanced pattern: Pre-seeded lesson files (course map)

When studying from a structured course (e.g., 15 video lessons), a **dual-track data model** is more useful than logs-only:

```
vault/
├── subject/
│   ├── stage-2-grammar/
│   │   ├── 语法-01-导学课.md      ← type: grammar-lesson (pre-seeded)
│   │   ├── 语法-02-名词.md        ← type: grammar-lesson (pre-seeded)
│   │   ├── ... (15 total)
│   │   └── 语法记录-2026-05-05.md  ← type: grammar-log (daily)
```

### Why two types?

| `grammar-lesson` | `grammar-log` |
|---|---|
| One file per lesson, created upfront | One file per study session |
| Holds static metadata: title, BV ID, CID, duration | Holds dynamic data: date, understanding, notes |
| `status` field drives completion: 未开始/进行中/已完成 | `lessons_today` field drives pace analysis |
| Dashboard renders full checklist (including pending) | Dashboard renders learning rhythm & trends |

### Pre-seeding from external sources

If your course is on Bilibili, fetch the episode list via API and generate all lesson files at once:

```python
from bilibili_api import video

async def get_season_episodes(bvid: str):
    v = video.Video(bvid=bvid)
    info = await v.get_info()
    season = info.get('ugc_season', {})
    episodes = []
    for section in season.get('sections', []):
        for ep in section.get('episodes', []):
            episodes.append({
                'no': len(episodes) + 1,
                'title': ep['title'],
                'bvid': ep['bvid'],
                'cid': ep['cid'],
            })
    return episodes
```

Generate one Markdown file per episode with this frontmatter:

```yaml
---
type: grammar-lesson
lesson_no: 2
title: 前言+名词
bvid: BV1gf6KBBE7q
cid: 35636186992
duration: 0
status: 未开始
understanding:
date:
bottleneck:
stuck_days: 0
---
```

### Dashboard queries for dual-track

**Course checklist with progress bar:**
```dataviewjs
const lessons = dv.pages('"subject/stage-2-grammar"')
  .where(p => p.type == "grammar-lesson")
  .sort(p => p.lesson_no)
  .array();

const total = 15;
const done = lessons.filter(p => p.status == "已完成").length;
const bar_len = 15;
const filled = Math.round((done / total) * bar_len);
const bar = "█".repeat(filled) + "░".repeat(bar_len - filled);
dv.paragraph(`> **${bar}** ${done}/${total} 节完成`);

dv.table(
  ["课时", "标题", "状态", "理解度", "操作"],
  lessons.map(p => {
    const icon = p.status == "已完成" ? "✅" : p.status == "进行中" ? "🔄" : "⬜";
    return [
      p.lesson_no,
      p.title,
      icon + " " + (p.status || "未开始"),
      p.understanding ? p.understanding + "%" : "-",
      p.file.link  // clickable link to the lesson note
    ];
  })
);
```

**Identify current lesson dynamically:**
```dataviewjs
const lessons = dv.pages('"subject/stage-2-grammar"')
  .where(p => p.type == "grammar-lesson")
  .sort(p => p.lesson_no)
  .array();
const current = lessons.find(p => p.status != "已完成");
if (current) {
  dv.paragraph(`当前进度：第 ${current.lesson_no} 节 "${current.title}"`);
  dv.paragraph(`[Bilibili](https://www.bilibili.com/video/${current.bvid}) | [笔记](${current.file.path})`);
}
```

**Status-driven milestone (not log-driven):**
```dataviewjs
const lessons = dv.pages('"subject/stage-2-grammar"')
  .where(p => p.type == "grammar-lesson")
  .array();
const completed = lessons.filter(p => p.status == "已完成").length;
// Use completed count for milestones, not sum(lessons_today)
```

## Key principles learned

1. **Separate data entry from aggregation**: Log notes are simple; dashboard does all math
2. **Type field is critical**: Dataview queries filter on `type`, not folder structure
3. **Bottleneck field everywhere**: Same field name across all log types enables unified alerting
4. **Daily log bridges stages**: One note tracks time spent across all modules for that day
5. **Templater for dynamic dates**: Templates use `{{date:YYYY-MM-DD}}` so new notes auto-fill today's date
6. **Pre-seeded lesson files create a course map**: You can see the full path ahead, not just where you've been
7. **Link files via `p.file.link`**: Makes the dashboard navigable — click any row to open its note
8. **Split the dashboard when it gets heavy**: A single file with 6+ Dataview blocks becomes slow to render and cognitively dense. Use a **hub-and-spoke** layout:
   - **Hub** (`📊 Dashboard.md`): Only today's tasks + key metrics + links to spoke panels
   - **Spokes** (`📚 Stage Panel.md`, `📝 Vocab Panel.md`): One per module, containing the detailed tables, progress bars, and course checklists
   - Clicking a spoke link in the hub jumps directly to that module's full view
   - This keeps the hub render time under 3 seconds even with hundreds of notes

## Common issues

- **"Dataview: Query returned 0 results"**: Check that `FROM` paths match your vault structure. Dataview paths are relative to vault root.
- **Templater not replacing dates**: Ensure Templater plugin is enabled and the template is triggered via Templater's "Insert template" command or hotkey.
- **Numeric fields treated as strings**: In YAML, write `time_minutes: 42` not `time_minutes: "42"`. Dataview arithmetic requires actual numbers.
- **Frontmatter syntax errors**: YAML is strict about indentation and colons. Use a YAML linter if queries break mysteriously.
### DataviewJS array conversion pitfalls (critical)

`dv.pages()` returns a **Dataview DataArray**, not a plain JavaScript array. This is the #1 source of silent failures and cryptic errors.

| Operation | DataArray | JS Array (after `.array()`) |
|---|---|---|
| Filter | `.where(fn)` | `.filter(fn)` |
| Sort | `.sort(p => p.date, "desc")` | `.sort((a, b) => b.date - a.date)` |
| First item | `.first()` | `[0]` |
| Last item | `.last()` | `[length - 1]` |
| Reduce / Aggregate | ❌ not supported | `.reduce(fn, init)` |
| Slice | ❌ not supported | `.slice(start, end)` |

**Rule: Decide your API at the chain boundary.**

```dataviewjs
// Pattern A: Stay in DataArray API (no .array())
const recent = dv.pages('"path"')
  .where(p => p.type == "log")
  .sort(p => p.date, "desc")
  .limit(7);
// recent is still a DataArray — safe for dv.table(), dv.list(), etc.

// Pattern B: Escape to JS array (needs .array())
const logs = dv.pages('"path"')
  .where(p => p.type == "log")
  .sort(p => p.date, "desc")
  .array();  // <-- escape hatch
const sum = logs.reduce((a, p) => a + p.minutes, 0);
const avg = Math.round(sum / logs.length);
// logs is now a plain JS array — no DataArray methods available
```

**Never mix APIs on the same chain:**
```dataviewjs
// WRONG — .array() kills DataArray methods
const broken = dv.pages('"path"').array().where(p => p.x);  // ❌ .where() does not exist

// WRONG — JS methods on DataArray
const broken = dv.pages('"path"').reduce((a, b) => a + b, 0);  // ❌ .reduce() does not exist
```

### Path resolution: vault-root relative

Dataview's `FROM "path"` and `dv.pages('"path"')` are **relative to the vault root**, not to the current file.

```
vault-root/
├── kaoyan/
│   ├── 02-英语/
│   │   └── 语法通关/          ← files are here
│   └── 📊 Dashboard.md         ← query runs from here
```

```dataviewjs
// WRONG — returns 0 results silently (no error!)
dv.pages('"语法通关"')

// CORRECT — full path from vault root
dv.pages('"kaoyan/02-英语/语法通关"')

// CORRECT — vault root IS kaoyan/ (if vault opened at kaoyan/)
dv.pages('"02-英语/语法通关"')
```

> **Silent failure**: Wrong paths return empty results with NO error. This is the hardest bug to catch. When a query returns 0 rows, always verify the path first.

### Self-assessment metrics: start minimal, add only if frictionless

A common temptation is to add a 0-100% `understanding` field to every log for fine-grained tracking. In practice this often fails because:

1. **Ambiguity**: What does 70% vs 75% mean? Different days, different moods, different criteria.
2. **Friction**: Estimating a percentage after every session is cognitively expensive — it interrupts flow.
3. **Actionability**: A continuous score rarely tells you what to do next. A ternary status does.

**Preferred approach**: Start with discrete status only:

```yaml
---
type: grammar-lesson
status: 未开始   # or: 进行中, 已完成
bottleneck:     # free-text, only fill when stuck
---
```

If you later need more granularity, add it **after** proving the simple version works. Never start with a 100-point scale — you can always aggregate upward (e.g., "3 of 15 lessons completed = 20%"), but you cannot recover from a system that demands too much data entry and gets abandoned.
