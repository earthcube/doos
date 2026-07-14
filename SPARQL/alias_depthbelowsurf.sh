#!/usr/bin/env bash
# Apply alias_depthbelowsurf.ru against a SPARQL 1.1 Update endpoint.
#
# Usage (from repo root or anywhere):
#   ./SPARQL/alias_depthbelowsurf.sh
#   ./SPARQL/alias_depthbelowsurf.sh http://localhost:7878
#   ENDPOINT=http://localhost:7878 ./SPARQL/alias_depthbelowsurf.sh
#
# Expects Oxigraph (or compatible) with POST /update.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
UPDATE_FILE="${SCRIPT_DIR}/alias_depthbelowsurf.ru"
USER_AGENT="DOOS-OxigraphLoader/1.0"

# Endpoint base URL (no trailing path). Override via $1 or ENDPOINT.
ENDPOINT="${1:-${ENDPOINT:-http://localhost:7878}}"
ENDPOINT="${ENDPOINT%/}"
UPDATE_URL="${ENDPOINT}/update"

if [[ ! -f "${UPDATE_FILE}" ]]; then
  echo "Error: update file not found: ${UPDATE_FILE}" >&2
  exit 1
fi

echo "POST ${UPDATE_URL}"
echo "  file: ${UPDATE_FILE}"

RESP_FILE="$(mktemp)"
trap 'rm -f "${RESP_FILE}"' EXIT

HTTP_CODE="$(
  curl -sS -o "${RESP_FILE}" -w '%{http_code}' \
    -X POST "${UPDATE_URL}" \
    -H "Content-Type: application/sparql-update" \
    -H "User-Agent: ${USER_AGENT}" \
    --data-binary @"${UPDATE_FILE}"
)"

if [[ -s "${RESP_FILE}" ]]; then
  cat "${RESP_FILE}"
  echo
fi

if [[ "${HTTP_CODE}" -ge 200 && "${HTTP_CODE}" -lt 300 ]]; then
  echo "OK (HTTP ${HTTP_CODE})"
  exit 0
fi

echo "Error: HTTP ${HTTP_CODE} from ${UPDATE_URL}" >&2
exit 1
