# Kanana 단독 HTTP 부하 메모리 검증

2026-11-08 KST. 사용자가 TP2 시험을 취소하고 GLM을 내린 상태의 Kanana 단독 부하를 요청했다.
TP2 컨테이너는 실행하지 않았다. 준비하던 TP 코드는 제거했다.

## 실행 조건

- dgx1 단독, GB10 통합 메모리. 양쪽 GLM을 중지했다.
- 모델 `kakaocorp/kanana-2-v-decide-3b-2611`, commit `1489062def4145ae3a0a9261fbac4f4d88a8c6d1`.
- BF16/SDPA, `device_map='cuda'`, Transformers5.5.3, Accelerate1.12.0.
- PyTorch `2.13.0a0+9186a08b2c.nv26.07`이며 공식 요구 버전2.10.0과 다르다.
- local image `kanana-memory:20261108-direct-accelerate112`, ID `sha256:349154e3f5a2cf08d1971453a9ed568f3ceed703e74569540ba7d9eafc44f2c5`.
- [kanana-load-probe.py](../scripts/load.py)에서 공식 `Decider`/`SystemOneServer`를 localhost18889로 실행했다.
- 공식 서버의 lock을 유지했다. C2/C4/C6은 HTTP 동시 요청 수이며 GPU 추론은 직렬이다.
- 기본 candidate cache를 유지하고 요청 사이 `empty_cache()`나 GC를 강제로 실행하지 않았다.
- 입력 잘라내기를 활성화했다. 실제 forward 입력 길이를 hook으로 기록했다.
- 이미지10개는 seed2611의 서로 다른1280×1280 난수 JPEG, quality90이다. 정확도 평가용 사진이 아니다.
- long/mixed의 state는 한국어 문장1800회이며 max_length20480으로 잘린다.
- 100ms마다 MemAvailable/RSS/SwapFree를 기록했다. 모델·PyTorch import 전 baseline 대비 감소량이다.
  Python 프로세스가 실행된 이후의 baseline이며, 이전 보고서의 torch import 이후 baseline과 구분한다.
- 부하 중 MemAvailable이8GiB 미만이면 Kanana를 중지하는 별도 감시를 시작했다. OOM 방지를 보장하지 않는다.

## 집계 규칙

short/long/images10/mixed C1과 mixed C2/C4/C6 각각3회 wave를 수행한다.
HTTP 지연에는 서버 대기열·JSON·이미지 전처리·GPU 추론이 모두 포함된다.
동시성별 wave3개의 완료 시간 평균과 요청 지연 평균을 구분한다.
메모리는 wave 중 최대치로 판단하며 평균치로 안전성을 판단하지 않는다.
startup warmup은 pass/fail만 기록하고 부하 평균에서 제외한다.
60초 지속 부하와30초 idle은 각각 단일 관측이며3회 평균으로 표시하지 않는다.
표본 사이의 peak 누락, OS 및 파일 캐시 변동 가능성이 있다. CUDA와 RSS는 단순 합산하지 않는다.

## 측정 결과

| 조건 | wave3회 평균 완료 초 | 평균 HTTP 지연 초 | 추가 시스템 peak GiB | CUDA allocated peak GiB |
| --- | ---: | ---: | ---: | ---: |
| short C1 | 0.039 | 0.038 | 10.034 | 6.865 |
| long C1 | 4.665 | 4.665 | 11.844 | 8.197 |
| images10 C1 | 7.504 | 7.504 | 16.486 | 10.157 |
| mixed C1 | 13.676 | 13.675 | 16.342 | 10.178 |
| mixed C2 | 27.463 | 20.541 | 16.064 | 10.178 |
| mixed C4 | 55.823 | 35.084 | 16.387 | 10.178 |
| mixed C6 | 85.523 | 50.239 | 16.967 | 10.178 |

long/mixed의 실제 forward는20,480token, images10은16,107token, short는87token이었다.
후보3개는warmup 후cache되어 있으므로 위 실제 사용량에는 재계산분이 포함되지 않는다.
CPU 전처리와 큰payload의queue를 포함하므로 C6은GPU 병렬화 성능이 아니다.

- 로딩 단일 관측:54.553초, 추가system peak15.814GiB, 직후9.023GiB.
- warmup:HTTP200, exchange 분류, candidate cache 생성을 확인했다. 단일pass이며 평균에서 제외했다.
- 반복 부하48request와 지속 부하9request, 총57request가 모두 성공했다.
- 지속 부하는60초 이상short/mixed를 교대로 전송했고 마지막request 완료까지70.224초였다.
  이 단일 관측의system peak는17.122GiB, 부하 종료 시점은16.225GiB였다.
- 이어지는30초idle 이후에도16.067GiB가 남았다. CUDA allocated6.859GiB, reserved11.822GiB였다.
- 최대query 길이20,480, 후보cache3개, 모든 분류 확률의 유한값과 합계1을 검증했다.

## 운영 판단과 제한

초기 대기의 약9GiB만으로는 시험한 부하 이후 필요한 메모리를 감당할 수 없다.
이번 최대17.12GiB에8GiB 가용 메모리 여유를 더하면 약25GiB 예산이다.
관측에 여유를 더한 운영 판단이며, 보장된 최소 사양이나GLM 동시 실행 실적은 아니다.
무거운 부하 이후allocator/CPU 메모리가 남았지만 원인별 엄밀한 내역이나leak 여부는 판정하지 않았다.
빈cache 해제, 수시간soak, candidate4096개 포화, 실제GPU 동시 추론은 미검증이다.
이미지는 합성 데이터이며 판정 품질 평가는 아니다.

raw:dgx1 `/home/USER/ds4/results/kanana-load-20261108-1489062/`。
HTTP log, 100ms memory.jsonl, 각wave의response/forward shape/allocator 통계, image/container inspect,
script SHA256, 실행wrapper와guard를 보존한다.
Notion:단독 부하 보고서 (private historical workspace).
공통benchmark DB에 조건별3-wave 평균7행과warmup/sustained 단일 관측2행을 구분해 기록했다.

## 종료와 복구 검증

- Kanana 시험 컨테이너는 종료됐고 메모리 중단guard는 발동하지 않았다.
- 보존한GLM512K 컨테이너를worker→leader 순으로 재시작했다. 영구 설정과1M 백업은 변경하지 않았다.
- 양쪽running/restart0/OOMKilled=false, direct health ok/warming=false를 확인했다.
- `/v1/models`의max_model_len524288과계산smoke 응답5를assert했다.
- 양쪽GLM의시험 구간CUDA/NCCL/OOM/Traceback/fatal 로그검색0건,
  양쪽커널의OOM/kill 로그검색0건이었다. raw 로그를 함께 보존했다.
- LiteLLM readiness HTTP200/healthy/db connected였다. proxy 경유 모델 추론은 별도 검증하지 않았다.
- 컨테이너 중지로 종료된메모리 감시를 복구했다. PID2942582,
  `/home/USER/kanana-direct-20261108/glm-memory-guard.py`가 양쪽8GiB/2초 조건을 감시한다.
- 복구 후가용 메모리는leader 약20GiB, worker 약22GiB였다. GLM과Kanana 동시 실행은 하지 않았다.
