#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "==> Backend quality checks"
cd "${ROOT_DIR}/backend"
ruff check app ../tests
black --check app ../tests
pyright app
pytest ../tests -q

echo "==> Frontend typecheck"
cd "${ROOT_DIR}/frontend"
npm run typecheck

echo "==> All checks passed"
