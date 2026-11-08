#!/usr/bin/env bash
set -Eeuo pipefail
source "$(dirname -- "$0")/scripts/common.sh"
if docker container inspect "$KANANA_CONTAINER" >/dev/null 2>&1; then
    owner="$(docker inspect -f '{{index .Config.Labels "sh.yangs.kanana-recipe"}}' "$KANANA_CONTAINER")"
    [[ "$owner" == "$KANANA_LABEL" ]] || { echo 'Container name belongs to another deployment; choose KANANA_CONTAINER.' >&2; exit 1; }
    if [[ "$(docker inspect -f '{{.State.Running}}' "$KANANA_CONTAINER")" == true ]]; then
        echo "$KANANA_CONTAINER already running; checking health without restarting."
        exec "$RECIPE_ROOT/smoke.sh"
    fi
    docker rm "$KANANA_CONTAINER" >/dev/null
fi
python3 "$RECIPE_ROOT/scripts/preflight.py"
[[ -f "$KANANA_MODEL_DIR/recipe-revision.json" ]] || { echo 'Run ./download.sh first.' >&2; exit 1; }
docker run --rm --user "$(id -u):$(id -g)" --env KANANA_REVISION \
    --mount "type=bind,src=$KANANA_MODEL_DIR,dst=/model,readonly" \
    "$KANANA_IMAGE" python /recipe/scripts/download.py --verify-only
docker run -d --name "$KANANA_CONTAINER" \
    --label "sh.yangs.kanana-recipe=$KANANA_LABEL" \
    --gpus all --network host --ipc host --restart no \
    --env KANANA_PORT --env DECISION_API_KEY \
    --mount "type=bind,src=$KANANA_MODEL_DIR,dst=/model,readonly" \
    "$KANANA_IMAGE"
nohup python3 "$RECIPE_ROOT/scripts/memory_guard.py" \
    >"$KANANA_HOME/logs/guard.log" 2>&1 </dev/null &
echo "$!" >"$KANANA_HOME/logs/guard.pid"
deadline=$((SECONDS + KANANA_READY_TIMEOUT))
while (( SECONDS < deadline )); do
    if [[ "$(docker inspect -f '{{.State.Running}}' "$KANANA_CONTAINER")" != true ]]; then
        docker logs --tail 50 "$KANANA_CONTAINER" >&2
        echo 'Server stopped before readiness; inspect guard.log and container logs.' >&2
        exit 1
    fi
    if python3 "$RECIPE_ROOT/scripts/smoke.py" --health-only >/dev/null 2>&1; then
        echo "Ready: http://127.0.0.1:$KANANA_PORT/v1/systemone"
        exit 0
    fi
    sleep 2
done
echo "Readiness timed out. Inspect: docker logs $KANANA_CONTAINER" >&2
exit 1
