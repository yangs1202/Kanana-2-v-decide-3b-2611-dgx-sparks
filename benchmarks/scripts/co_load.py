"""HTTP coexistence stress: existing Kanana on dgx2 and GLM TP2 on both nodes."""
import base64
import concurrent.futures
import io
import json
import math
import os
import random
import statistics
import subprocess
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(os.environ.get('RESULTS_DIR', './results/co-load'))
KANANA = os.environ.get('KANANA_ENDPOINT', 'http://127.0.0.1:18889')
GLM = os.environ['GLM_ENDPOINT']
GIB = 1024 ** 3
ROOT.mkdir(parents=True, exist_ok=True)
stop = threading.Event()
monitor_done = threading.Event()
lock = threading.Lock()
samples, glm_rows, kanana_rows, phases = [], [], [], []
server_pid = subprocess.check_output(['docker', 'inspect', '-f', '{{.State.Pid}}',
                                      os.environ.get('KANANA_CONTAINER', 'kanana-dgx-sparks')], text=True).strip()


def memory():
    values = {k: int(v.split()[0]) * 1024
              for k, v in (line.split(':', 1) for line in Path('/proc/meminfo').read_text().splitlines())
              if k in ('MemAvailable', 'SwapFree')}
    status = Path('/proc') / server_pid / 'status'
    if status.exists():
        values.update({k: int(v.split()[0]) * 1024
                       for k, v in (line.split(':', 1) for line in status.read_text().splitlines() if ':' in line)
                       if k in ('VmRSS', 'VmHWM')})
    return dict(time=time.time(), **values)


baseline = memory()


def monitor():
    with (ROOT / 'memory.jsonl').open('w', buffering=1) as output:
        while not monitor_done.wait(0.2):
            row = memory()
            samples.append(row)
            output.write(json.dumps(row) + '\n')
            if row['MemAvailable'] < 4 * GIB or 'VmRSS' not in row:
                stop.set()


def request(endpoint, body, service):
    started = time.time()
    try:
        req = urllib.request.Request(endpoint, data=body, headers={'Content-Type': 'application/json'})
        with urllib.request.urlopen(req, timeout=300) as response:
            result = json.load(response)
            assert response.status == 200
        if service == 'kanana':
            for answer in result['answers'].values():
                values = answer['probabilities'].values()
                assert all(math.isfinite(v) for v in values) and abs(sum(values) - 1) < 1e-5
        else:
            assert result['choices'][0]['message']['content']
        row = dict(ok=True, response=result)
    except Exception as error:
        row = dict(ok=False, error=f'{type(error).__name__}: {error}')
        stop.set()
    row.update(start=started, end=time.time(), seconds=time.time() - started, service=service)
    with lock:
        with (ROOT / 'requests.jsonl').open('a') as output:
            output.write(json.dumps(row, ensure_ascii=False) + '\n')
        (kanana_rows if service == 'kanana' else glm_rows).append(row)
    return row


def payload(value):
    return json.dumps(value, ensure_ascii=False).encode()


threading.Thread(target=monitor, daemon=True).start()
for service, url in (('kanana', KANANA), ('glm', GLM)):
    for route in ('health', 'v1/models'):
        with urllib.request.urlopen(url + '/' + route, timeout=10) as response:
            (ROOT / (service + '-' + route.replace('/', '-') + '.json')).write_bytes(response.read())

question = {'category': dict(type='choice', instructions='고객 문의를 분류하세요.',
                           criteria={'exchange': '상품 교환 요청', 'delivery': '배송 문의', 'payment': '결제 문의'})}
unit = '주문한 상품이 깨져서 도착했습니다. 교환을 요청합니다. '
short = payload(dict(state=unit, questions=question))
warm = request(KANANA + '/v1/systemone', short, 'kanana')
assert warm['ok'] and warm['response']['answers']['category']['choice'] == 'exchange'
glm_smoke = payload(dict(model='GLM-5.3-Flash', messages=[dict(role='user', content='2+3의 답을 숫자만 출력하세요.')],
                         max_tokens=16, temperature=0, chat_template_kwargs={'enable_thinking': False}))
warm_glm = request(GLM + '/v1/chat/completions', glm_smoke, 'glm')
assert warm_glm['ok'] and warm_glm['response']['choices'][0]['message']['content'].strip() == '5'
warmup_end = time.time()

from PIL import Image

rng = random.Random(2611)
images = []
for i in range(10):
    image = Image.frombytes('RGB', (1280, 1280), rng.randbytes(1280 * 1280 * 3))
    buffer = io.BytesIO()
    image.save(buffer, format='JPEG', quality=90)
    images.append('data:image/jpeg;base64,' + base64.b64encode(buffer.getvalue()).decode())
bodies = dict(short=short, long=payload(dict(state=unit * 1800, questions=question)),
              images10=payload(dict(state=unit, images=images, questions=question)),
              mixed=payload(dict(state=unit * 1800, images=images, questions=question)))
glm_body = payload(dict(model='GLM-5.3-Flash',
    messages=[dict(role='user', content='다음 자료를 바탕으로 개선안을 1번부터 100번까지 자세히 작성하세요. 생략하지 마세요.\n' +
                   '고객 문의의 배송, 결제, 교환을 분석하고 문제 원인과 해결 절차를 정리한다. ' * 250)],
    max_tokens=128, temperature=0, chat_template_kwargs={'enable_thinking': False}))
(ROOT / 'conditions.json').write_text(json.dumps(dict(image_seed=2611, generator='Python random.Random.randbytes',
    images=10, image_size=[1280, 1280], jpeg_quality=90, glm_concurrency=2, glm_max_tokens=128,
    glm_payload_bytes=len(glm_body), payload_bytes={k: len(v) for k, v in bodies.items()}), indent=2))


def glm_pressure():
    while not stop.is_set():
        request(GLM + '/v1/chat/completions', glm_body, 'glm')


def wave(name, data, concurrency):
    if stop.is_set():
        return False
    print('START ' + name, flush=True)
    index = len(samples)
    started = time.time()
    with concurrent.futures.ThreadPoolExecutor(max_workers=concurrency) as pool:
        rows = list(pool.map(lambda _: request(KANANA + '/v1/systemone', data, 'kanana'), range(concurrency)))
    observed = samples[index:] + [memory()]
    row = dict(phase=name, start=started, end=time.time(), seconds=time.time() - started,
               concurrency=concurrency, requests=rows, min_available=min(s['MemAvailable'] for s in observed),
               after=observed[-1])
    phases.append(row)
    (ROOT / (name + '.json')).write_text(json.dumps(row, ensure_ascii=False, indent=2))
    print(json.dumps({k: v for k, v in row.items() if k != 'requests'}), flush=True)
    return all(r['ok'] for r in rows) and not stop.is_set()


workers = [threading.Thread(target=glm_pressure) for _ in range(2)]
for worker in workers:
    worker.start()
try:
    for case, concurrency in (('short', 1), ('long', 1), ('images10', 1), ('mixed', 6)):
        for run in range(1, 4):
            if not wave(f'{case}-c{concurrency}-run{run}', bodies[case], concurrency):
                break
        if stop.is_set():
            break
    if not stop.is_set():
        deadline = time.monotonic() + 60
        run = 0
        while time.monotonic() < deadline and not stop.is_set():
            run += 1
            wave(f'sustained-c1-run{run}', bodies['mixed' if run % 2 else 'short'], 1)
finally:
    failed = stop.is_set()
    stop.set()
    for worker in workers:
        worker.join()

print('IDLE 30s', flush=True)
time.sleep(30)
monitor_done.set()
glm_load = [r for r in glm_rows if r['start'] > warmup_end]
kanana_load = [r for r in kanana_rows if r['start'] > warmup_end]
overlap = sum(any(g['start'] < k['end'] and g['end'] > k['start'] for g in glm_load) for k in kanana_load)
summary = dict(baseline=baseline, failed=failed, kanana_requests=len(kanana_load), glm_requests=len(glm_load),
    kanana_errors=sum(not r['ok'] for r in kanana_load), glm_errors=sum(not r['ok'] for r in glm_load),
    kanana_overlapping_glm=overlap, min_available=min(s['MemAvailable'] for s in samples), final=memory(),
    glm_usage=[r['response']['usage'] for r in glm_load if r['ok']],
    glm_request_mean_seconds=statistics.mean(r['seconds'] for r in glm_load) if glm_load else None,
    kanana_usage=sorted({r['response']['usage']['input_tokens'] for r in kanana_load if r['ok']}),
    model_commit='1489062def4145ae3a0a9261fbac4f4d88a8c6d1', glm_context=524288,
    kanana_server_serialized=True, allocator_cache_cleared=False)
(ROOT / 'summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2))
(ROOT / 'complete').write_text('failed\n' if failed else 'pass\n')
print('COMPLETE ' + json.dumps({k: v for k, v in summary.items() if k != 'glm_usage'}), flush=True)
