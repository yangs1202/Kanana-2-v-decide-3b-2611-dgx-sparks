"""Download an immutable upstream revision and verify the measured weight file."""
import argparse
import hashlib
import json
import os
from pathlib import Path

REVISION = '1489062def4145ae3a0a9261fbac4f4d88a8c6d1'
WEIGHT_SHA256 = '528930fa261b31ed1f47eecbe7d08efd2e226207508124ae186e1a65dbbbda3b'
MODEL = 'kakaocorp/kanana-2-v-decide-3b-2611'
parser = argparse.ArgumentParser()
parser.add_argument('--verify-only', action='store_true')
args = parser.parse_args()
assert os.environ.get('KANANA_REVISION', REVISION) == REVISION
root = Path('/model')
marker = root / 'recipe-revision.json'
if args.verify_only:
    assert json.loads(marker.read_text())['revision'] == REVISION
else:
    from huggingface_hub import snapshot_download
    snapshot_download(MODEL, revision=REVISION, local_dir=str(root), max_workers=2)
with (root / 'model.safetensors').open('rb') as source:
    digest = hashlib.file_digest(source, 'sha256').hexdigest()
assert digest == WEIGHT_SHA256, 'Unexpected model weights'
for name in ('config.json', 'server_kanana_v_decide.py', 'tokenizer.json', 'LICENSE'):
    assert (root / name).is_file(), name
if not args.verify_only:
    marker.write_text(json.dumps(dict(model=MODEL, revision=REVISION, weight_sha256=digest), indent=2) + '\n')
print(f'Verified {MODEL}@{REVISION} (weights SHA256 {digest})', flush=True)
