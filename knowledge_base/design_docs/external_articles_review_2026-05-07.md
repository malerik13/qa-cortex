# External articles review — Habr "Second Brain" theme

> Reviewed: 2026-05-07 (overnight, Yaroslav was sleeping)
> Articles: habr.com/ru/articles/1031970 + 1031112
> Theme: building "Second Brain" / LLM-Wiki for AI agents using Obsidian + Claude Code

---

## TL;DR — что брать, что не брать

| Идея из статей | Применимость к нашему проекту | Action |
|---|---|---|
| **3-layer architecture: Raw → Wiki → Schema** | ✅ Уже есть: source files → product_map → brain consumption | Validation that we're on right track |
| **3 операции: Ingest / Query / Lint** | 🟡 Ingest есть (crawlers), Query есть (brain reads). **Lint отсутствует.** | **Add lint script** — Phase A.5 |
| **Wikilinks `[[]]` over vector search** | 🟢 Соответствует нашему Path 3 (Obsidian-flavor). Brain парсит, человек кликает | **Adopt convention** в KB cross-refs |
| **LLM-Wiki vs RAG** | ✅ Мы LLM-Wiki style — compile once, cheap query | Validate подход |
| **~100 sources optimal scale** | ✅ У нас ~30 KB sources + ~3 recipes — хорошо в пределах | Reassuring |
| **PARA structure (Projects/Areas/Resources/Archive)** | ⚠️ Альтернатива нашей module taxonomy. PARA фокусируется на life-management, не product-domain | Skip — наш module split лучше для QA |
| **Different formats for human vs AI consumers** | 🔥 **Critical insight** — мы строим AI-side, journal/* = human-side. Не смешивать | **Add explicit boundary в master plan** |
| **Risk: AI-generated bloat вместо authentic notes** | ⚠️ Применимо к нашему journal — следить чтобы dev-log + log оставались твоими записями | Add anti-pattern note |
| **Karpathy x473 GitHub repos surge** | ℹ️ Indicates это hot space — много open source инструментов появится | Periodic re-scan |

---

## Article 1 (1031970) — "Второй мозг и LLM-Wiki" (hands-on guide)

### Главная идея

Описывает практический подход построения личной KB через LLM-агенты. Ключевая инновация: **компиляция знаний один раз** (LLM-Wiki) вместо RAG-style runtime aggregation.

### Архитектура (3 слоя)

1. **Raw sources** — пользовательские входы (заметки, документы, beauty)
2. **Wiki** — обработанная структура с явными `[[wikilinks]]`
3. **Schema** — машинно-читаемая декларация структуры (для агента)

### 3 операции

- **Ingest** — добавление новых источников
- **Query** — поиск с использованием графа связей
- **Lint** — проверка целостности (битые ссылки, missing required frontmatter, etc.)

### Сравнение с нашим проектом

| Их слой | Наш аналог | Match |
|---|---|---|
| Raw sources | `journal/*`, `bugs.json`, recipes (auto-distilled in Phase B) | ✅ |
| Wiki | `knowledge_base/*.md` + `flows/*.recipe.md` | ✅ |
| Schema | `knowledge_base/product_map.json` + `flows/_index.json` + `_module_taxonomy.json` | ✅ |
| Ingest op | Нет автоматизации — `journal.sh log/bug`, manual recipe distillation | 🟡 partial |
| Query op | Brain читает map slice + targeted KB | ✅ |
| **Lint op** | **Отсутствует** | ❌ **gap** |

### Что взять — Lint operation

Добавить `scripts/lint-kb.py` который проверяет:

1. **Recipe frontmatter completeness** — все required fields присутствуют (per flow_cache_v1 §4.2)
2. **Module references valid** — recipe.area существует в _module_taxonomy.json
3. **Wikilinks resolve** — `[[file]]` или `[[file#section]]` указывают на существующие
4. **No orphan tags** — tags в bugs.json/recipes должны быть в taxonomy keywords (или явно whitelisted)
5. **Stale recipes flag** — `last_verified > 30 days`
6. **Index sync** — `_index.json` matches filesystem state

Run via git pre-commit hook + CI. Возвращает non-zero на ошибках.

**Effort:** ~2-3ч в Phase A.5 (между Product Map A и B).

### Что не взять — PARA structure

PARA — методология Tiago Forte (Projects/Areas/Resources/Archive). Заточена под personal life management. Наш product-domain module split (auth, client-mgmt, ...) точнее для QA-задач. PARA подразумевает temporal классификацию (active project vs archived), у нас семантическая (по продукту).

---

## Article 2 (1031112) — "Второй мозг строят все. Но большинство — не для себя"

### Главная идея

Различает **human-side** vs **AI-side** Second Brain:

- **Human-side**: инструмент для собственного мышления, ценность через годы. Цель: «заметки написанные не зная зачем» → озарения позже.
- **AI-side**: инфраструктура контекста для агентов, immediate utility. Цель: эффективность операций.

Эти системы **разные форматы, разные критерии успеха, разные maintenance patterns**.

Автор предупреждает: AI агенты решили проблему «too expensive to maintain» (главный исторический барьер personal KB), но создали новую: **смешивание двух парадигм** → получаешь ни ту, ни другую.

### Применимость к нашему проекту

🔥 **Это критически важное различие для нас.**

| Артефакт | Side | Кто ведёт | Кто читает |
|---|---|---|---|
| `knowledge_base/qa_persona.md` etc. (personas) | AI-side | brain self-edits | brain |
| `flows/*.recipe.md` | AI-side | auto-distilled (Phase B) | brain |
| `product_map.json` | AI-side | crawler-generated | brain |
| `_module_taxonomy.json` | Hybrid | hand-curated | brain |
| `business_rules.md`, `ui_flows.md`, `db_naming_map.md` | Hybrid | hand-curated by Yaroslav, brain reads | both |
| **`journal/<DATE>.md` (QA log)** | **Human-side** | **Yaroslav decides verbatim** | Yaroslav (standup) + occasional brain |
| **`journal/dev/<DATE>.md` (build chat)** | **Hybrid leaning Human** | Yaroslav-curated, brain auto-suggests | Yaroslav |
| `qa-output/intake.md`, `cockpit.md` | AI-side | brain | both |
| `insights.md` | Hybrid | hand-written by Yaroslav, brain auto-suggests entries | both |

**Critical risk** highlighted by article: **journal'ы могут засориться auto-generated bloat** если brain начнёт писать туда. Anti-pattern уже зафиксирован (CLAUDE.md anti-pattern #4: «Don't pollute QA journal with meta-build noise»). Но article 2 раздувает эту угрозу: даже non-meta auto-generated content в personal-side артефакты — risk to authentic thinking.

### Что взять — Explicit boundary в master plan

Добавить раздел в `qa_brain_master_plan.md`:

```markdown
## Brain artefacts — human-side vs AI-side

Following Habr article 1031112 framing — explicit categorisation:

**AI-side** (brain works freely, may auto-generate, optimised for brain consumption):
- knowledge_base/qa_persona.md, orchestrator_persona.md, qa_workflow.md
- flows/*.recipe.md (Phase B+ auto-distilled)
- knowledge_base/product_map.json (auto-generated)
- knowledge_base/bugs.json (auto-generated)
- qa-output/* (per-session artefacts)

**Hybrid** (Yaroslav curates, brain reads, brain may suggest edits with approval):
- knowledge_base/business_rules.md, ui_flows.md, glossary.md, db_naming_map.md
- knowledge_base/insights.md (Yaroslav writes, brain reads)
- knowledge_base/_module_taxonomy.json

**Human-side** (Yaroslav's authentic record, brain doesn't write):
- journal/<DATE>.md (QA standup history)
- journal/dev/<DATE>.md (meta-build chronicle, brain may help format but content from Yaroslav)
- knowledge_base/qa_brain_master_plan.md decision log sections

Anti-pattern: brain auto-writing to human-side artefacts. Brain may *suggest*
edits via journal.sh log/dev-log commands but content originates with Yaroslav.
```

### Что взять — Karpathy surge signal

Article cites x473 GitHub репозиториев на тему за 5 лет, рост после твита Карпатого. Indicates space движется быстро. **Recommendation:** ежеквартальный re-scan landscape — что появилось из community-инструментов что можем reuse вместо custom.

---

## Что НЕ берём — критическая оценка

| Не берём | Почему |
|---|---|
| **Полноценный Obsidian vault makeover** | Уже обсуждали — Path 1 premature. Stay custom + adopt conventions (Path 3 light) |
| **Vector / RAG infrastructure** | Articles явно говорят что для ~100 sources LLM-Wiki выигрывает. Мы при 30. RAG = overkill. |
| **PARA structure** | Не подходит для product-domain |
| **Тяжёлая graph DB** | Out of scope. JSON tree достаточен. |
| **Karpathy-style "vibe coding" agentic workflows** | Не упоминается напрямую в этих 2 статьях, но связанная тема. Не наш профиль — мы Senior QA, не yolo agents. |

---

## Concrete additions проекта (по результатам review)

### Now (autonomous overnight session, 2026-05-07)

1. ✅ Phase A Product Map crawler (was in flight)
2. ✅ This review document
3. ⏳ Lint operation skeleton — propose в morning brief, не implement без approval

### Next session (when Yaroslav wakes up)

1. **Decide:** add `scripts/lint-kb.py` with rules from Article 1's lint operation? (~2-3ч)
2. **Decide:** add explicit human/AI-side boundary section в master plan?
3. **Decide:** quarterly external landscape rescan — schedule в calendar / journal?
4. **Decide:** continue Phase B Product Map (extend to 7 more sources)?

---

## Honest take

Эти статьи **подтверждают что мы на правильном пути.** 3-layer arch, LLM-Wiki style, module taxonomy — convergent design с industry-direction.

**Но** Article 2 даёт fresh angle что мы ещё не зафиксировали явно: **separation of concerns** между AI-side и human-side артефактами. Это deserves explicit anti-pattern, иначе через год journal будет засорён brain-output вместо твоих standup-фактов.

**Lint operation** — единственный конкретный gap который заслуживает immediate addition. Cheap (~2-3ч), reduces drift risk, integrates with git hooks.

Всё остальное — validation, не new requirements.
