#!/bin/bash
set -euo pipefail
cd -- "$(dirname -- "$0")"
if ! bash scripts/setup-mac.sh; then
  echo "Setup did not finish. Read the error above, then see MAC-SETUP.md."
  read -r -p "Press Return to close... " || true
  exit 1
fi
echo "Setup complete. Open Start Content Studio.command."
read -r -p "Press Return to close... " || true
