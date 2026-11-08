"""Text-only CSAT choice benchmark against an already running Kanana server."""
import argparse
import hashlib
import json
import math
import re
import statistics
import time
import urllib.request
from pathlib import Path

CIRCLED = '①②③④⑤'
ANSWER_URL = 'https://www.suneung.re.kr/boardCnts/fileDown.do?fileSeq=46c7d36aa9208016099f9a4cf2e7cc2a'


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def prepare(args):
    import pymupdf
    pdf = pymupdf.open(args.pdf)
    supplements = json.loads(Path(args.supplements).read_text())
    answer_bytes = urllib.request.urlopen(ANSWER_URL, timeout=30).read()
    (args.root / 'official-answer.pdf').write_bytes(answer_bytes)
    answer_pdf = pymupdf.open(stream=answer_bytes, filetype='pdf')
    keys = {}
    for index, form in enumerate(('odd', 'even')):
        for section, x0, x1 in [('common', 90, 190), ('common', 194, 294),
                                ('speech', 299, 400), ('language', 404, 500)]:
            text = answer_pdf[index].get_text(clip=pymupdf.Rect(x0, 253, x1, 720))
            triples = re.findall(r'(\d+)\s*([①②③④⑤])\s*([23])', text)
            for number, choice, points in triples:
                keys[f'{form}-{section}-{number}'] = dict(answer=str(CIRCLED.index(choice) + 1), points=int(points))
    assert len(keys) == 112, len(keys)
    cases = []
    for index, form in enumerate(('odd', 'even')):
        sections = [('common', 0, 12), ('speech', 12, 16), ('language', 16, 20)]
        for section, start, end in sections:
            page_texts = []
            for page_index in range(start + index * 20, end + index * 20):
                page = pdf[page_index]
                columns = []
                for x0, x1 in [(80, 418), (423, 765)]:
                    # PDF block order preserves choice labels before their multi-line examples.
                    blocks = page.get_text('blocks', clip=pymupdf.Rect(x0, 150, x1, 1070))
                    columns.append('\n'.join(b[4] for b in blocks if b[6] == 0))
                text = '\n'.join(columns)
                text = re.sub(r'^\s*(?:홀수형|짝수형|제1 교시|\(화법과 작문\)|\(언어와 매체\))\s*$', '', text, flags=re.M)
                text = text.split('* 확인 사항')[0]
                page_texts.append(text)
            text = '\n'.join(page_texts)
            if section == 'common':
                ranges = [(1, 3), (4, 9), (10, 13), (14, 17), (18, 21), (22, 26), (27, 30), (31, 34)]
            elif section == 'speech':
                ranges = [(35, 37), (38, 42), (43, 45)]
            else:
                ranges = [(35, 36), (37, 37), (38, 38), (39, 39), (40, 43), (44, 45)]
            starts = []
            for first, last in ranges:
                pattern = rf'\[{first}～{last}\]' if first != last else rf'(?m)^{first}\.\s'
                match = re.search(pattern, text)
                assert match, (form, section, first)
                starts.append(match.start())
            for n, (first, last) in enumerate(ranges):
                group = text[starts[n]:starts[n + 1] if n + 1 < len(starts) else len(text)]
                first_question = re.search(rf'(?m)^{first}\.\s', group)
                assert first_question
                passage = group[:first_question.start()]
                supplement = supplements.get(f'{section}-{first}', '')
                if supplement:
                    group += '\n\n[원본 PDF의 표·화면·기호를 텍스트로 옮긴 자료]\n' + supplement
                for number in range(first, last + 1):
                    match = re.search(rf'(?m)^{number}\.\s', group)
                    assert match, (form, section, number)
                    following = re.search(rf'(?m)^{number + 1}\.\s', group[match.end():]) if number < last else None
                    end_pos = match.end() + following.start() if following else group.find('\n\n[원본 PDF')
                    if end_pos < 0:
                        end_pos = len(group)
                    question = group[match.end():end_pos]
                    choices = list(re.finditer('[①②③④⑤]', question))
                    assert len(choices) == 5, (form, section, number, len(choices))
                    stem = question[:choices[0].start()].strip()
                    criteria = {str(i + 1): re.sub(r'\s+', ' ', question[m.end():choices[i + 1].start() if i < 4 else len(question)]).strip()
                                for i, m in enumerate(choices)}
                    if section == 'common' and number == 16:
                        # This worksheet prints option numbers AFTER the associated statements.
                        stem, worksheet = question.split('□', 1)
                        previous = 0
                        for i, m in enumerate(re.finditer('[①②③④⑤]', worksheet)):
                            criteria[str(i + 1)] = re.sub(r'[·\s]+', ' ', worksheet[previous:m.start()]).strip()
                            previous = m.end()
                        criteria['1'] = criteria['1'][criteria['1'].index('∙칸트:'):]
                    group_state = passage + ('\n[표·화면·기호의 텍스트 전사]\n' + supplement if supplement else '')
                    if section == 'language' and number in (35, 36):
                        # A few historical Hangul glyphs are raster-only / private-use glyphs.
                        group_state = group_state.replace('‘\n’', '‘ㆁ’')
                        criteria = {k: v.replace('‘ ’', '‘ㆁ’') for k, v in criteria.items()}
                    criteria = {k: v.rstrip(' (') for k, v in criteria.items()}
                    case_id = f'{form}-{section}-{number}'
                    payload = dict(state=group_state, questions={case_id: dict(type='choice',
                                   instructions=re.sub(r'\s+', ' ', stem) + ' 다섯 선택지 중 하나를 고르세요.',
                                   criteria=criteria)})
                    cases.append(dict(id=case_id, form=form, section=section, number=number,
                                      payload=payload))
    assert len(cases) == 112 and len({c['id'] for c in cases}) == 112
    save(args.root / 'cases.json', cases)
    save(args.root / 'answer-key.json', dict(source=ANSWER_URL, keys=keys))
    save(args.root / 'source.json', dict(pdf_sha256=hashlib.sha256(Path(args.pdf).read_bytes()).hexdigest(),
                                       answer_sha256=hashlib.sha256(answer_bytes).hexdigest(),
                                       text_conversion='PyMuPDF column clips plus manually transcribed visual supplements',
                                       pages=40, cases=112, unique_questions=56))
    print('prepared', len(cases), flush=True)


def post(endpoint, payload):
    request = urllib.request.Request(endpoint + '/v1/systemone',
                                    data=json.dumps(payload, ensure_ascii=False).encode(),
                                    headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(request, timeout=180) as response:
        assert response.status == 200
        return json.load(response)


def run(args):
    cases = json.loads((args.root / 'cases.json').read_text())
    health = json.load(urllib.request.urlopen(args.endpoint + '/health', timeout=10))
    assert health['status'] == 'ready'
    warmup = post(args.endpoint, dict(state='사과는 과일이다.', questions={'warmup': dict(type='choice',
                  instructions='사과는 무엇인가?', criteria={'1': '과일', '2': '동물'})}))
    assert warmup['answers']['warmup']['choice'] == '1'
    save(args.root / 'warmup.json', dict(health=health, response=warmup, performance_sample=False))
    with (args.root / 'results.jsonl').open('w', buffering=1) as output:
        for run_number in range(1, 4):
            for case in cases:
                available = next(int(line.split()[1]) for line in Path('/proc/meminfo').read_text().splitlines()
                                 if line.startswith('MemAvailable:')) * 1024
                assert available >= 4 * 1024 ** 3, '4 GiB memory floor'
                started = time.time()
                response = post(args.endpoint, case['payload'])
                elapsed = time.time() - started
                answer = response['answers'][case['id']]
                probabilities = answer['probabilities']
                assert set(probabilities) == set('12345')
                assert all(math.isfinite(v) for v in probabilities.values())
                assert abs(sum(probabilities.values()) - 1) < 1e-5
                assert response['usage']['input_tokens'] < health['max_input_tokens']
                row = dict(id=case['id'], run=run_number, start=started, seconds=elapsed,
                           mem_available_bytes=available, response=response)
                output.write(json.dumps(row, ensure_ascii=False) + '\n')
                print(case['id'], run_number, answer['choice'], round(elapsed, 3), flush=True)


def grade(args):
    cases = json.loads((args.root / 'cases.json').read_text())
    keys = json.loads((args.root / 'answer-key.json').read_text())['keys']
    rows = [json.loads(line) for line in (args.root / 'results.jsonl').read_text().splitlines()]
    assert len(rows) == 336
    for run_number in range(1, 4):
        (args.root / f'kanana-csat-20261108-1489062-run-{run_number}.jsonl').write_text(
            ''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows if row['run'] == run_number))
    summary = dict(requests=len(rows), conditions='C1; 3 complete passes; default Decider probability temperature; existing GLM remains running; warmup excluded', forms={})
    graded = []
    for case in cases:
        samples = [r for r in rows if r['id'] == case['id']]
        assert len(samples) == 3
        predictions = [r['response']['answers'][case['id']]['choice'] for r in samples]
        graded.append(dict(id=case['id'], form=case['form'], section=case['section'], number=case['number'],
                           **keys[case['id']], predictions=predictions,
                           correct=predictions[0] == keys[case['id']]['answer'], stable=len(set(predictions)) == 1,
                           mean_seconds=statistics.mean(r['seconds'] for r in samples),
                           input_tokens=[r['response']['usage']['input_tokens'] for r in samples]))
    for form in ('odd', 'even'):
        subset = [r for r in graded if r['form'] == form]
        sections = {}
        for section in ('common', 'speech', 'language'):
            items = [r for r in subset if r['section'] == section]
            sections[section] = dict(correct=sum(r['correct'] for r in items), total=len(items),
                                     score=sum(r['points'] for r in items if r['correct']),
                                     max_score=sum(r['points'] for r in items))
        exams = {s: dict(score=sections['common']['score'] + sections[s]['score'],
                         correct=sections['common']['correct'] + sections[s]['correct'], total=45, max_score=100)
                 for s in ('speech', 'language')}
        assert all(sections['common']['max_score'] + sections[s]['max_score'] == 100 for s in ('speech', 'language'))
        summary['forms'][form] = dict(correct=sum(r['correct'] for r in subset), total=56, sections=sections, exams=exams)
    times = [r['seconds'] for r in rows]
    summary.update(mean_seconds=statistics.mean(times), median_seconds=statistics.median(times),
                   p95_seconds=sorted(times)[math.ceil(len(times) * .95) - 1],
                   max_seconds=max(times), stable_cases=sum(r['stable'] for r in graded),
                   min_mem_available_gib=min(r['mem_available_bytes'] for r in rows) / 1024 ** 3,
                   max_input_tokens=max(max(r['input_tokens']) for r in graded),
                   pass_mean_seconds={str(i): statistics.mean(r['seconds'] for r in rows if r['run'] == i) for i in range(1, 4)})
    summary['cross_form_same_selected_text'] = sum(
        next(c for c in cases if c['id'] == a['id'])['payload']['questions'][a['id']]['criteria'][a['predictions'][0]] ==
        next(c for c in cases if c['id'] == b['id'])['payload']['questions'][b['id']]['criteria'][b['predictions'][0]]
        for a, b in zip(graded[:56], graded[56:]))
    save(args.root / 'graded.json', graded)
    save(args.root / 'summary.json', summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


parser = argparse.ArgumentParser()
parser.add_argument('action', choices=('prepare', 'run', 'grade'))
parser.add_argument('--root', type=Path, required=True)
parser.add_argument('--pdf')
parser.add_argument('--supplements')
parser.add_argument('--endpoint', default='http://127.0.0.1:18889')
args = parser.parse_args()
args.root.mkdir(parents=True, exist_ok=True)
globals()[args.action](args)
