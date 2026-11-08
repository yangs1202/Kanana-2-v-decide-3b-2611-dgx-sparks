# 2호기 Kanana와 GLM512K 동시 기동

2026-11-08 KST. 사용자 요청으로 GLM을 유지한 채 dgx2에 Kanana를 추가 기동했다.
고부하 동시 실행이 아닌 로딩과 간단한 요청의 검증이다.

- GLM:양쪽 `glm53-spark`, context524288, parallel8, 기존 image/실행 인자 유지.
- Kanana:dgx2 `kanana-decide`, BF16/SDPA/device_map=cuda, torch CPU threads8.
- 모델 commit:`1489062def4145ae3a0a9261fbac4f4d88a8c6d1`.
- image:`kanana-memory:20261108-direct-accelerate112`, local ID
  `sha256:349154e3f5a2cf08d1971453a9ed568f3ceed703e74569540ba7d9eafc44f2c5`.
- 서버:`kanana-serve.py` (historical wrapper; operational source excluded). 공식 Decider/SystemOneServer를 사용하며 추론은 직렬이다.
- endpoint:dgx2 `http://127.0.0.1:18889`, 추론 `POST /v1/systemone`.
  loopback만 열었고 proxy나외부 라우팅은 추가하지 않았다.
- Docker는host network/ipc, GPU all, 모델readonly `/model`, 실행 디렉터리readonly `/results`.
  실행 디렉터리는`/home/USER/kanana-serve-20261108`이다.
- restart policy는기본no이다. 재부팅 자동 기동은 설정하지 않았다.

## 측정과 검증

- 기동 직전2호기 MemAvailable24,607,625,216bytes, 약22.92GiB.
- 200ms 감시의로딩/간단 요청 구간 최저MemAvailable8.50056GiB.
- warmup 이후MemAvailable15,353,561,088bytes, 약14.30GiB.
- Kanana `/health`, `/v1/models`, `/v1/systemone` 성공.
- choice/noul/score warmup 성공. 교환분류exchange와파손확률0.916>0.5를assert했다.
- 같은 확인 구간에GLM 계산smoke도5를반환했다. 시작 시간을 엄밀히 정렬한 동시 부하 벤치마크는 아니다.
- Kanana와양쪽GLM은running/restart0/OOMKilled=false였다.
- 양쪽GLM/커널과Kanana의시작 이후CUDA/NCCL/OOM/Traceback/fatal/kill 검색0건이었다.
- LiteLLM readiness HTTP200/healthy/db connected였다. proxy 경유 모델 추론은 별도 검증하지 않았다.

## 메모리 감시 변경

사용자는8GiB 여유 유지가필수가아니라고 명시했다. 기존GLM 감시는양쪽8GiB/2초 조건으로
GLM을 중지하므로 이번 동시실행 동안은중지하고 `kanana-trial-guard.py` (historical wrapper; operational source excluded)로 대체했다.

- worker 모드:2호기MemAvailable4GiB 미만이면`docker stop -t 2 kanana-decide`를실행한다.
- leader 모드:1호기MemAvailable8GiB 미만이면Kanana부터중지한다.
- Kanana가종료되면leader 감시는기존GLM 감시
  `/home/USER/kanana-direct-20261108/glm-memory-guard.py`로전환한다.
- 각노드의guard PID/log와2호기의memory.jsonl은실행 디렉터리에있다.
- 4GiB guard는발동하지않았다. 표본지연/stop지연/SSH 장애등이있어OOM 방지를보장하지않는다.

raw snapshot:dgx1 `/home/USER/ds4/results/kanana-coexist-20261108-1489062/`의leader/worker.
현재는두모델을기동한채유지한다. 고해상도10장/20K/대기열6개와GLM 동시부하,
장시간안정성 및지연영향은미검증이다.
