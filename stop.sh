#!/usr/bin/env bash
set -Eeuo pipefail
source "$(dirname -- "$0")/scripts/common.sh"
docker container inspect "$KANANA_CONTAINER" >/dev/null 2>&1 || exit 0
owner="$(docker inspect -f '{{index .Config.Labels "sh.yangs.kanana-recipe"}}' "$KANANA_CONTAINER")"
[[ "$owner" == "$KANANA_LABEL" ]] || { echo 'Refusing to stop a container owned by another deployment.' >&2; exit 1; }
docker stop -t 10 "$KANANA_CONTAINER"
