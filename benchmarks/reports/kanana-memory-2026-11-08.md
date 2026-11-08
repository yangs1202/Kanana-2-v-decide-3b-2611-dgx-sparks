# Kanana-2-v-decide DGX Spark 메모리 실측

2026-11-08 KST, internal.example.invalid 단독 실행. 사용자의 승인으로 양쪽 GLM을 잠시 중지하고 측정했다.

## 판단

- 가중치 자체 CUDA 할당은 6.83 GiB지만 전체 시스템 추가 메모리는 이보다 크다.
- 시험한 요청의 시스템 메모리 증가 최대치는 11.12 GiB, 로딩 순간은 15.42 GiB였다.
- 시작 전 **18~20 GiB 가용 메모리 확보**를 권장한다. 실측 peak에 여유를 더한 운영 판단이며 보장된 최소 사양은 아니다.
- 기존 GLM 운영 중 관측한 가용 메모리 9.2/11 GiB로는 이 로딩 방식의 peak를 수용할 여유가 부족하다. GLM과 동시 실행은 시험하지 않았다.
- 더 큰 이미지 10장, 최대 길이 입력, 동시 추론 등 미측정 조건에는 위 권장치를 그대로 적용하지 않는다.

## 고정 조건

- 모델: `kakaocorp/kanana-2-v-decide-3b-2611`
- 모델 commit: `1489062def4145ae3a0a9261fbac4f4d88a8c6d1`
- 가중치 SHA-256: `528930fa261b31ed1f47eecbe7d08efd2e226207508124ae186e1a65dbbbda3b`
- 노드: NVIDIA GB10, aarch64, 시스템 메모리 약 121.7 GiB
- BF16, SDPA, 동시 추론 1개, `eval()`, 모델 기본 `use_cache=False`
- Transformers `5.5.3`, Pillow `12.1.1`, safetensors `0.7.0`
- PyTorch `2.13.0a0+9186a08b2c.nv26.07`: 공식 requirements의 `2.10.0`과 다르다.
- 기반 image digest: `nvcr.io/nvidia/pytorch@sha256:2140e699b3beaf7f96a0081fd9c9406bc3832b435cdb60dfa2d261f7d2f34a1c`
- 의존성 설치 후 보존 image: `kanana-memory:20261108-transformers553`, local image ID `sha256:1c6f223ede3361d68d3aaf1cb000d1c6af3bc3a7e2466fffeff7677f6db4eb3a`
- 원본: dgx1 `/home/USER/ds4/results/kanana-memory-20261108-1489062/`
- 실행 스크립트: [kanana-memory-probe.py](../scripts/memory.py)

## 측정 방법과 제한

시스템 메모리는 Python 프로세스의 모델 로딩 전 `MemAvailable`과 각 구간 최솟값의 차이다. 20ms마다 표본을 수집했으며 OS 변동과 표본 사이의 peak 누락 가능성이 있다. GLM과 다른 GPU 추론 프로세스는 중지했다. CUDA peak는 PyTorch allocator 통계를 사용했다. 통합 메모리 환경이므로 RSS와 CUDA 수치를 단순 합산하지 않는다.

각 조건은 3회 실행했다. 평균은 시간만 집계했고 메모리는 3회 중 최대치로 판단했다. 요청마다 candidate cache를 비우고 `gc.collect()` 및 `torch.cuda.empty_cache()`를 실행했다. 마지막 cached 조건만 선택지 벡터를 미리 채웠다. 공식 서버를 장기 운영할 때의 allocator 잔류 상태와 구분한다.

선택지 3개의 `choice` 질문 하나를 사용했다. 이미지 fixture는 흰 배경에 빨간 사각형인 합성 이미지다. 실제 사진 정확도 평가는 아니다. processor의 이미지 축소와 토큰화가 반영된 실측이다. 원본 이미지 크기에 비례한 메모리 증가를 가정하지 않는다.

text 이름의 숫자는 state 생성 전 token target이다. decode 후 재토큰화로 길이가 달라졌으므로 실제 사용량을 별도로 표시했다. 사용량은 질문과 candidate 인코딩을 합한 `usage.input_tokens`이며 cached 조건에서는 이미 저장된 candidate가 제외된다. 잘라내기는 비활성화했다. 정확한 20,480-token 상한 시험은 하지 않았다.

## 결과

| 조건 | 실제 input tokens | 평균 시간(초), 3회 | CUDA peak allocated GiB | CUDA peak reserved GiB | 추가 시스템 메모리 peak GiB |
| --- | ---: | ---: | ---: | ---: | ---: |
| text target 256 | 380 | 0.149 | 6.92 | 6.98 | 9.62 |
| text target 2,048 | 1,916 | 0.366 | 7.02 | 7.14 | 9.78 |
| text target 8,192 | 7,182 | 1.355 | 7.36 | 7.59 | 10.22 |
| text target 20,000 | 17,303 | 3.612 | 8.02 | 8.49 | 11.12 |
| 512×512 이미지 1장 | 428 | 0.565 | 6.95 | 7.03 | 9.96 |
| 1280×1280 이미지 1장 | 1,772 | 0.728 | 7.23 | 7.45 | 10.64 |
| 512×512 이미지 10장 | 2,750 | 1.043 | 7.43 | 7.76 | 11.04 |
| 짧은 text, candidate cached | 90 | 0.038 | 6.90 | 6.97 | 10.21 |

마지막 cached 조건은 이미지 시험 이후 실행되어 CPU RSS 등의 이전 작업 영향이 남아 있다. 위 시간은 요청당 Python `system_one` 실행 시간이며 네트워크 지연은 포함하지 않는다. 기사 H200 수치와 동일 조건의 비교가 아니다.

로딩은 공식 예제처럼 CPU `from_pretrained` 후 `.to('cuda')`를 사용했다. 1회 관측에서 53.67초, CUDA 6.83 GiB, CPU RSS peak 7.65 GiB, 추가 시스템 메모리 peak 15.42 GiB였다. 로딩 후 시스템 메모리 증가는 약 8.69 GiB였다. GPU 직접 로딩 등 메모리 절감 방식은 시험하지 않았다.

## 검증과 복구

- startup warmup: choice/noul/score 응답 성공, 교환 분류와 파손 확률 > 0.5 확인. 단일 관측이며 성능 평균에서 제외.
- candidate cache가 실제 채워지는 것을 확인했다.
- 공식 `SystemOneServer`를 같은 모델 인스턴스에 연결하여 localhost:18889의 `/health`, `/v1/models`, `/v1/systemone` HTTP 200을 확인했다.
- 8개 요청 조건 모두 3회씩 성공했다. raw 응답과 메모리 기록 26개(load/warmup 포함)를 보존했다.
- Kanana를 종료하고 기존 GLM 컨테이너를 worker→leader 순서로 재시작했다. 기존 image와 실행 인자는 변경하지 않았다.
- 복구 후 direct `/health`는 `status=ok`, `warming=false`. warmup은 `OK`, 계산 smoke test는 `5`를 반환했다. 응답 원본을 raw 디렉터리에 보존했다.
- 양쪽 GLM 컨테이너는 running, restart count 0, OOMKilled=false였고 image ID는 이전과 동일했다. 재시작 이후 Docker 로그의 `CUDA error`, `NCCL error`, `out of memory`, `Traceback`, `fatal` 검색은 양쪽 모두 0건이었다. 커널 전체 로그 검사와 구분한다.
- LiteLLM `https://internal.example.invalid/health/liveliness`, `/health/readiness`는 HTTP 200, readiness는 `healthy/db connected`였다. proxy 경유 모델 추론은 별도 검증하지 않았다.
- Kanana 시험 컨테이너는 exited 상태이며 GLM이 GPU를 다시 사용 중이다.

출처: [공식 모델 카드](https://huggingface.co/kakaocorp/kanana-2-v-decide-3b-2611).

Notion: 측정 보고서 (private historical workspace), 공통 benchmark DB (private historical workspace). 조건별 3회 집계 8행과 load/warmup 단일 관측 2행을 구분해 기록했다.
