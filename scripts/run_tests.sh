#!/usr/bin/env bash
# Lance la suite de tests MBM, y compris les tests d'interface en mode hors écran.
set -eu
cd "$(dirname "$0")/.."
export QT_QPA_PLATFORM="${QT_QPA_PLATFORM:-offscreen}"
python3 -m pytest "$@"
