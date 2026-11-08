"""Single-request BF16/SDPA memory probe; run inside the isolated DGX container."""
import gc
import json
import os
import sys
import threading
import time
import urllib.request
from pathlib import Path

import torch
from PIL import Image, ImageDraw
from transformers import AutoModel

OUT = Path('/results')
GIB = 1024 ** 3


def host_memory():
    values = {}
    for line in Path('/proc/meminfo').read_text().splitlines():
        key, value = line.split(':', 1)
        if key in ('MemTotal', 'MemAvailable', 'SwapFree'):
            values[key] = int(value.split()[0]) * 1024
    for line in Path('/proc/self/status').read_text().splitlines():
        if line.startswith('VmRSS:'):
            values['rss'] = int(line.split()[1]) * 1024
    return values


def measure(name, run, fn):
    gc.collect()
    torch.cuda.empty_cache()
    torch.cuda.synchronize()
    torch.cuda.reset_peak_memory_stats()
    before = host_memory()
    samples = [before]
    done = threading.Event()

    def monitor():
        while not done.wait(0.02):
            samples.append(host_memory())

    watcher = threading.Thread(target=monitor)
    watcher.start()
    started = time.monotonic()
    try:
        result = fn()
        torch.cuda.synchronize()
        elapsed = time.monotonic() - started
    finally:
        done.set()
        watcher.join()
    samples.append(host_memory())
    row = dict(case=name, run=run, seconds=elapsed, before=before,
               after=samples[-1], min_available=min(s['MemAvailable'] for s in samples),
               peak_rss=max(s['rss'] for s in samples),
               cuda_allocated=torch.cuda.memory_allocated(),
               cuda_reserved=torch.cuda.memory_reserved(),
               cuda_peak_allocated=torch.cuda.max_memory_allocated(),
               cuda_peak_reserved=torch.cuda.max_memory_reserved(), result=result)
    (OUT / f'kanana-memory-20261108-1489062-{name}-run{run}.json').write_text(
        json.dumps(row, ensure_ascii=False, indent=2))
    print(json.dumps(row, ensure_ascii=False), flush=True)
    return row


torch.set_num_threads(8)
metadata = dict(torch=torch.__version__, device=torch.cuda.get_device_name(),
                loader=os.environ.get('KANANA_LOADER', 'cpu-then-cuda'),
                dtype='bfloat16', attention='sdpa', concurrency=1,
                model_commit='1489062def4145ae3a0a9261fbac4f4d88a8c6d1',
                baseline=host_memory())
(OUT / 'metadata.json').write_text(json.dumps(metadata, indent=2))
model = None


def load():
    global model
    direct = metadata['loader'] == 'direct-cuda'
    options = {'device_map': 'cuda'} if direct else {}
    model = AutoModel.from_pretrained('/model', trust_remote_code=True,
                                     dtype=torch.bfloat16, attn_implementation='sdpa',
                                     **options).eval()
    if not direct:
        model = model.to('cuda')
    assert all(p.device.type == 'cuda' for p in model.parameters())
    assert all(b.device.type == 'cuda' for b in model.buffers())
    return dict(parameter_bytes=sum(p.numel() * p.element_size() for p in model.parameters()),
                parameter_devices=sorted({str(p.device) for p in model.parameters()}))


measure('load', 0, load)
model.config.truncate_inputs = False
model.config.truncate_question_candidates = False
sys.path.insert(0, '/model')
from server_kanana_v_decide import Decider, SystemOneServer

server = SystemOneServer(('127.0.0.1', 18889), Decider(model, 'kanana-2-v-decide-3b-2611'))
threading.Thread(target=server.serve_forever, daemon=True).start()
for route in ('health', 'v1/models'):
    with urllib.request.urlopen(f'http://127.0.0.1:18889/{route}') as response:
        (OUT / (route.replace('/', '-') + '.json')).write_bytes(response.read())
questions = {
    'category': dict(type='choice', instructions='고객 문의를 분류하세요.',
                     criteria={'exchange': '상품 교환 요청', 'delivery': '배송 문의', 'payment': '결제 문의'}),
    'damaged': dict(type='noul', instructions='상품이 파손되었습니까?'),
    'sentiment': dict(type='score', instructions='고객 감정이 얼마나 긍정적입니까?',
                      criteria=['부정적', '중립적', '긍정적']),
}
warm = measure('warmup', 0, lambda: model.system_one(
    state='주문한 상품이 깨져서 도착했습니다. 교환해주세요.', questions=questions))
assert warm['result']['answers']['category']['choice'] == 'exchange', warm
assert warm['result']['answers']['damaged']['noul'] > 0.5, warm
assert len(model._candidate_cache) > 0
request = urllib.request.Request('http://127.0.0.1:18889/v1/systemone',
    data=json.dumps(dict(state='주문한 상품이 깨졌습니다. 교환해주세요.', questions=questions)).encode(),
    headers={'Content-Type': 'application/json'})
with urllib.request.urlopen(request, timeout=120) as response:
    (OUT / 'http-smoke.json').write_bytes(response.read())
single = {'category': questions['category']}
tokenizer = model.processor.tokenizer
unit = '주문한 상품이 깨져서 도착했습니다. 교환을 요청합니다. '
unit_ids = tokenizer.encode(unit, add_special_tokens=False)
cases = []
for target in (256, 2048, 8192, 20000):
    state = tokenizer.decode((unit_ids * (target // len(unit_ids) + 1))[:target])
    cases.append((f'text-{target}', state, None))
for size, count in ((512, 1), (1280, 1), (512, 10)):
    image = Image.new('RGB', (size, size), 'white')
    ImageDraw.Draw(image).rectangle((size // 4, size // 4, size * 3 // 4, size * 3 // 4), fill='red')
    image.save(OUT / f'fixture-{size}.png')
    cases.append((f'image-{size}x{size}-n{count}',
                  '고객이 상품 사진을 보냈고 교환을 요청합니다.', [image.copy() for _ in range(count)]))
for name, state, images in cases:
    for run in range(1, 4):
        model._candidate_cache.clear()
        measure(name, run, lambda: model.system_one(state=state, images=images, questions=single))
model._candidate_cache.clear()
model.system_one(state=unit, questions=single)
for run in range(1, 4):
    measure('text-short-cached', run, lambda: model.system_one(state=unit, questions=single))
(OUT / 'complete').write_text('pass\n')
server.shutdown()
