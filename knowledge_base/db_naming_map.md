# DB Naming Map — UI ↔ Database — {COMPANY}

> Hand-curated translation between product/UI terminology and actual table/column names.
> Read this BEFORE writing any DB query so you don't search for non-existent tables.

---

## Why this file exists

Table names rarely match UI terms. "Customer" in product is often `users` in DB. Without this map, every query starts with hunting through `information_schema`.

(Document FK / referential integrity practice if any: at DB level / app level.)

---

## Core entity mapping

| UI term | DB table(s) | Notes |
|---|---|---|
| (entity) | `(table_name)` | (notes on join columns, soft delete, etc.) |

---

## Sensitive columns (privacy-protected fields)

If product has 2FA-protected / privacy-sensitive cols, list here:

| Column path | Meaning |
|---|---|
| `(table.column)` | (description) |

---

## Conventions observed in the schema

- **Audit columns**: `created_at`, `updated_at`?
- **Authoring columns**: `created_by_*`?
- **Soft delete**: `deleted_at`?
- **Multi-tenancy**: `tenant_id` / `organization_id`?
- **External integrations**: prefix patterns?

---

## Open questions / TBD

- [ ] Where is **(entity)** stored?
- [ ] (Other unknowns)

---

## How to query safely

Always use the read-only wrapper:

```bash
scripts/db-query.sh "SELECT id, email FROM users WHERE id = 12345"
scripts/db-query.sh --json --db <env> "SELECT * FROM ..."
```

Three layers of defence: server-side read-only role + transaction read-only + client regex guard.

---

## Refresh cadence

```bash
scripts/refresh-db-schema.sh --all
```

Updates `kb_cache/db/raw_schema.json` and rebuilds `knowledge_base/db_schema__*.{md,json}`. This file (`db_naming_map.md`) is hand-curated — manually add new entries when new tables appear.
