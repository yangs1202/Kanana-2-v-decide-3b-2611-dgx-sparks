# GLM512K와 Kanana 동시 부하 검증

2026-11-08 KST. 사용자 요청으로 양쪽GLM을 유지하고2호기Kanana에 부하를 보냈다.
[kanana-co-load-probe.py](../scripts/co_load.py)는기동 중인HTTP 서버를사용하며모델을새로로딩하지않는다.

## 고정 조건

- Kanana:dgx2 `kanana-decide`, BF16/SDPA, direct CUDA, 모델commit
  `1489062def4145ae3a0a9261fbac4f4d88a8c6d1`.
- image ID:`sha256:349154e3f5a2cf08d1971453a9ed568f3ceed703e74569540ba7d9eafc44f2c5`.
  Transformers5.5.3/Accelerate1.12.0/torch2.13.0a0+9186a08b2c.nv26.07.
- GLM:양쪽`glm53-spark`, context524288/parallel8/FP8 KV, thinking=false/temperature0.
  실행recipe commit:`13f2464ee84ab2b5dabf0bb264d1144b02cf5fb7`.
  image ID:`sha256:6f08848c663bdc3d60cacfc863c28f9764fb86ed0fd426abf25da0f44dc07e73`.
- GLM 부하는C2이며실제input8542/output128token을반복한다. 동일prompt를사용해
  202개중200개는8192token cache hit, 2개는cold였다. 지속fresh-prefill 부하와구분한다.
- Kanana는short/long/images10 C1, mixed C6를각3회wave로시험한다.
  공식서버의직렬추론lock을유지하므로C6는GPU 병렬화가아닌HTTP 대기열이다.
- long/mixed는한국어문장1800회이며입력잘라내기를활성화한20,480token 요청이다.
- images10/mixed는서로다른1280×1280 JPEG10개, quality90,
  Python `random.Random(2611).randbytes`로생성한다.
  HTTP client는host Python3.12.3/Pillow10.2.0을사용한다.
  이전단독부하의NumPy RNG와이미지내용은다르므로엄밀히동일fixture의성능비교가아니다.
- startup warmup은Kanana exchange와GLM 계산5를확인하고성능평균에서제외한다.
- 양쪽부하의요청시작/종료시각을보존하여실제겹침을집계한다.
- 2호기MemAvailable/SwapFree/Kanana RSS를200ms마다기록한다.
  메모리는두모델/HTTP client/OS를포함하며Kanana 단독사용량으로해석하지않는다.
- 요청사이allocator cache를강제로해제하지않는다. 기존worker4GiB Kanana 중지guard와
  leader8GiB Kanana 우선중지guard를유지한다. OOM 방지를보장하지않는다.

raw 작업디렉터리:dgx2 `/home/USER/kanana-co-load-20261108/`.
실행/guard/상태로그와결과는dgx1 `/home/USER/ds4/results/kanana-co-load-20261108-1489062/`에보존한다.
GLM512K 최대길이prefill, 최대운영동시성8, 장시간soak 또는판정품질의검증은아니다.

## 결과

| Kanana 조건 | wave 3회 평균 완료 초 | 평균 HTTP 지연 초 | 2호기 최저 가용 GiB |
| --- | ---: | ---: | ---: |
| short C1 | 0.097 | 0.092 | 14.200 |
| long C1 | 10.635 | 10.634 | 12.257 |
| images10 C1 | 22.390 | 22.389 | 7.172 |
| mixed C6 | 214.545 | 128.102 | 5.978 |

- 위 반복 시험은 Kanana 요청 27개다. 이후 60.900초간 mixed/short를 교대로 3개 보냈다.
  지속 시험은 단일 관측이며 3회 평균으로 표시하지 않는다.
- Kanana 총 30개와 GLM 202개 부하 요청이 전부 성공했다. warmup과 종료 smoke는 별도다.
- Kanana의 모든 30개 요청 구간이 GLM HTTP 요청 구간과 겹쳤다.
  GPU kernel이 동시에 실행됐다는 의미는 아니다.
- 전체 2호기 최저 MemAvailable은 6,322,409,472bytes, **5.888203GiB**였다.
- 30초 idle 후는 7,557,402,624bytes, **7.038380GiB**였다.
  client 종료 후 추가 확인에서는 약7.16GiB였다.
- 실제 Kanana 사용량은 short90/images16110/long·mixed20480token이었다.
- GLM 요청 평균 지연은 8.013초다. 이 값은 202개 요청의 관측 평균이며
  독립 3회 GLM benchmark 평균이나 단독 성능 대비 비율로 해석하지 않는다.
- 무거운 혼합 입력 C6에서는 마지막 응답까지 평균 약3분35초였다.
  GPU 공유와 직렬 대기열을 포함한 실제 HTTP 지연으로, 메모리 통과와 응답 속도는 구분한다.

## 종료 검증과 현재 상태

- 양쪽 GLM 및 Kanana는 모두 running/restart0/OOMKilled=false이며 기동한 채 유지했다.
- worker4GiB guard는 발동하지 않았고, 양쪽 guard 프로세스와 로그를 확인했다.
- 종료 후 Kanana exchange 분류와 GLM 계산5를 다시 assert했다.
- GLM health ok/warming=false, Kanana health ready였다.
- 양쪽 GLM/커널 및 Kanana 로그의 CUDA/NCCL/OOM/Traceback/fatal/kill 검색은 0건이었다.
- LiteLLM readiness는 HTTP200/healthy/db connected였다. proxy 경유 추론은 별도 미검증이다.

이번 조건에서는 GLM512K와 2호기 Kanana의 동시 실행이 통과했다.
입력이 더 길거나 GLM 동시성이 더 높아지는 경우의 여유, 수시간 안정성, 모든 요청에서의
OOM 방지를 보장하지 않는다. 영구 실행 설정과 메모리 guard 기준은 이번 시험에서 변경하지 않았다.

Notion: 동시 부하 보고서 (private historical workspace).
공통 benchmark DB에 조건별 3-wave 평균4행과 sustained/idle 단일 관측1행을 구분해 기록했다.
