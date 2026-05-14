#!/usr/bin/env bash
# Safe wrapper for ad-hoc read-only queries against any registered project DB.
#
# Multi-DB: pick which database via --db <name>. Looks up env vars by prefix
# derived from the name: e.g. --db stage → CRM_STAGE_DB_*, --db release →
# CRM_RELEASE_DB_*. Default: stage.
#
# Defense-in-depth: even though the DB role is server-side read-only, this
# script also refuses anything that looks like a write. Belt + suspenders.
#
# Usage:
#   scripts/db-query.sh "SELECT count(*) FROM traders"
#   scripts/db-query.sh --db release "SELECT count(*) FROM <table>"
#   scripts/db-query.sh -f path/to/query.sql
#   scripts/db-query.sh --json --db stage "SELECT id, email FROM traders LIMIT 5"
#
# .env must define for each DB <NAME>:
#   <NAME>_DB_HOST, <NAME>_DB_PORT, <NAME>_DB_NAME, <NAME>_DB_USER,
#   <NAME>_DB_PASSWORD, <NAME>_DB_SSLMODE (optional, default 'require')
#
# Built-in name → env-prefix mapping:
#   stage    → CRM_STAGE_DB
#   release  → CRM_RELEASE_DB
# Add more aliases below in `resolve_prefix()` as new DBs join the project.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

set -a
# shellcheck disable=SC1091
source .env
set +a

if ! command -v psql >/dev/null 2>&1; then
  echo "❌ psql not found. brew install libpq && brew link --force libpq" >&2
  exit 1
fi

# ── DB name → env-var prefix ─────────────────────────────────
resolve_prefix() {
  case "$1" in
    stage|crm_stage)             echo "CRM_STAGE_DB" ;;
    stage-ca|crm_stage_ca)       echo "CRM_STAGE_CA_DB" ;;
    release|crm_release)         echo "CRM_RELEASE_DB" ;;
    release-ca|crm_release_ca)   echo "CRM_RELEASE_CA_DB" ;;
    *)
      # Generic fallback: uppercase the name (dashes → underscores) and append _DB
      # e.g. --db myapp → MYAPP_DB_HOST, --db foo-bar → FOO_BAR_DB_HOST
      echo "$(echo "$1" | tr '[:lower:]-' '[:upper:]_')_DB"
      ;;
  esac
}

# ── List available DBs from .env (calibrated 2026-05-13 from {TICKET_PREFIX}-XXXXX) ───
list_available_dbs() {
  echo "Available DBs (detected via *_DB_HOST in .env):" >&2
  grep -E '^[A-Z_]+_DB_HOST=' .env 2>/dev/null | sed 's/_DB_HOST=.*//' | sort -u | while read -r prefix; do
    [[ -z "$prefix" ]] && continue
    dbname=$(grep "^${prefix}_DB_NAME=" .env 2>/dev/null | cut -d= -f2- | tr -d "'\"" | head -1)
    host=$(grep "^${prefix}_DB_HOST=" .env 2>/dev/null | cut -d= -f2- | tr -d "'\"" | head -1)
    echo "  prefix=${prefix} · db=${dbname:-?} · host=${host:-?}" >&2
  done
  echo "" >&2
  echo "Aliases configured (use as --db <alias>):" >&2
  echo "  stage / crm_stage           → CRM_STAGE_DB" >&2
  echo "  stage-ca / crm_stage_ca     → CRM_STAGE_CA_DB" >&2
  echo "  release / crm_release       → CRM_RELEASE_DB" >&2
  echo "  release-ca / crm_release_ca → CRM_RELEASE_CA_DB" >&2
}

# ── parse args ────────────────────────────────────────────────
DB_NAME="stage"
JSON_OUT=0
QUERY=""
QUERY_FILE=""
PSQL_EXTRA=()

while [[ $# -gt 0 ]]; do
  case "$1" in
    --db) DB_NAME="$2"; shift 2 ;;
    --json) JSON_OUT=1; shift ;;
    -f|--file) QUERY_FILE="$2"; shift 2 ;;
    -h|--help) sed -n '2,30p' "$0"; exit 0 ;;
    --list|--list-dbs) list_available_dbs; exit 0 ;;
    --) shift; PSQL_EXTRA+=("$@"); break ;;
    *)
      if [[ -z "$QUERY" ]]; then QUERY="$1"; else PSQL_EXTRA+=("$1"); fi
      shift ;;
  esac
done

# ── resolve env vars for chosen DB ───────────────────────────
PREFIX=$(resolve_prefix "$DB_NAME")
host_var="${PREFIX}_HOST"
port_var="${PREFIX}_PORT"
name_var="${PREFIX}_NAME"
user_var="${PREFIX}_USER"
pass_var="${PREFIX}_PASSWORD"
ssl_var="${PREFIX}_SSLMODE"

# Indirect expansion ${!var} works in bash. Set -u + missing var would error;
# guard explicitly with a helpful message + list available DBs.
for v in "$host_var" "$port_var" "$name_var" "$user_var" "$pass_var"; do
  if [[ -z "${!v:-}" ]]; then
    echo "❌ Missing env var $v in .env (resolved from --db $DB_NAME → prefix $PREFIX)" >&2
    echo "   Required: $host_var, $port_var, $name_var, $user_var, $pass_var (optional: $ssl_var)" >&2
    echo "" >&2
    list_available_dbs
    exit 1
  fi
done

DB_HOST="${!host_var}"
DB_PORT="${!port_var}"
DB_DBNAME="${!name_var}"
DB_USER="${!user_var}"
DB_PASS="${!pass_var}"
DB_SSL="${!ssl_var:-require}"

# ── load query ────────────────────────────────────────────────
if [[ -n "$QUERY_FILE" ]]; then
  if [[ ! -f "$QUERY_FILE" ]]; then
    echo "❌ File not found: $QUERY_FILE" >&2; exit 1
  fi
  QUERY="$(cat "$QUERY_FILE")"
fi

if [[ -z "$QUERY" ]]; then
  echo "❌ No query provided. Usage: $0 [--db <name>] \"SELECT ...\"" >&2
  exit 1
fi

# ── client-side write guard ──────────────────────────────────
DENY_PATTERN='\b(insert|update|delete|truncate|drop|alter|create|grant|revoke|copy|vacuum|reindex|cluster|comment|lock|listen|notify|reset)\b'
if echo "$QUERY" | grep -iqE "$DENY_PATTERN"; then
  echo "❌ Query contains forbidden write keyword. This wrapper is read-only." >&2
  echo "   Pattern matched: $DENY_PATTERN" >&2
  exit 2
fi

# ── execute ──────────────────────────────────────────────────
PSQL_ARGS=(
  "host=$DB_HOST port=$DB_PORT dbname=$DB_DBNAME user=$DB_USER sslmode=$DB_SSL connect_timeout=15 application_name=qa-brain-db-query"
  -v ON_ERROR_STOP=1
  --set=AUTOCOMMIT=on
)

# Set default_transaction_read_only at connection startup so it doesn't
# pollute stdout in --json mode.
export PGOPTIONS="-c default_transaction_read_only=on -c statement_timeout=60000"

if [[ $JSON_OUT -eq 1 ]]; then
  WRAPPED="SELECT json_agg(row_to_json(_q)) FROM ( $QUERY ) _q;"
  PGPASSWORD="$DB_PASS" psql "${PSQL_ARGS[@]}" -At ${PSQL_EXTRA[@]+"${PSQL_EXTRA[@]}"} -c "$WRAPPED"
else
  PGPASSWORD="$DB_PASS" psql "${PSQL_ARGS[@]}" ${PSQL_EXTRA[@]+"${PSQL_EXTRA[@]}"} -c "$QUERY"
fi
