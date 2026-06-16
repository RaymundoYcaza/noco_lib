#!/usr/bin/env bash
# Pre-commit hook: incrementa el build number en tardis/VERSION
#
# Se ejecuta automaticamente antes de cada commit local.
# Instalacion: python tardis/scripts/install_hooks.py
#
# El hook:
#   1. Corre bump_version.py que incrementa el build en VERSION
#   2. Staged el archivo VERSION modificado para que quede incluido en el commit

set -e

REPO_ROOT=$(git rev-parse --show-toplevel)
cd "$REPO_ROOT"

# Incrementar el build number
python tardis/scripts/bump_version.py

# Stagerar el VERSION actualizado para que forme parte del commit
git add tardis/VERSION
