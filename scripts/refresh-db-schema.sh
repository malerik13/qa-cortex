#!/usr/bin/env bash
# Refresh DB schema dump for any registered project DB.
#
# Usage:
#   scripts/refresh-db-schema.sh                  # default: stage
#   scripts/refresh-db-schema.sh --db release     # specific DB
#   scripts/refresh-db-schema.sh --all            # refresh every registered DB
#
# Output paths (per --db <name>):
#   kb_cache/db/<name>/raw_schema.json
#   knowledge_base/db_schema__<name>.md
#   knowledge_base/db_schema__<name>.json
#
# Read-only — only runs the introspection SELECT via psql. The DB role
# (member of readonly_role) cannot write at server side anyway.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if [[ ! -f .env ]]; then
  echo "❌ .env not found at $ROOT/.env" >&2
  exit 1
fi

set -a
# shellcheck disable=SC1091
source .env
set +a

if ! command -v psql >/dev/null 2>&1; then
  echo "❌ psql not found. brew install libpq && brew link --force libpq" >&2
  exit 1
fi

# ── DB name → env-var prefix (mirrors db-query.sh) ────────────
resolve_prefix() {
  case "$1" in
    stage|crm_stage)        echo "CRM_STAGE_DB" ;;
    release|release_logs)   echo "CRM_RELEASE_DB" ;;
    *)                      echo "$(echo "$1" | tr '[:lower:]' '[:upper:]')_DB" ;;
  esac
}

# All known DB names — used by --all. Update when new DBs join.
KNOWN_DBS=("stage" "release")

# ── parse args ────────────────────────────────────────────────
DB_NAMES=()
ALL_FLAG=0
while [[ $# -gt 0 ]]; do
  case "$1" in
    --db) DB_NAMES+=("$2"); shift 2 ;;
    --all) ALL_FLAG=1; shift ;;
    -h|--help) sed -n '2,15p' "$0"; exit 0 ;;
    *) echo "❌ Unknown arg: $1" >&2; exit 1 ;;
  esac
done

if [[ $ALL_FLAG -eq 1 ]]; then
  DB_NAMES=("${KNOWN_DBS[@]}")
elif [[ ${#DB_NAMES[@]} -eq 0 ]]; then
  DB_NAMES=("stage")
fi

# ── refresh one DB ────────────────────────────────────────────
refresh_one() {
  local name="$1"
  local prefix
  prefix=$(resolve_prefix "$name")
  local host_var="${prefix}_HOST"
  local port_var="${prefix}_PORT"
  local dbn_var="${prefix}_NAME"
  local usr_var="${prefix}_USER"
  local pwd_var="${prefix}_PASSWORD"
  local ssl_var="${prefix}_SSLMODE"

  for v in "$host_var" "$port_var" "$dbn_var" "$usr_var" "$pwd_var"; do
    if [[ -z "${!v:-}" ]]; then
      echo "❌ [$name] missing env $v in .env" >&2
      return 1
    fi
  done

  local out_dir="kb_cache/db/$name"
  mkdir -p "$out_dir"
  local raw="$out_dir/raw_schema.json"

  echo "→ [$name] dumping schema from ${!host_var}/${!dbn_var} ..."
  PGPASSWORD="${!pwd_var}" psql \
    "host=${!host_var} port=${!port_var} dbname=${!dbn_var} user=${!usr_var} sslmode=${!ssl_var:-require} connect_timeout=15" \
    -At -o "$raw" -f scripts/sql/dump-schema.sql

  echo "→ [$name] building docs ..."
  python3 scripts/build-db-schema-doc.py --db "$name"

  echo "✓ [$name] refreshed."
}

for db in "${DB_NAMES[@]}"; do
  refresh_one "$db" || { echo "❌ Failed for $db" >&2; exit 1; }
done

echo
echo "✓ All requested DBs refreshed."
