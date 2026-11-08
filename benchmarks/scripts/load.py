"""Standalone Kanana HTTP load/memory probe using the official serialized server."""
import base64
import concurrent.futures
import io
import json
import math
import statistics
import sys
import threading
import time
import urllib.request
from pathlib import Path

OUT = Path('/results')
GIB = 1024 ** 3


def memory():
    values = {k: int(v.split()[0]) * 1024
              for k, v in (line.split(':', 1) for line in Path('/proc/meminfo').read_text().splitlines())
              if k in ('MemAvailable', 'SwapFree')}
    for line in Path('/proc/self/status').read_text().splitlines():
        if line.startswith(('VmRSS:', 'VmHWM:')):
            values[line.split(':')[0]] = int(line.split()[1]) * 1024
    return dict(time=time.time(), **values)


baseline = memory()
samples = [baseline]
done = threading.Event()


def monitor():
    with (OUT / 'memory.jsonl').open('w', buffering=1) as output:
        while not done.wait(0.1):
            row = memory()
            samples.append(row)
            output.write(json.dumps(row) + '\n')


threading.Thread(target=monitor, daemon=True).start()
print('IMPORT', flush=True)
import numpy as np
import torch
from PIL import Image
from transformers import AutoModel

torch.set_num_threads(8)
model = None
forward_shapes = []
phase_rows = []


def phase(name, fn):
    torch.cuda.synchronize()
    torch.cuda.reset_peak_memory_stats()
    start_index, forward_index = len(samples), len(forward_shapes)
    samples.append(memory())
    started = time.monotonic()
    print('START ' + name, flush=True)
    result = fn()
    torch.cuda.synchronize()
    elapsed = time.monotonic() - started
    samples.append(memory())
    observed = samples[start_index:]
    row = dict(phase=name, seconds=elapsed, result=result,
               min_available=min(s['MemAvailable'] for s in observed),
               system_delta_gib=(baseline['MemAvailable'] - min(s['MemAvailable'] for s in observed)) / GIB,
               after=observed[-1], rss_peak=max(s['VmRSS'] for s in observed),
               cuda_allocated=torch.cuda.memory_allocated(), cuda_reserved=torch.cuda.memory_reserved(),
               cuda_peak_allocated=torch.cuda.max_memory_allocated(),
               cuda_peak_reserved=torch.cuda.max_memory_reserved(),
               forwards=forward_shapes[forward_index:])
    phase_rows.append(row)
    (OUT / (name + '.json')).write_text(json.dumps(row, ensure_ascii=False, indent=2))
    print(json.dumps({k: v for k, v in row.items() if k not in ('result', 'forwards')}, ensure_ascii=False), flush=True)
    return result


def load():
    global model
    model = AutoModel.from_pretrained('/model', trust_remote_code=True, dtype=torch.bfloat16,
                                     attn_implementation='sdpa', device_map='cuda').eval()
    assert all(p.device.type == 'cuda' for p in model.parameters())
    return dict(parameter_bytes=sum(p.numel() * p.element_size() for p in model.parameters()))


phase('load', load)
model.config.truncate_inputs = True
model.config.truncate_question_candidates = True


def input_shape(module, args, kwargs):
    ids = kwargs['input_ids']
    pixels = kwargs.get('pixel_values')
    forward_shapes.append(dict(tokens=ids.shape[1], pixels=list(pixels.shape) if pixels is not None else None))


model.register_forward_pre_hook(input_shape, with_kwargs=True)
sys.path.insert(0, '/model')
from server_kanana_v_decide import Decider, SystemOneServer

server = SystemOneServer(('127.0.0.1', 18889), Decider(model, 'kanana-2-v-decide-3b-2611'))
threading.Thread(target=server.serve_forever, daemon=True).start()
for route in ('health', 'v1/models'):
    with urllib.request.urlopen('http://127.0.0.1:18889/' + route) as response:
        (OUT / (route.replace('/', '-') + '.json')).write_bytes(response.read())
question = {'category': dict(type='choice', instructions='고객 문의를 분류하세요.',
                           criteria={'exchange': '상품 교환 요청', 'delivery': '배송 문의', 'payment': '결제 문의'})}
short = dict(state='주문한 상품이 깨져서 도착했습니다. 교환해주세요.', questions=question)


def payload(body):
    return json.dumps(body, ensure_ascii=False).encode()


def request(data):
    started = time.monotonic()
    req = urllib.request.Request('http://127.0.0.1:18889/v1/systemone', data=data,
                                 headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=600) as response:
        assert response.status == 200
        answer = json.load(response)
    for value in answer['answers'].values():
        probabilities = value['probabilities']
        assert all(math.isfinite(v) for v in probabilities.values())
        assert abs(sum(probabilities.values()) - 1) < 1e-5
    return dict(seconds=time.monotonic() - started, response=answer)


warm = phase('warmup', lambda: request(payload(short)))
assert warm['response']['answers']['category']['choice'] == 'exchange'
assert len(model._candidate_cache) > 0


bodies = {}


def fixtures():
    rng = np.random.default_rng(2611)
    image_urls = []
    for i in range(10):
        image = Image.fromarray(rng.integers(0, 256, (1280, 1280, 3), dtype=np.uint8))
        buffer = io.BytesIO()
        image.save(buffer, format='JPEG', quality=90)
        image_urls.append('data:image/jpeg;base64,' + base64.b64encode(buffer.getvalue()).decode())
    unit = '주문한 상품이 깨져서 도착했습니다. 교환을 요청합니다. '
    bodies.update(dict(short=payload(short),
                  long=payload(dict(state=unit * 1800, questions=question)),
                  images10=payload(dict(state=short['state'], images=image_urls, questions=question)),
                  mixed=payload(dict(state=unit * 1800, images=image_urls, questions=question))))
    (OUT / 'fixtures.json').write_text(json.dumps(dict(seed=2611, image_count=10, image_size=[1280, 1280],
        jpeg_quality=90, payload_bytes={k: len(v) for k, v in bodies.items()}), indent=2))
    return dict(payload_bytes={k: len(v) for k, v in bodies.items()})


phase('fixtures', fixtures)


def waves(data, concurrency):
    with concurrent.futures.ThreadPoolExecutor(max_workers=concurrency) as pool:
        return list(pool.map(request, [data] * concurrency))


for case in ('short', 'long', 'images10', 'mixed'):
    for run in range(1, 4):
        phase(f'{case}-c1-run{run}', lambda: waves(bodies[case], 1))
for concurrency in (2, 4, 6):
    for run in range(1, 4):
        phase(f'mixed-c{concurrency}-run{run}', lambda: waves(bodies['mixed'], concurrency))


def sustained():
    end = time.monotonic() + 60
    results = []
    while time.monotonic() < end:
        data = bodies['mixed'] if len(results) % 2 == 0 else bodies['short']
        results.append(request(data))
    return results


phase('sustained-60s', sustained)
phase('idle-30s', lambda: time.sleep(30))
all_requests = [r for p in phase_rows if p['phase'] != 'warmup'
                for r in (p['result'] if isinstance(p['result'], list) else [])]
summary = dict(baseline=baseline, requests=len(all_requests),
               peak_system_delta_gib=(baseline['MemAvailable'] - min(s['MemAvailable'] for s in samples)) / GIB,
               final=memory(), max_query_tokens=max(s['tokens'] for s in forward_shapes),
               candidate_cache_entries=len(model._candidate_cache),
               request_median_seconds=statistics.median(r['seconds'] for r in all_requests),
               torch=torch.__version__, transformers=__import__('transformers').__version__,
               model_commit='1489062def4145ae3a0a9261fbac4f4d88a8c6d1',
               server_serialized=True, allocator_cache_cleared_between_phases=False)
assert summary['max_query_tokens'] == 20480, summary
(OUT / 'summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2))
(OUT / 'complete').write_text('pass\n')
print('COMPLETE ' + json.dumps(summary, ensure_ascii=False), flush=True)
server.shutdown()
done.set()
