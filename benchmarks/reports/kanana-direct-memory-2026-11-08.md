# Kanana GPU 직접 로딩 검증

2026-11-08 KST. 사용자 승인으로 양쪽 GLM을 중지한 뒤 dgx1에서 측정했다.
`KANANA_LOADER=direct-cuda`는 `from_pretrained(device_map='cuda')`를 사용한다.
모든 parameter와 buffer가 CUDA에 있는지 assert했다. 기존 CPU 후 CUDA 경로도 유지한다.

## 조건

- 모델 commit: `1489062def4145ae3a0a9261fbac4f4d88a8c6d1`
- BF16, SDPA, 동시 추론 1개. 기존 측정과 같은 모델·텍스트·합성 이미지.
- Transformers 5.5.3, Accelerate 1.12.0, torch 2.13.0a0+9186a08b2c.nv26.07.
- 기존 준비 이미지에 Accelerate를 추가했다. 이미지 `kanana-memory:20261108-direct-accelerate112`.
- local image ID: `sha256:349154e3f5a2cf08d1971453a9ed568f3ceed703e74569540ba7d9eafc44f2c5`.
- raw: dgx1 `/home/USER/ds4/results/kanana-direct-memory-20261108-1489062/`.
- 독립 프로세스 3개에서 각각 load, warmup, 8조건×3회 요청을 실행했다.

## 결과

메모리는 기존 보고서와 동일하게 metadata baseline의 MemAvailable 대비 감소량이다.
baseline은 Python/torch import 이후이므로 전체 프로세스 시작 비용과 구분한다.
20ms 표본, OS 변동·파일 캐시 영향·표본 사이 피크 누락 가능성이 있다.

| 방식 | 로딩 시간 초 | 로딩 peak GiB | 로딩 직후 GiB |
| --- | ---: | ---: | ---: |
| 기존 CPU 후 CUDA, 단일 관측 | 53.67 | 15.42 | 8.69 |
| 직접 CUDA run1 | 48.98 | 15.39 | 8.54 |
| 직접 CUDA run2 | 51.18 | 14.47 | 7.64 |
| 직접 CUDA run3 | 49.01 | 14.43 | 7.59 |

직접 로딩 평균 시간은 49.73초다. 기존은 단일 관측이므로 3회 평균 성능 비교가 아니다.
직접 로딩도 CPU RSS peak 약 7.65GiB이며 로딩 peak 최대는 기존과 사실상 같다.
직접 CUDA 배치만으로 시스템 메모리 peak가 크게 감소한다는 가설은 확인되지 않았다.
원인별 메모리 breakdown은 측정하지 않았으므로 CPU 복제만을 원인으로 확정하지 않는다.
중간 진행 보고의 15.15/14.25GiB는 load.before 기준이었다. 표는 기존과 맞춘 metadata 기준이다.

| 요청 조건 | 전체 9회 평균 초 | 시스템 추가 peak 최대 GiB |
| --- | ---: | ---: |
| text target256 | 0.1450 | 9.52 |
| text target2048 | 0.3633 | 9.69 |
| text target8192 | 1.3280 | 10.15 |
| text target20000 | 3.5680 | 11.07 |
| image512×512 1장 | 0.2903 | 9.89 |
| image1280×1280 1장 | 0.7222 | 10.41 |
| image512×512 10장 | 1.0459 | 10.78 |
| short candidate cached | 0.0387 | 9.93 |

warmup 3개는 모두 pass이며 성능 평균에서 제외했다. 72개 측정 요청 모두 성공했다.
분류 확률의 유한값과 합1을 별도로 검사했다. 각 프로세스의 공식 HTTP 서버 health/models/추론도 성공했다.
JSON은 각 세션26개, 총78개다. 실제 토큰 수와 세부 allocator 통계는 JSON에 보존했다.
정확한20,480token, 고해상도10장, 동시 추론 및 GLM 동시 실행은 미검증이다.

## 복구

Kanana 종료 후 보존한 GLM512K 컨테이너를 worker→leader 순으로 재시작했다.
양쪽 running/restart0/OOMKilled=false, direct health ok/warming=false,
models의 max_model_len524288, 계산 요청 응답5를 확인했다.
양쪽 재시작 구간 CUDA/NCCL/OOM/Traceback/fatal 로그 검색0건, leader 커널 OOM 검색0건이었다.
LiteLLM readiness도 HTTP200이었다. proxy 경유 모델 추론은 별도 검증하지 않았다.
기존 start.sh의 memory guard는 컨테이너 중지 시 종료되므로 복구 후 별도 감시를 재개했다.
dgx1 `/home/USER/kanana-direct-20261108/glm-memory-guard.py`가 양쪽 MemAvailable을 감시하고
8GiB 미만이2초 지속되면 기존 stop.sh로 양쪽 GLM을 중지한다. OOM 방지를 보장하지 않는다.
GLM 영구 실행 설정은 변경하지 않았고 기존 1M 백업 컨테이너도 보존했다.

Notion: 검증 보고서 (private historical workspace),
공통 DB 측정 행 (private historical workspace).
