#!/usr/bin/env bash
set -Eeuo pipefail
RECIPE_ROOT="$(cd -- "$(dirname -- "$0")" && pwd)"
for command in docker python3 nvidia-smi; do
    command -v "$command" >/dev/null || { echo "Missing prerequisite: $command" >&2; exit 1; }
done
nvidia-smi -L
"$RECIPE_ROOT/build.sh"
"$RECIPE_ROOT/download.sh"
"$RECIPE_ROOT/start.sh"
"$RECIPE_ROOT/smoke.sh"
