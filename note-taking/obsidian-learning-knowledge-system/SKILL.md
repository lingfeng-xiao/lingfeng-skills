---
name: obsidian-learning-knowledge-system
description: Design a Zettelkasten-inspired knowledge management system within an existing Obsidian vault for learning/study purposes. Features two-stage note-taking, cross-disciplinary concept cards, project-based method application, and native Obsidian aesthetics without plugins.
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [obsidian, zettelkasten, knowledge-management, learning, study, note-taking, concept-cards]
    related_skills: [obsidian, obsidian-vault-initialization, writing-plans]
---

# Obsidian Learning Knowledge System Design

Design a knowledge architecture inside an existing Obsidian vault optimized for learning from courses/lectures and building reusable concept assets.

## Core Philosophy

- **No Inbox**: Rough notes and refined notes happen in a continuous flow within the same file. There are no temporary holding pens.
- **Concepts above Disciplines**: Concept cards live in a cross-disciplinary layer. They are decontextualized and reusable across subjects.
- **Methods derive from Concepts**: Methods are not standalone cards. They are temporary combinations of concepts within project notes.
- **Single File, Two Stages**: Course notes contain both raw capture (stage 1) and Feynman refinement (stage 2) in one document.

## Directory Structure

```
vault/
├── 00-Meta/                    # Metadata layer
│   ├── 工作流/                 # Workflow rules
│   ├── 索引/                   # MOC (Map of Content) indexes
│   │   ├── 概念索引.md
│   │   └── 项目索引.md
│   └── 模板/                   # All templates
│       ├── 概念卡.md
│       ├── 课程笔记.md
│       ├── 项目笔记.md
│       └── 每日复盘.md
├── 10-Concepts/                # Cross-disciplinary concept library
│   ├── 认知科学/
│   ├── 语言习得/
│   └── 元认知/
├── 20-Projects/                # Applied projects (methods live here)
│   ├── Project-A/
│   └── Project-B/
├── 30-Subjects/                # Course raw material notes
│   ├── English/
│   ├── Politics/
│   └── Math/
├── 40-Daily/                   # Daily reviews
└── 90-Attachments/             # Images, PDFs
```

Use numeric prefixes so physical sorting equals logical sorting.

## YAML Frontmatter Standard

All notes use Properties (YAML frontmatter):

```yaml
---
type: concept | course | project | daily
domain: 认知科学 | 语言习得 | 元认知 | English | Politics | Math
status: draft | reviewing | mature | archived
created: YYYY-MM-DD
modified: YYYY-MM-DD
source: 来源描述
tags: []
---
```

## The Four Templates

### 1. Concept Card (`00-Meta/模板/概念卡.md`)

Decontextualized, cross-disciplinary, permanent asset.

```markdown
---
type: concept
domain:
status: draft
created: {{date:YYYY-MM-DD}}
modified: {{date:YYYY-MM-DD}}
source:
tags: []
---

# {{title}}

## 定义
（一句话精确定义）

## 核心机制
（它为什么成立？底层逻辑是什么？）

## 我的解释
（如果给朋友打电话，我会怎么解释这个概念？）

## 例子
（通用例子，不限于当前学习场景）

## 边界与反例
（什么时候不适用？常见的误解是什么？）

## 关联概念
- [[相关概念A]]
- [[相关概念B]]

## 来源与验证
- 来源：[[课程笔记名]]
- 验证状态：
  - [ ] 我能解释它为什么成立
  - [ ] 我能说出它什么时候不适用
  - [ ] 我能回应别人的反驳

## 历史
- {{date:YYYY-MM-DD}} 创建
```

**Rules:**
- No "考研版", no "老师说", no course-specific context.
- `我的解释` forces Feynman output.
- `边界与反例` prevents dogmatization.

### 2. Course Notes (`00-Meta/模板/课程笔记.md`)

Single file for both rough capture and Feynman refinement.

```markdown
---
type: course
domain:
status: draft
created: {{date:YYYY-MM-DD}}
modified: {{date:YYYY-MM-DD}}
source:
tags: []
---

# {{title}}

## 课程信息
- **讲师**：
- **章节**：
- **视频链接**：
- **重要程度**：⭐⭐⭐⭐⭐

---

## 阶段一：结论捕获
（看网课时快速填写，只记结论+最小上下文）

### 结论 1
- 结论：
- 前提/边界：
- 是否应提炼为概念卡：[[概念名]]（留空表示待决定）

### 结论 2
- 结论：
- 前提/边界：
- 是否应提炼为概念卡：[[概念名]]

### 引用资源
- [ ] 电子资料链接：
- [ ] 教材页码：

---

## 阶段二：费曼整理
（课后在此文件内直接整理，或新建概念卡后在此引用）

### 我的理解
（用自己的话复述这节课的核心思想）

### 与已有知识的关联
- 关联概念：[[ ]]
- 与之前课程的衔接：

### 信息流失检查
- [ ] 老师提到但我没记的：是遗漏还是主动舍弃？
- [ ] 我标记的结论：理解是否可能偏差？
- [ ] 我的猜测 vs 老师讲的内容：有无混淆？

---

## 行动输出
（这节课直接导致的行动或项目决策）
- 项目笔记：[[ ]]
- 待办：
  - [ ]
```

**Key mechanism:** `[[概念名]]` leverages Obsidian's wikilinks. If the concept card doesn't exist, it appears as a gray link. Click after class to auto-create the blank file, then move it to `10-Concepts/`.

### 3. Project Notes (`00-Meta/模板/项目笔记.md`)

Where concepts are combined into situational methods.

```markdown
---
type: project
domain:
status: draft
created: {{date:YYYY-MM-DD}}
modified: {{date:YYYY-MM-DD}}
source:
tags: []
---

# {{title}}

## 目标
- **量化目标**：
- **截止期限**：
- **每日时间预算**：

## 核心判断
（基于哪些概念做出了这个项目的设计？）
- [[概念A]] → 因此决定：
- [[概念B]] → 因此决定：

## 方法设计
（方法是概念在约束条件下的临时组合）
### 阶段 X
- **概念支撑**：[[ ]]
- **具体动作**：
- **工具**：
- **验证标准**：

## 进度追踪
| 周期 | 计划 | 实际 | 偏差原因 |
|------|------|------|----------|
| 第1周 | | | |

## 问题与调整
- **问题**：
- **假设**：
- **实验**：
- **结论**：

## 复盘总结
- 哪些判断是正确的？
- 哪些概念需要修正？
- 下次复用这个项目的方法时，注意什么？
```

**Rule:** After a project ends, valuable methodology should be abstracted into concept cards, not left in project notes.

### 4. Daily Review (`00-Meta/模板/每日复盘.md`)

Organized by projects and concepts, not by subject task lists.

```markdown
---
type: daily
domain:
status: draft
created: {{date:YYYY-MM-DD}}
modified: {{date:YYYY-MM-DD}}
source:
tags: []
---

# {{date:YYYY-MM-DD}} 学习日记

## 今日聚焦项目
（今天主要推进哪个项目？）
- [[项目名]]

## 今日输入
（看过的课程/读过的资料）
| 时间 | 内容 | 产出概念卡 |
|------|------|-----------|
| | | [[ ]] |

## 概念触动
（今天有没有哪个已有概念被新信息验证或修正？）
- [[概念名]]：我的理解发生了什么变化？

## 执行数据
| 项目 | 计划时长 | 实际时长 | 完成度 |
|------|----------|----------|--------|
| | | | |

## 明日决策
- 基于今天的数据，哪个概念/假设需要调整？
- 明天的核心动作是什么？
```

## Visual Aesthetics (No Plugins)

Use Obsidian native Callouts for visual hierarchy:

```markdown
> [!info] 来源
> 讲师课程第3节，约15分钟处

> [!warning] 边界
> 此结论仅在"专业课时间紧张"时成立

> [!tip] 我的版本
> 我用手机背单词时，只记大意，不点开详细释义

> [!question] 待验证
> 墨墨的算法是否真的与快速重复冲突？需测试3天
```

| Callout Type | Color | Use For |
|-------------|-------|---------|
| `[!info]` | Blue | Sources, definitions |
| `[!warning]` | Orange | Boundaries, counterexamples, risks |
| `[!tip]` | Green | Personal understanding, adjustments |
| `[!question]` | Purple | Unverified hypotheses, experiments |

Use `---` horizontal rules to separate stages within course notes.

## Linking Philosophy

```
Course Notes → Concept Cards (upward extraction)
  [[导学课]] mentions [[边际效应]]...

Project Notes → Concept Cards (upward traceability)
  Based on [[边际效应]], decided to target 80 points...

Concept Cards → Concept Cards (lateral association)
  [[过度学习原则]] often pairs with [[间隔重复]]...
```

**Graph View check:** Open Graph View, color by `domain`. You should see:
- Dense cluster: Concepts (many interconnections)
- Radiating spokes: Subjects (pointing to concepts)
- Radiating spokes: Projects (pointing to concepts)

## Two-Stage Workflow in Obsidian

### Stage 1: During Class
1. Create note in `30-Subjects/Subject/Course-Name/`
2. Use Course Notes template
3. In "阶段一：结论捕获", quickly fill:
   - Conclusion (one sentence)
   - Premise/boundary (if mentioned)
   - For important conclusions, immediately type `[[ConceptName]]`
4. Record resource links

### Stage 2: Within 24 Hours
1. Return to the same course note
2. Fill "阶段二：费曼整理":
   - Restate in your own words
   - Check information loss checklist
3. For items marked with `[[ConceptName]]`:
   - Click gray link → Obsidian auto-creates blank file
   - Move file to `10-Concepts/Domain/`
   - Apply Concept Card template
   - Ensure no course-specific context in concept card
4. In concept card's `来源与验证`, link back: `来源：[[课程笔记名]]`
5. If class led to action plans:
   - Update project note in `20-Projects/`
   - Link from course note's "行动输出" section

## Common Pitfalls

| Pitfall | Prevention |
|---------|------------|
| Concept cards accumulate course context | Strict template enforcement; "考研版" forbidden |
| Methods become standalone cards | Always ask "Which concepts support this method?" |
| Course notes become permanent knowledge | Course notes are raw material; concept cards are permanent |
| Link maintenance overhead too high | Use Backlinks panel; Obsidian auto-tracks incoming links |
| "No inbox" causes quality inconsistency | Status field (`draft` → `reviewing` → `mature`) tracks maturity |
| Cross-disciplinary concepts hard to categorize | Allow multiple `domain` values (YAML array) |

## Validation Checklist

After implementing, verify:
- [ ] Graph View shows 3 clear clusters (Concepts dense, Subjects/Projects radiating)
- [ ] Any course note can reach its extracted concept cards within 3 seconds
- [ ] Any project note can trace back to supporting concept cards within 3 seconds
- [ ] Concept index page (`00-Meta/索引/概念索引.md`) auto-completes via `[[` for all concept cards
- [ ] Daily review no longer lists tasks by subject, but records "concept touches"
- [ ] Course notes do not serve as permanent knowledge storage
