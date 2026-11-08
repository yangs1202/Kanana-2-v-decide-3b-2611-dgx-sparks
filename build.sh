#!/usr/bin/env bash
set -Eeuo pipefail
source "$(dirname -- "$0")/scripts/common.sh"
[[ "$(uname -m)" == aarch64 ]] || { echo 'This recipe targets Linux aarch64 DGX Spark.' >&2; exit 1; }
docker info >/dev/null
docker build --platform linux/arm64 -t "$KANANA_IMAGE" "$RECIPE_ROOT"
docker image inspect "$KANANA_IMAGE" --format '{{.Id}}' | tee "$KANANA_HOME/logs/runtime-image.txt"
