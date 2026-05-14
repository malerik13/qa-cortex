# PARALLEL Tool Execution — mandatory pattern

> **Load when:** brain is about to make >1 tool call. Or when reasoning whether to batch tool calls.
>
> **Lazy-load trigger:** «параллель», «multi tool», «batch», «independent calls», debugging slow tool execution.

---

## The rule (hard)

If N tool calls are **independent** (none uses output of another) → emit **ALL in ONE assistant message** as multiple `tool_use` blocks. Not as N sequential assistant messages.

This is mandatory, not optimization. Sequential emission when parallelism is possible = regression.

---

## The failure mode

**Observed (TRD-13812 retest 2026-05-06):** brain wrote «Запускаю параллельную загрузку контекста», intended 4 parallel MCP calls, but emitted them in 4 separate assistant messages — sequential, not parallel. **4 round trips of latency for 0 benefit.**

The trap: intent matches "parallel" but emission is sequential. The model THOUGHT it was parallel because it intended to be.

---

## Anti-pattern (forbidden)

```
Assistant message 1: <text "Запускаю..."> + <tool_use: get_ticket>
                   ← wait for tool_result
Assistant message 2: <tool_use: get_linked_tickets>
                   ← wait for tool_result
Assistant message 3: <tool_use: get_comments>
                   ← wait for tool_result
Assistant message 4: <tool_use: find_test_cases_by_issue>
                   ← wait for tool_result
```

---

## Correct pattern

```
Assistant message 1: <text "Запускаю параллельную загрузку...">
                   + <tool_use: get_ticket>
                   + <tool_use: get_linked_tickets>
                   + <tool_use: get_comments>
                   + <tool_use: find_test_cases_by_issue>
                   ← all 4 tool_results return in parallel, ONE round trip
```

---

## When parallel applies (independent calls)

- Pre-load context for a ticket (4 MCP reads on same TRD-ID)
- Multi-file `Read` calls (multiple KB files)
- Parallel `Bash` checks (status + diff + log)
- Tool research (multiple `WebFetch` for unrelated URLs)
- Audit / discovery — search multiple files / sources at once

---

## When sequential is required (dependency)

- Subsequent call needs output of prior (search ticket → use ID in next call)
- Conditional logic (if X exists then call Y)
- State-affecting calls in sequence (login → action → assert)

---

## Self-check (mandatory)

Before sending response: if you've decided to call N independent tools, count `tool_use` blocks in your current assistant turn.

- N? Good.
- <N? **Stop. Repack into one message.**

---

## Trigger phrase to catch yourself

«Вызвал X, теперь жду результат, потом вызову Y» — for independent X and Y → that's the regression. Restructure into single message.

The mental anti-pattern: «sequential narrative feels safer because I see each result before next call». In reality, for INDEPENDENT calls, you don't need each result — you batch and read all together.

---

## R1/R2/R3 wave pattern (multi-agent decomposition)

The same principle applies recursively when decomposing into sub-agents:

- R1 = parallel discovery wave (all independent reads in ONE message with N `Agent` tool_use blocks)
- R2 = targeted deep-dive (may be parallel or sequential per dependency)
- R3 = synthesis

See `orchestration_playbook.md` Rule 3 for full pattern.

---

## Source

- TRD-13812 retest 2026-05-06 (failure observed + rule codified)
- v0.7.2 orchestration_playbook (recursively applies to delegation layer)
