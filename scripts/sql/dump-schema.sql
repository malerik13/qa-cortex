-- Schema introspection query.
-- Outputs a single JSON object describing all tables, columns, indexes, and constraints
-- in non-system schemas. Read-only.
SELECT json_build_object(
  'meta', json_build_object(
    'database', current_database(),
    'pg_version', current_setting('server_version'),
    'extracted_at', now(),
    'role', current_user
  ),
  'tables', (
    SELECT json_agg(t ORDER BY t.schema_name, t.table_name)
    FROM (
      SELECT
        n.nspname AS schema_name,
        c.relname AS table_name,
        c.reltuples::bigint AS approx_rows,
        pg_size_pretty(pg_total_relation_size(c.oid)) AS total_size,
        obj_description(c.oid) AS table_comment,
        (
          SELECT json_agg(col ORDER BY col.ordinal_position)
          FROM (
            SELECT
              a.attnum AS ordinal_position,
              a.attname AS name,
              format_type(a.atttypid, a.atttypmod) AS type,
              NOT a.attnotnull AS nullable,
              pg_get_expr(d.adbin, d.adrelid) AS default_value,
              col_description(c.oid, a.attnum) AS comment
            FROM pg_attribute a
            LEFT JOIN pg_attrdef d ON d.adrelid = a.attrelid AND d.adnum = a.attnum
            WHERE a.attrelid = c.oid AND a.attnum > 0 AND NOT a.attisdropped
          ) col
        ) AS columns,
        (
          SELECT json_agg(idx)
          FROM (
            SELECT
              i.relname AS name,
              ix.indisprimary AS is_primary,
              ix.indisunique AS is_unique,
              pg_get_indexdef(ix.indexrelid) AS definition
            FROM pg_index ix
            JOIN pg_class i ON i.oid = ix.indexrelid
            WHERE ix.indrelid = c.oid
          ) idx
        ) AS indexes,
        (
          SELECT json_agg(con)
          FROM (
            SELECT
              co.conname AS name,
              CASE co.contype
                WHEN 'p' THEN 'primary_key'
                WHEN 'u' THEN 'unique'
                WHEN 'c' THEN 'check'
                WHEN 'f' THEN 'foreign_key'
                WHEN 'x' THEN 'exclude'
              END AS type,
              pg_get_constraintdef(co.oid) AS definition
            FROM pg_constraint co
            WHERE co.conrelid = c.oid
          ) con
        ) AS constraints
      FROM pg_class c
      JOIN pg_namespace n ON n.oid = c.relnamespace
      WHERE c.relkind IN ('r','p')
        AND n.nspname NOT IN ('pg_catalog','information_schema')
    ) t
  )
);
