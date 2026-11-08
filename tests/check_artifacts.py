"""Verify published hashes and independently reproduce the archived CSAT scores."""
import hashlib
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

root = Path(__file__).resolve().parents[1]
manifest = json.loads((root / 'benchmarks/publication-manifest.json').read_text())
for row in manifest['files']:
    path = root / 'benchmarks/raw' / row['path']
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    assert digest == row['published_sha256'], path

raw = root / 'benchmarks/raw/kanana-csat-20261108-1489062'
with tempfile.TemporaryDirectory() as directory:
    target = Path(directory)
    for name in ('cases.json', 'answer-key.json', 'results.jsonl'):
        shutil.copyfile(raw / name, target / name)
    subprocess.run([sys.executable, str(root / 'benchmarks/scripts/csat.py'), 'grade', '--root', directory],
                   check=True, stdout=subprocess.PIPE)
    actual = json.loads((target / 'summary.json').read_text())
    expected = json.loads((raw / 'summary.json').read_text())
    assert actual == expected, 'CSAT aggregation changed'
    assert actual['requests'] == 336 and actual['stable_cases'] == 112
    assert actual['forms']['odd']['exams']['speech']['score'] == 54
    assert actual['forms']['odd']['exams']['language']['score'] == 43

secret = re.compile(rb'gh[opusr]_[A-Za-z0-9]{20,}|hf_[A-Za-z0-9]{20,}|-----BEGIN (?:RSA |OPENSSH )?PRIVATE KEY')
private = re.compile(rb'(?:[a-zA-Z0-9-]+\.)+yangs\.sh|/home/[y]angs/|192\.168\.\d+\.\d+')
for path in root.rglob('*'):
    if not path.is_file() or any(part in ('.git', '__pycache__', '.venv', 'results') for part in path.parts):
        continue
    data = path.read_bytes()
    assert not secret.search(data), f'Credential pattern: {path}'
    assert not private.search(data), f'Internal address/path: {path}'
print(f'PASS: {len(manifest["files"])} artifact hashes, 336-response grading, public-file scan')
