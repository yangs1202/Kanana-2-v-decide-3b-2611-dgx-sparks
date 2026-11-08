# Kanana-2-v-decide-3b-2611 for DGX Spark

[English](README.md) | **한국어**

**Powered by Kanana** · NVIDIA GB10 / Linux aarch64 · BF16 / SDPA · single GPU

[Kakao의 Kanana-2-v-decide-3b-2611](https://huggingface.co/kakaocorp/kanana-2-v-decide-3b-2611)을 DGX Spark에서 설치하고 실행하는 Docker 레시피입니다. **선택형(`choice`)·예/아니오(`noul`)·척도(`score`) 판정과 확률을 반환하는 모델**이며, 텍스트를 생성하는 채팅 모델이 아닙니다. API는 `/v1/systemone`입니다.

## 원클릭 설치

DGX Spark에서 실행합니다. Docker, NVIDIA Container Toolkit, `git`, `python3`, `nvidia-smi`가 설치되어 있고 현재 사용자가 Docker를 실행할 수 있어야 합니다. 이미지·가중치를 위한 디스크 공간을 확보하세요. 가중치 파일만 약 7.33GB이며 NGC 이미지 공간은 별도입니다.

```bash
curl -fsSL https://raw.githubusercontent.com/yangs1202/Kanana-2-v-decide-3b-2611-dgx-sparks/main/install.sh | bash
```

직접 확인한 후 실행하려면:

```bash
git clone https://github.com/yangs1202/Kanana-2-v-decide-3b-2611-dgx-sparks.git
cd Kanana-2-v-decide-3b-2611-dgx-sparks
./setup.sh
```

`setup.sh`는 **이미지 빌드 → 고정 revision 다운로드·SHA256 검증 → 메모리/포트 확인 → 서버 시작 → smoke test**를 실행합니다. 첫 설치 시 모델과 NGC 이미지 다운로드 시간이 필요합니다. NVIDIA 이미지 이용 조건과 [Kanana 라이선스](docs/KANANA-LICENSE.txt)가 적용됩니다.

- 기본 API: **`http://127.0.0.1:18889`** (localhost 전용, Docker host network)
- 기본 컨테이너: `kanana-dgx-sparks`, 자동 재시작 없음
- 모델·로그: `$HOME/.cache/kanana-dgx-sparks/{model,logs}`
- 시작 전 가용 통합 메모리 **25GiB 이상** 확인
- 실행 중 가용 메모리 **8GiB 미만**이면 이 레시피의 컨테이너만 중지
- 다른 모델·GLM을 자동으로 중단하거나 설정을 바꾸지 않음

25GiB는 측정한 단독 부하 최대 17.12GiB에 여유를 더한 기본 정책입니다. 표본 사이의 급격한 증가나 다른 프로세스의 할당까지 막는 OOM 보장은 아닙니다.

## API 사용

```bash
curl -sS http://127.0.0.1:18889/v1/systemone \
  -H 'Content-Type: application/json' \
  -d '{
    "state": "주문한 상품이 깨져서 도착했습니다. 교환해주세요.",
    "questions": {
      "intent": {
        "type": "choice",
        "instructions": "고객 문의를 분류하세요.",
        "criteria": {"exchange": "상품 교환 요청", "delivery": "배송 문의", "payment": "결제 문의"}
      }
    }
  }'
```

`answers.intent.choice`, `confidence`, `probabilities`와 `usage`를 반환합니다. `output_tokens`는 0입니다. `noul`은 0~1의 수치이며 별도의 probabilities 객체가 없습니다. `score`는 척도별 확률과 점수를 반환합니다. [공식 요청 규격](https://huggingface.co/kakaocorp/kanana-2-v-decide-3b-2611/blob/1489062def4145ae3a0a9261fbac4f4d88a8c6d1/README.md)을 참고하세요.

```bash
./smoke.sh                        # health, models, choice/noul/score 검사
./stop.sh                         # 이 레시피가 소유한 컨테이너만 중지
./start.sh                        # 이미 실행 중이면 재시작 없이 smoke 확인
docker logs -f kanana-dgx-sparks
```

선택지는 캐시되며 공식 서버의 lock을 유지합니다. **HTTP 요청을 동시에 보내도 GPU 추론은 직렬 처리**됩니다. 입력은 최대 20,480토큰, 이미지는 최대 10장입니다. 기본 upstream 설정대로 길이 초과 입력은 잘립니다. 이미지는 base64 data URL로 전달합니다.

## 설정

```bash
cp .env.example .env
# 필요한 값만 .env에서 수정한 후 ./setup.sh 또는 ./start.sh 실행
```

| 변수 | 기본값 | 설명 |
|---|---|---|
| `KANANA_IMAGE` | `kanana-dgx-sparks:2611` | 로컬 빌드 이미지 |
| `KANANA_CONTAINER` | `kanana-dgx-sparks` | 컨테이너 이름 |
| `KANANA_PORT` | `18889` | localhost API 포트 |
| `KANANA_HOME` | `$HOME/.cache/kanana-dgx-sparks` | 데이터·로그 경로 |
| `KANANA_MODEL_DIR` | `$KANANA_HOME/model` | 검증한 모델 디렉터리 |
| `KANANA_MIN_START_GIB` | `25` | 시작 전 MemAvailable 하한 |
| `KANANA_MIN_FREE_GIB` | `8` | 실행 중 MemAvailable 중단 하한 |
| `KANANA_READY_TIMEOUT` | `300` | 준비 완료 대기 시간(초) |
| `DECISION_API_KEY` | 없음 | 설정 시 models/추론에 Bearer 인증 적용 |

`.env`와 모델 파일은 Git에 포함되지 않습니다. 포트나 모델 디렉터리를 바꾸려면 `./stop.sh` 후 설정하고 `./start.sh`를 실행하세요. 원격 접근은 SSH 터널을 사용할 수 있습니다.

```bash
ssh -L 18889:127.0.0.1:18889 USER@SPARK_HOST
# 로컬 PC에서 http://127.0.0.1:18889 사용
```

## 고정 실행 환경

| 항목 | 값 |
|---|---|
| 모델 | `kakaocorp/kanana-2-v-decide-3b-2611` |
| 모델 revision | `1489062def4145ae3a0a9261fbac4f4d88a8c6d1` |
| 가중치 SHA256 | `528930fa261b31ed1f47eecbe7d08efd2e226207508124ae186e1a65dbbbda3b` |
| 기반 이미지 | `nvcr.io/nvidia/pytorch@sha256:2140e699b3beaf7f96a0081fd9c9406bc3832b435cdb60dfa2d261f7d2f34a1c` |
| PyTorch | NVIDIA `2.13.0a0+9186a08b2c.nv26.07` |
| Transformers / Accelerate | `5.5.3` / `1.12.0` |
| 추론 | BF16, SDPA, `device_map='cuda'`, CPU threads 8 |

공식 requirements의 torch 2.10.0/torchvision 0.25.0을 설치하는 대신 NVIDIA 이미지의 GB10 빌드를 유지합니다. 모델의 custom code와 공식 `Decider`/`SystemOneServer`는 고정된 모델 snapshot에서 읽습니다. 레시피 wrapper는 direct CUDA 배치로 로드합니다. 직접 CUDA 로딩도 초기 메모리 피크를 크게 줄이지 못했습니다.

## 실측 벤치마크 — 2026-11-08

모든 자료: **[벤치마크 안내](benchmarks/README.md)** · [상세 보고서](benchmarks/reports/) · [공개 raw](benchmarks/raw/) · [공개 변환 manifest](benchmarks/publication-manifest.json)

### 메모리와 로딩

GB10 통합 메모리에서 `MemAvailable` 감소량입니다. CUDA allocator와 CPU RSS를 단순히 더하지 않습니다. 실험마다 baseline·캐시 정책이 다르므로 각 보고서의 조건을 함께 확인하세요.

| 실험 | 관측 |
|---|---|
| 초기 CPU→CUDA 로딩, 단일 관측 | 53.67초, 추가 시스템 peak **15.42GiB**, 직후 8.69GiB |
| direct CUDA 독립 로딩 3회 | 평균 **49.73초**, peak **15.39 / 14.47 / 14.43GiB** |
| 단독 무거운 HTTP 부하 최대 | 추가 시스템 **17.12GiB** |
| 무거운 부하 후 30초 idle | 추가 시스템 **16.07GiB** 잔류 |
| GLM 512K + Kanana 동시 부하 | Kanana 30 + GLM 202 요청 성공, worker 최소 가용 **5.89GiB** |

기존 1M GLM과 공존이 검증됐다는 의미가 아닙니다. 동시 부하는 GLM context 상한을 **524,288**로 줄인 특정 구성에서 실행했습니다. GLM 최대 길이 요청·C8·장시간 soak는 측정하지 않았습니다. TP2 Kanana 시험은 취소됐으며 이 레시피는 단일 GPU입니다.

### 요청 지연

| 조건 | 단독 평균 HTTP | GLM 동시 부하 평균 HTTP |
|---|---:|---:|
| 짧은 텍스트 C1 | **0.038초** | **0.092초** |
| 20,480-token 텍스트 C1 | 4.665초 | 10.634초 |
| 1280×1280 합성 이미지 10장 C1 | 7.504초 | 22.389초 |
| 긴 텍스트 + 이미지 10장 C6 | 50.239초 | 128.102초 |

각 조건은 3-wave 평균입니다. C6 지연에는 직렬 서버의 대기 시간이 포함됩니다. 이미지 fixture는 합성 난수 이미지이며 이미지 판정 정확도 점수가 아닙니다. 단독과 동시 부하는 난수 생성기까지 같지는 않습니다.

### 2026학년도 수능 국어 — 텍스트 선택형

첨부 문제지의 홀수형·짝수형, 공통과 두 선택과목 모두 평가했습니다. **56개 고유 문항**, 형별 56입력씩 3회, **336/336 성공**, 같은 입력의 3회 답은 모두 동일했습니다. 정답표는 평가원 공식 자료입니다.

| 시험 조합 | 홀수형 원점수 / 정답 수 | 짝수형 원점수 / 정답 수 |
|---|---:|---:|
| 공통 + 화법과 작문 | **54/100 · 25/45** | **56/100 · 26/45** |
| 공통 + 언어와 매체 | **43/100 · 19/45** | **45/100 · 20/45** |

HTTP 평균 **0.309초**, P95 **0.685초**. 이미 로드된 서버와 후보 캐시를 사용했고 warmup은 제외했습니다. 생성 토큰 속도가 아닙니다. 표·화면·옛한글을 텍스트로 전사한 탐색 평가이므로 원본 시각 시험과의 동등성은 보장하지 않습니다. 초기 별도 독해 1번 오답 기록도 함께 공개했습니다. 입력 포맷이 달라진 전체 시험에서는 해당 문항을 맞혔습니다.

## 검증 범위

이 레시피의 ARM64 이미지 빌드·CUDA/GB10 인식·고정 snapshot 다운로드와 해시 검증·가용 메모리 부족 시 시작 거부·실행 중인 모델의 세 판정 API smoke를 확인했습니다. 자세한 결과는 [검증 기록](docs/VALIDATION.md)에 있습니다. 새 이미지의 전체 GPU 재로딩은 운영 모델을 중단하지 않기 위해 재실행하지 않았으며, 기존에 검증한 동일 direct CUDA 로더와 고정 runtime 버전을 사용합니다.

## 출처와 라이선스

- 모델·공식 서버: [Kakao Kanana](https://huggingface.co/kakaocorp/kanana-2-v-decide-3b-2611), [Kanana Open License](docs/KANANA-LICENSE.txt)
- 레시피의 설치 스크립트·wrapper: [MIT](LICENSE). 모델·NGC 이미지·제3자 시험 지문에는 MIT가 적용되지 않습니다.
- 패키징 형식 참고: [MiaAI-Lab DGX Spark recipe](https://github.com/MiaAI-Lab/GLM-5.3-Flash-EXL3-2x-DGX-Sparks). 해당 프로젝트와 제휴한 저장소는 아닙니다.
- 시험 문제·정답: [한국교육과정평가원](https://www.suneung.re.kr/boardCnts/view.do?boardID=1500234&boardSeq=5093801&lev=0&m=0403&s=suneung). 텍스트 전사·채점 입력은 원저작권을 유지하며 평가 재현 자료로 구분합니다.
