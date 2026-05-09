#!/usr/bin/env bash
set -euo pipefail

ROOT="${1:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
cd "$ROOT"

# Scan tracked source files for high-confidence secret values.
# Template placeholders in .env.example are allowed.
regex='(sk-[A-Za-z0-9_-]{12,}|BEGIN (RSA|OPENSSH|PRIVATE)|AIza[0-9A-Za-z_-]{20,}|xox[baprs]-|[A-Za-z0-9_]*(TOKEN|PASSWORD|SECRET|API_KEY)[A-Za-z0-9_]*=(?!your_|replace-me|123456:replace-me)[^[:space:]#]+)'

if git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  files=$(git ls-files .)
else
  files=$(find . -type f \
    -not -path './.venv/*' \
    -not -path './data/*' \
    -not -path './__pycache__/*' \
    -not -name '*.pyc' \
    -not -name '.env' \
    -not -name '.env.*')
fi

if [ -z "${files}" ]; then
  echo "No tracked files to scan."
  exit 0
fi

matches=$(printf '%s\n' "$files" | xargs -r grep -nPI "$regex" || true)
if [ -n "$matches" ]; then
  echo "Potential secrets found:" >&2
  echo "$matches" >&2
  exit 1
fi

echo "Secret scan passed."
