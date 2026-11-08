#!/usr/bin/env bash
set -Eeuo pipefail
target="${KANANA_INSTALL_DIR:-$HOME/Kanana-2-v-decide-3b-2611-dgx-sparks}"
command -v git >/dev/null || { echo 'Install git first.' >&2; exit 1; }
if [[ -e "$target" ]]; then
    echo "Installation directory already exists: $target. Run its ./setup.sh or choose KANANA_INSTALL_DIR." >&2
    exit 1
fi
git clone --depth 1 https://github.com/yangs1202/Kanana-2-v-decide-3b-2611-dgx-sparks.git "$target"
exec "$target/setup.sh"
