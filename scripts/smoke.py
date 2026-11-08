"""Verify health/models and all three decision types; no third-party client deps."""
import argparse
import json
import math
import os
import time
import urllib.request

parser = argparse.ArgumentParser()
parser.add_argument('--endpoint', default='http://127.0.0.1:' + os.environ.get('KANANA_PORT', '18889'))
parser.add_argument('--health-only', action='store_true')
args = parser.parse_args()
headers = {'Content-Type': 'application/json'}
if os.environ.get('DECISION_API_KEY'):
    headers['Authorization'] = 'Bearer ' + os.environ['DECISION_API_KEY']


def request(route, body=None):
    req = urllib.request.Request(args.endpoint.rstrip('/') + route,
                                 data=json.dumps(body).encode() if body is not None else None,
                                 headers=headers)
    with urllib.request.urlopen(req, timeout=120) as response:
        assert response.status == 200
        return json.load(response)


health = request('/health')
assert health['status'] == 'ready' and health['max_input_tokens'] == 20480
if args.health_only:
    print(json.dumps(health))
    raise SystemExit(0)
assert request('/v1/models')['models'][0]['name'] == health['model']
body = dict(state='The item I ordered arrived damaged. Please replace it.', questions={
    'intent': dict(type='choice', instructions='Classify the customer request.',
                   criteria={'exchange': 'Exchange or replacement', 'cancel': 'Cancellation', 'other': 'Other'}),
    'damaged': dict(type='noul', instructions='Is the item damaged?'),
    'urgency': dict(type='score', instructions='Rate urgency.', criteria=['low', 'medium', 'high'])})
started = time.monotonic()
result = request('/v1/systemone', body)
for name in body['questions']:
    answer = result['answers'][name]
    assert answer['type'] == body['questions'][name]['type']
    if answer['type'] == 'noul':
        assert math.isfinite(answer['noul']) and .5 < answer['noul'] <= 1
        continue
    values = list(answer['probabilities'].values())
    assert all(math.isfinite(v) for v in values) and abs(sum(values) - 1) < 1e-5
assert result['answers']['intent']['choice'] == 'exchange'
assert result['usage']['output_tokens'] == 0
print(json.dumps(dict(pass_=True, seconds=time.monotonic() - started, response=result), ensure_ascii=False, indent=2))
