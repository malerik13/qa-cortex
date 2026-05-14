# Recommendation Block Format — mandatory response closing

> **Load when:** brain is composing a substantive reply with decision point or next-step ambiguity.
>
> **Lazy-load trigger:** writing reply that ends with options, when multiple paths possible.

---

## When required

**Every substantive reply ends with a recommendation block.** Применять для любого ответа где есть:
- decision point
- next-step ambiguity
- multiple options

**When to SKIP:**
- Trivial ack («да», «ок», «понял»)
- Pure status output (no decision implied)
- Read-only-status-checks where there's nothing to decide

---

## Two parts

### Part 1 — text summary (after `---` separator)

```
---
**Дальше:** <1-3 короткие опции / следующих шагов>
**Рекомендую:** <X> — <одной фразой почему>
**Модель/усилие:** <Sonnet 4.6 standard | Sonnet 4.7 standard | Sonnet 4.7 xhigh | Opus 4.7 standard | Opus 4.7 xhigh | Sonnet 4.5 (1M)>
```

### Part 2 — `AskUserQuestion` tool call (when 2+ real alternatives)

Loaded via `ToolSearch select:AskUserQuestion` if not already.

**When to use AskUserQuestion vs plain text:**

| Decision shape | Use |
|---|---|
| 1 reasonable path, just need confirmation | **Plain text** in Part 1: «Делаем X? Запускаю если ок» — нет смысла строить menu |
| 2-4 real alternatives | **AskUserQuestion** with exact count of options (NOT padded) |
| 5+ alternatives | Группируй в 3-4 категории, иначе menu становится паралич выбора |

**Critical rule (calibrated 2026-05-13):**
- **Options = real alternatives count, never padded.** Если 2 реальных пути — 2 options. Не лепи 3-4 если третий filler типа «show diff first».
- Лучше plain text question + 2 options чем AskUserQuestion с искусственными вариантами.

**Parameters (when using):**
- `question` — короткая постановка («Что делаем дальше?» / «Какой fix запускаем?»)
- `header` — chip-метка ≤12 chars («Next step», «Fix path», «Approach»)
- `options` — **2-4 вариантов, столько сколько реальных альтернатив**:
  - **Первый = recommended** с суффиксом «(Recommended)» в label
  - В `description` — trade-off / impact одной фразой
  - НЕ добавлять «Other» — система добавит автоматически

Опции зеркалят то что в Part 1, но в кликабельном виде. User тыкает → instant decision без печати.

**Examples:**

✅ **Right (1 path → plain text):**
> Готов commit `<message>`. Push origin/main. Делаем?

✅ **Right (2 real alternatives):**
> AskUserQuestion: [Push сейчас (Recommended) · Сначала diff покажи]

✅ **Right (3 real choices):**
> AskUserQuestion: [merge to main (Recommended) · PR through GitHub UI · keep feature branch as WIP]

❌ **Wrong (padded options):**
> AskUserQuestion: [Push (Recommended) · Diff first · Cancel · «Other»] — последние два filler

❌ **Wrong (menu for binary):**
> AskUserQuestion: [Yes · No] — better as plain «делаем?» в тексте

---

## Model/effort rubric (short form)

Full rubric: `orchestrator_persona §13`.

| Task pattern | Recommendation |
|---|---|
| Routine QA (read ticket, draft bug, fetch AC, journal log) | **Sonnet 4.6 standard** |
| Standard test planning, AC parsing, scenario generation | **Sonnet 4.7 standard** |
| Ambiguous AC, severity calibration, cross-ref reasoning, audit | **Sonnet 4.7 xhigh** |
| Strategic / fuzzy / multi-system architecture / calibration analysis | **Opus 4.7 xhigh** |
| Big-batch reads (KB sync, multi-session forensic, doc consolidation) | **Sonnet 4.5 (1M)** |
| Long-running automation (regression run, multi-ticket triage) | **Sonnet 4.6 standard** (cheap, durable) |
| Critical architecture session (new mode, major refactor) | **Opus 4.7 max** |

---

## Honesty rule

Always state honest recommendation — даже если user уже выбрал модель, если она overkill / underkill — surface'ить как «модель overkill, можно switch на X для cost».

Don't recommend Opus reflexively for "important" tasks — most QA work is pattern-matching, Sonnet handles fine.

Don't recommend Haiku for QA decisions — too weak for severity/AC judgement; only for mechanical loops.

---

## Examples

### Example 1 — clear next step

```
Готов commit `feat: phase 4 calibration`. Все 9 правок применены.

---
**Дальше:** push now / show diff first / cancel commit
**Рекомендую:** push now — diff виден в git status, ничего скрытого
**Модель/усилие:** Sonnet 4.6 standard

[AskUserQuestion with same 3 options]
```

### Example 2 — strategic fork

```
Два пути архитектуры: (a) 3 separate subagents, (b) hybrid mode-based.

---
**Дальше:** (a) полное разделение / (b) hybrid / (c) больше анализа
**Рекомендую:** (b) hybrid — coordination overhead меньше, current usage patterns говорят за overlap
**Модель/усилие:** Opus 4.7 xhigh

[AskUserQuestion with 3 options]
```

---

## Source

- CLAUDE.md v6.0 (initial spec)
- v0.7.2 calibration (added xhigh tier, refined rubric)
