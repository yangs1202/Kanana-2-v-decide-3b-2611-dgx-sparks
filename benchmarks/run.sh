#!/usr/bin/env bash
set -Eeuo pipefail
source "$(dirname -- "$0")/../scripts/common.sh"
kind="${1:-}"
case "$kind" in
    memory|direct-memory) script=memory.py ;;
    load) script=load.py ;;
    *) echo 'Usage: ./benchmarks/run.sh memory|direct-memory|load' >&2; exit 1 ;;
esac
# Historical probes bind 18889, regardless of the installed API's configured port.
KANANA_PORT=18889 python3 "$RECIPE_ROOT/scripts/preflight.py"
run_root="$RECIPE_ROOT/results/$kind-$(date -u +%Y%m%dT%H%M%SZ)"
mkdir -p "$run_root"
count=1
[[ "$kind" != direct-memory ]] || count=3
for ((run=1; run<=count; run++)); do
    output="$run_root/run$run"
    mkdir -p "$output"
    name="kanana-bench-$(date +%s)-$run"
    loader=cpu-then-cuda
    [[ "$kind" != direct-memory ]] || loader=direct-cuda
    docker run -d --name "$name" --label "sh.yangs.kanana-recipe=$KANANA_LABEL" \
        --gpus all --network host --ipc host --restart no --env "KANANA_LOADER=$loader" \
        --mount "type=bind,src=$KANANA_MODEL_DIR,dst=/model,readonly" \
        --mount "type=bind,src=$output,dst=/results" \
        --mount "type=bind,src=$RECIPE_ROOT/benchmarks/scripts,dst=/benchmarks,readonly" \
        "$KANANA_IMAGE" python "/benchmarks/$script"
    KANANA_CONTAINER="$name" KANANA_HOME="$output" python3 -c \
        'import os; from pathlib import Path; (Path(os.environ["KANANA_HOME"])/"logs").mkdir()'
    KANANA_CONTAINER="$name" KANANA_HOME="$output" python3 "$RECIPE_ROOT/scripts/memory_guard.py" >"$output/guard.log" 2>&1 &
    guard_pid=$!
    code="$(docker wait "$name")"
    wait "$guard_pid"
    docker logs "$name" >"$output/probe.log" 2>&1
    [[ "$code" == 0 && ! -f "$output/logs/memory-abort.json" ]] || { echo "Benchmark failed: $output" >&2; exit 1; }
done
echo "Results: $run_root"
