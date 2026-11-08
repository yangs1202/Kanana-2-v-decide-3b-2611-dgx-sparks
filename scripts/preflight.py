"""Check available unified memory and the loopback port before creating a server."""
import os
import socket
from pathlib import Path

available = next(int(line.split()[1]) for line in Path('/proc/meminfo').read_text().splitlines()
                 if line.startswith('MemAvailable:')) / 1024 ** 2
minimum = float(os.environ.get('KANANA_MIN_START_GIB', '25'))
floor = float(os.environ.get('KANANA_MIN_FREE_GIB', '8'))
assert minimum > 0 and 0 < floor < minimum, 'Require 0 < MIN_FREE_GIB < MIN_START_GIB'
if available < minimum:
    raise SystemExit(f'MemAvailable={available:.2f} GiB; need {minimum:g} GiB before startup. Other models are not stopped automatically.')
port = int(os.environ.get('KANANA_PORT', '18889'))
with socket.socket() as listener:
    listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    listener.bind(('127.0.0.1', port))
print(f'Preflight OK: {available:.2f} GiB available; loopback port {port} free')
