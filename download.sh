#!/usr/bin/env bash
set -Eeuo pipefail
source "$(dirname -- "$0")/scripts/common.sh"
mkdir -p "$KANANA_MODEL_DIR"
docker run --rm --user "$(id -u):$(id -g)" \
    --env HF_TOKEN --env KANANA_REVISION \
    --mount "type=bind,src=$KANANA_MODEL_DIR,dst=/model" \
    "$KANANA_IMAGE" python /recipe/scripts/download.py
