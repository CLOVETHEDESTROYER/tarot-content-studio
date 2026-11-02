#!/bin/bash
set -euo pipefail
cd -- "$(dirname -- "$0")"
if [[ ! -x .venv/bin/python ]]; then
  echo "Run Setup Content Studio.command first."
  read -r -p "Press Return to close... " || true
  exit 1
fi
if ! .venv/bin/python scripts/start.py; then
  echo "The studio could not start. See the error above and MAC-SETUP.md."
  read -r -p "Press Return to close... " || true
  exit 1
fi
