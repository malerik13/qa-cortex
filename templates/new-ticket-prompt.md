# 🎯 New Ticket — Session Kickoff Prompts

> Copy-paste templates to start a fresh Claude Code session per ticket.
> One ticket = one session (clean context, no contamination).
>
> **Always run from `~/Documents/ScaleFinal/`** — otherwise plugin/MCP/KB won't load.
> ```bash
> cd ~/Documents/ScaleFinal && claude
> ```

---

## Универсальный промпт (закрывает 90% случаев)

```
Тикет: TRD-XXXXX
Окружение: staging
Что нужно: [test-plan | bug-report | by-design check | explore | related]
Контекст (если есть): [симптом / фича / что уже пробовал]

Действуй:
1. Прочитай AC из YouTrack (MCP get_ticket + get_comments).
2. Проверь связи (get_linked_tickets) — чтобы я понимал регрессионные риски.
3. Сверься с локальными insights/business_rules — нет ли уже известного бага рядом.
4. Выдай результат по выбранному формату.

Если AC неоднозначен или отсутствует — скажи прямо, не выдумывай.
```

---

## Сокращение №1 — «Просто протестируй»

```
/test TRD-XXXXX
Окружение: staging-ca
```

> Slash-команда сама позовёт субагента `test-planner` с изолированным контекстом.

---

## Сокращение №2 — «Баг или by design?»

```
/bydesign

Что вижу: [симптом]
Где: [URL / модуль / клиент-ID]
Тикет фичи (если знаю): TRD-XXXXX
```

---

## Сокращение №3 — «Напиши баг-репорт»

```
/bug

Симптом: [что сломалось]
Шаги: [1, 2, 3]
Ожидал: [по AC такой-то]
Получил: [фактическое]
Окружение: staging
Связанная User Story (если знаю): TRD-XXXXX
```

> Я пройду по шагам уточнений и заполню EN-шаблон, покажу draft на ревью перед YouTrack.

---

## Доп. команды вне шаблона

| Что нужно | Команда |
|-----------|---------|
| Глубокое исследование фичи (история, AC, баги) | `/explore <фича>` напр. `/explore 2FA` |
| Граф связей вокруг тикета | `/related TRD-XXXXX` |
| Changelog по версии | `/whatchanged 2.9` |
| Обновить KB (раз в спринт) | `обнови индекс` |
| Дайджест Slack | `/slack-analyze` |

---

## Что я делаю автоматически (не нужно напоминать)

- Бизнес-правила 2FA, экспортов, Desk-иерархии — учитываю
- Окружения (staging / staging-ca / release / release-ca / demo / prod) и тест-аккаунты — знаю
- Известные баги (TRD-13526 toast, TRD-13527 backdrop, etc.) — узнаю и не дублирую
- Все артефакты (баги, тест-планы, кейсы) — на английском
- Чат с тобой — на русском
- Перед "by design" — всегда цитирую AC из KB; без AC честно говорю «не знаю»

---

## Когда обновлять KB

Раз в спринт или когда SessionStart hook предупредит о устаревании.
Команда: `обнови индекс` (skill `kb-refresh`) или вручную:
```bash
.venv/bin/python scripts/update-kb.py && .venv/bin/python scripts/build-graph.py
```
