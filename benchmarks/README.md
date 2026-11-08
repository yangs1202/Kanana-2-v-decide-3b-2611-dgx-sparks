# 벤치마크 자료와 재현

2026-11-08에 측정한 모든 Kanana 실험을 공개합니다. 보고서는 당시 조건과 판단을 보존한 역사 기록이며, 중간 실험의 메모리 권장치나 컨테이너 상태가 현재 설치 기본값을 뜻하지 않습니다. 최종 운영 설명은 루트 README를 기준으로 보세요.

| 실험 | 보고서 | raw |
|---|---|---|
| 초기 CPU→CUDA 로딩·8조건 | [memory](reports/kanana-memory-2026-11-08.md) | [memory](raw/kanana-memory-20261108-1489062/) |
| 직접 CUDA 독립 프로세스 3회 | [direct-memory](reports/kanana-direct-memory-2026-11-08.md) | [direct-memory](raw/kanana-direct-memory-20261108-1489062/) |
| 단독 HTTP 부하·잔류 메모리 | [load](reports/kanana-load-2026-11-08.md) | [load](raw/kanana-load-20261108-1489062/) |
| GLM과 배치·시작 확인 | [coexist](reports/kanana-coexist-2026-11-08.md) | [coexist](raw/kanana-coexist-20261108-1489062/) |
| GLM C2 + Kanana 부하 | [co-load](reports/kanana-co-load-2026-11-08.md) | [co-load](raw/kanana-co-load-20261108-1489062/) |
| 최초 독해 한 문항 | [reading](reports/reading-2026-11-08.md) | [reading](raw/kanana-reading-20261108-1489062/) |
| 수능 국어 전체 | [CSAT](reports/kanana-csat-2026-11-08.md) | [CSAT](raw/kanana-csat-20261108-1489062/) |
| 동시 실행의 GLM 512K 조건 | [GLM profile](reports/glm53-512k-check-2026-11-08.md) | 각 동시 부하 raw의 health/models |

## 공개 처리

측정값·질문·응답·메모리 시계열·warmup·3회 결과·로그·합성 fixture를 보존했습니다. 내부 호스트/IP/사용자 경로는 치환했고 Docker inspect는 image/state/restart 등 필요한 항목만 공개했습니다. 환경변수·mount·network·label 전체 덤프는 제외했습니다. 운영용 SSH/복구 wrapper, PID 파일, 중복 스크립트, 원본 정답 PDF는 재배포하지 않습니다. 대응 스크립트와 공식 정답 링크를 제공합니다.

[publication-manifest.json](publication-manifest.json)에 파일별 원본 SHA256, 공개본 SHA256, 처리 방식과 제외 목록을 기록했습니다. 일반 JSON 결과의 숫자는 원본과 동일함을 대조했습니다. 원본 전체는 실험 노드에 보존되어 있으며 공개본 해시는 `python3 tests/check_artifacts.py`로 검사할 수 있습니다. 이 저장소에는 가중치·인증키가 없습니다.

`raw`는 과거 측정 아카이브입니다. 재실행 결과는 별도 `results/`에 저장하세요. 과거 이미지 ID와 현재 레시피를 다시 빌드한 이미지 ID는 다릅니다. 기반 NGC digest와 runtime 버전은 고정했고 각 ID를 구분해 기록했습니다.

## 메모리·단독 부하 재현

루트 레시피 이미지와 검증된 모델 디렉터리가 필요합니다. 서버를 포함해 실행하는 실험이므로 동일 포트에서 이 레시피가 실행 중이면 먼저 `./stop.sh`를 실행합니다. 이 wrapper는 다른 모델을 중단하지 않습니다. 다른 모델이 이미 실행 중이면 단독 실험 조건이 아니므로 결과를 분리하세요.

```bash
./benchmarks/run.sh memory
./benchmarks/run.sh direct-memory  # 독립 프로세스 3회
./benchmarks/run.sh load           # 20,480토큰 / 이미지 10장 / C1,C2,C4,C6
```

`memory`는 요청 사이 GC/empty_cache와 후보 캐시 해제를 사용하고, `load`는 요청 사이 캐시를 유지합니다. 이미지 fixture도 다르므로 보고서 조건을 구분하세요. 무거운 실험은 충분한 MemAvailable에서 실행해야 합니다. 설치 서버와 같은 메모리 guard가 해당 실험 컨테이너만 감시합니다.

## 기존 GLM과 동시 부하 재현

이 실험은 이미 실행 중인 모델에 요청만 보냅니다. GLM 설치·재시작·context 변경은 수행하지 않습니다. 원래 비교 조건은 GLM context 524,288, max parallel 8, FP8 KV, DFlash2, GLM 요청 C2/input8542/output128입니다. 두 모델의 설정이 다르면 같은 조건으로 집계하지 마세요.

```bash
python3 -m venv .venv
.venv/bin/pip install pillow==10.2.0
GLM_ENDPOINT=http://GLM_HOST:18888 \
KANANA_ENDPOINT=http://127.0.0.1:18889 \
KANANA_CONTAINER=kanana-dgx-sparks \
RESULTS_DIR="$PWD/results/co-load-new" \
  .venv/bin/python benchmarks/scripts/co_load.py
```

클라이언트의 원래 버전은 Python 3.12.3/Pillow 10.2.0이며 이미지 생성기는 `random.Random(2611).randbytes`입니다. 과거 단독 부하의 NumPy fixture와 같지 않습니다. 인증이 없는 로컬 direct API 실험용 스크립트입니다. GLM_ENDPOINT를 명시하지 않으면 실행되지 않습니다. C6은 서버 GPU 병렬 추론 수가 아니라 동시 HTTP 요청 수입니다.

## 수능 평가 재현

전사한 실제 입력과 정답·배점을 함께 공개했습니다. 정답은 추론 payload에 포함되지 않습니다. 점수는 각 입력의 첫 회 선택으로 계산하고 3회 답의 일관성을 별도로 기록합니다. 홀수/짝수형을 112개의 서로 다른 문제로 합산하지 않습니다.

```bash
mkdir -p results/csat-new
cp benchmarks/raw/kanana-csat-20261108-1489062/{cases,answer-key,source}.json results/csat-new/
python3 benchmarks/scripts/csat.py run --root results/csat-new
python3 benchmarks/scripts/csat.py grade --root results/csat-new
```

위 client는 인증 없는 localhost 서버를 대상으로 합니다. 원본 PDF부터 다시 전사하려면 별도 환경에 `pymupdf`를 설치한 뒤 다음과 같이 실행합니다. 수기 전사 보완본의 표·기호는 같은 시험 PDF에만 적용됩니다.

```bash
python3 benchmarks/scripts/csat.py prepare --root results/csat-prepared \
  --pdf /path/to/2026-korean-exam.pdf \
  --supplements benchmarks/scripts/csat-supplements.json
```

[공식 문제·정답](https://www.suneung.re.kr/boardCnts/view.do?boardID=1500234&boardSeq=5093801&lev=0&m=0403&s=suneung). 원본 PDF SHA256은 raw의 `source.json`에 있습니다. 그림·밑줄·옛한글의 텍스트 전사는 시각 원본과 동등성이 보장되지 않습니다. 이 평가는 일반 독해 문제의 탐색 결과이며 Kanana 공식 Decision Index 평가가 아닙니다.
