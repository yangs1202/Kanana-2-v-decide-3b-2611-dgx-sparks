#!/usr/bin/env bash
# Shared paths for scripts; caller enables strict mode.
RECIPE_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
if [[ -f "$RECIPE_ROOT/.env" ]]; then
    set -a
    source "$RECIPE_ROOT/.env"
    set +a
fi
export KANANA_IMAGE="${KANANA_IMAGE:-kanana-dgx-sparks:2611}"
export KANANA_CONTAINER="${KANANA_CONTAINER:-kanana-dgx-sparks}"
export KANANA_PORT="${KANANA_PORT:-18889}"
export KANANA_HOME="${KANANA_HOME:-$HOME/.cache/kanana-dgx-sparks}"
export KANANA_MODEL_DIR="${KANANA_MODEL_DIR:-$KANANA_HOME/model}"
export KANANA_MIN_START_GIB="${KANANA_MIN_START_GIB:-25}"
export KANANA_MIN_FREE_GIB="${KANANA_MIN_FREE_GIB:-8}"
export KANANA_READY_TIMEOUT="${KANANA_READY_TIMEOUT:-300}"
export KANANA_REVISION=1489062def4145ae3a0a9261fbac4f4d88a8c6d1
export KANANA_LABEL=kanana-dgx-sparks
mkdir -p "$KANANA_HOME/logs"
