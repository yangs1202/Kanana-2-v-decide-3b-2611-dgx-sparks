#!/usr/bin/env bash
set -Eeuo pipefail
source "$(dirname -- "$0")/scripts/common.sh"
exec python3 "$RECIPE_ROOT/scripts/smoke.py" "$@"
