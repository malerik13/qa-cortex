# UI Flows — Verified Navigation Paths

> Hand-curated, verified UI navigation patterns for your product.
> Read BEFORE describing any UI navigation in chat.
> Per CLAUDE.md anti-pattern #6 (UI navigation anti-hallucination): NEVER invent a UI path.

---

## Why this file exists

UI navigation map for your product. Used by brain when:
- User asks «as create X in UI?» — brain checks here first
- Recipe distillation needs verified path
- Bug report «steps to reproduce» needs UI path

If a path isn't here, brain MUST verify via Playwright (`browser_navigate → browser_snapshot`) before claiming.

---

## §1 Authentication flow

(empty — fill as you discover and verify paths)

---

## §2 (your-module-1) navigation

(empty — fill as you go)

---

## §3 (your-module-2) navigation

(empty)

---

## Format

When adding a flow:

```markdown
### Open Client Card by Client ID

1. Click `Operations` in main nav
2. Click `Clients` in submenu
3. Type Client ID in search input
4. Click matching row
5. Wait for client card to load

**Verified on:** stage env, 2026-05-07 (TRD-XXXXX)
**Selectors:** see `flows/client-mgmt/open-client-card.recipe.md`
```

Always include: verified-when + verified-on-which-env.
