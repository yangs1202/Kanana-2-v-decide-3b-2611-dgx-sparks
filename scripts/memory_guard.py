"""Sample host memory; stop only the labeled recipe container below the floor."""
import json
import os
import subprocess
import time
from pathlib import Path

container = os.environ['KANANA_CONTAINER']
floor = float(os.environ['KANANA_MIN_FREE_GIB']) * 1024 ** 3
root = Path(os.environ['KANANA_HOME']) / 'logs'
with (root / 'memory.jsonl').open('a', buffering=1) as output:
    while True:
        result = subprocess.run(['docker', 'inspect', '-f',
                                 '{{.State.Running}} {{index .Config.Labels "sh.yangs.kanana-recipe"}}',
                                 container], capture_output=True, text=True)
        if result.returncode or result.stdout.strip() != 'true kanana-dgx-sparks':
            break
        available = next(int(line.split()[1]) * 1024 for line in Path('/proc/meminfo').read_text().splitlines()
                         if line.startswith('MemAvailable:'))
        row = dict(time=time.time(), mem_available_bytes=available)
        output.write(json.dumps(row) + '\n')
        if available < floor:
            (root / 'memory-abort.json').write_text(json.dumps(row) + '\n')
            print('Memory floor crossed: stopping recipe container only.', flush=True)
            subprocess.run(['docker', 'stop', '-t', '2', container], check=True)
            break
        time.sleep(.2)
