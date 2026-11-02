#!/bin/bash
set -euo pipefail
cd -- "$(dirname -- "$0")/.."
if [[ "$(uname -s)" != Darwin ]]; then
  echo "Use Setup Content Studio.cmd on Windows. This installer is for macOS."
  exit 1
fi
studio_python=""
for candidate in "${STUDIO_PYTHON:-}" python3.13 python3.12 python3.11 python3; do
  if [[ -n "$candidate" ]] && command -v "$candidate" >/dev/null 2>&1 && "$candidate" -c 'import sys; assert (3,11) <= sys.version_info[:2] < (3,14)' >/dev/null 2>&1; then
    studio_python="$candidate"
    break
  fi
done
if [[ -z "$studio_python" ]]; then
  echo "Install Python 3.12 (macOS universal2 installer), then run setup again. See MAC-SETUP.md."
  exit 1
fi
if ! command -v node >/dev/null 2>&1 || ! command -v npm >/dev/null 2>&1; then
  echo "Install Node.js 22 LTS for macOS x64 (Intel), then run setup again. See MAC-SETUP.md."
  exit 1
fi
if ! node -e 'const [m,n]=process.versions.node.split(".").map(Number); process.exit(((m===20&&n>=19)||(m===22&&n>=12)||m>=24)?0:1)'; then
  echo "Node.js 20.19+, 22.12+, or 24+ is required. Node 22 x64 is recommended for Intel Macs."
  exit 1
fi
if [[ -d .venv && ! -x .venv/bin/python ]]; then
  echo "This .venv belongs to another operating system. Rename it to .venv-windows, then run setup again."
  echo "A fresh Git clone does not include .venv."
  exit 1
fi
if [[ ! -x .venv/bin/python ]]; then "$studio_python" -m venv .venv; fi
.venv/bin/python -c 'import sys; assert (3,11) <= sys.version_info[:2] < (3,14), "Use a Python 3.11-3.13 environment."'
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -r requirements-lock.txt
pushd frontend >/dev/null
npm ci --no-audit --no-fund
npm run build
popd >/dev/null
.venv/bin/python scripts/doctor.py
