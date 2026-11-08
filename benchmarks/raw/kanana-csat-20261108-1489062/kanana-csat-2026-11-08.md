# Kanana 2026학년도 수능 국어 텍스트 선택형 평가

2026-11-08 14:40:08~14:41:52 KST, dgx2에서 운영 중인 Kanana에 첨부 PDF의 모든 문항을 텍스트로 입력했다. 홀수형·짝수형 각각 공통 34문항과 두 선택과목 각 11문항, 총 112개 입력을 C1으로 3회씩 실행했다. 서로 다른 문제는 56개이며 두 형을 독립 문제 112개로 합산하지 않는다.

## 결과

| 영역 | 홀수형 정답 | 홀수형 배점 합계 | 짝수형 정답 | 짝수형 배점 합계 |
|---|---:|---:|---:|---:|
| 공통 | 17/34 | 38/76 | 18/34 | 40/76 |
| 화법과 작문 | 8/11 | 16/24 | 8/11 | 16/24 |
| 언어와 매체 | 2/11 | 5/24 | 2/11 | 5/24 |
| 전체 고유 문항 | 27/56 (48.21%) | — | 28/56 (50.00%) | — |

| 실제 시험 조합 | 홀수형 원점수 | 홀수형 정답 | 짝수형 원점수 | 짝수형 정답 |
|---|---:|---:|---:|---:|
| 공통 + 화법과 작문 | **54/100** | 25/45 | **56/100** | 26/45 |
| 공통 + 언어와 매체 | **43/100** | 19/45 | **45/100** | 20/45 |

원점수이며 표준점수·등급으로 환산하지 않았다. 모든 112개 입력에서 3회 선택이 같았다. 홀수형·짝수형 간 선택한 문장의 내용도 55/56문항에서 같았다. 공통 13번은 홀수형에서 ④(오답), 짝수형에서 ②(정답)로 달라졌다. 해당 문항은 ①·②의 순서가 바뀌므로 선택지 순서에 민감한 사례다.

앞서 별도 수기 전사로 오답을 냈던 공통 1번은 이번 PDF 전사 입력에서는 3회 모두 ③으로 정답이었다. 전사 문구·줄바꿈·지문 포맷이 다른 입력이므로 이전 결과를 같은 입력의 재현 실패로 해석하지 않는다. 이번 평가 도중 정답을 보고 문항을 수정하거나 재시도해 답을 고르지 않았다.

## 속도와 조건

| 항목 | 측정값 |
|---|---:|
| 성공 요청 | 336/336 |
| 전체 HTTP 평균 | 0.3092초 |
| 중앙값 | 0.2712초 |
| P95 | 0.6853초 |
| 최대 | 0.8924초 |
| 1회차 112문항 평균 | 0.4398초 |
| 2회차 112문항 평균 | 0.1662초 |
| 3회차 112문항 평균 | 0.3215초 |
| API 보고 입력 토큰 | 210~2,063 |
| 생성 출력 토큰 | 0 |

대상은 생성형 답안 모델이 아닌 `Decider`의 `choice` 분류다. 지문은 `state`, 문제와 보기는 `instructions`, 다섯 선택지는 `criteria`로 전달했다. 이미 로딩된 서버에 간단한 과일 분류 warmup을 실행해 정답·readiness를 확인하고 시간 통계에서 제외했다. 병렬 요청은 없고 모든 문항을 1회씩 순회하는 과정을 3회 반복했다. 정답률은 첫 회 선택으로 계산하며 반복 횟수로 표본을 늘리지 않았다.

확률 temperature는 서버 기본값 1.0이며 생성 sampler의 temperature=0과 같은 개념이 아니다. 후보 임베딩 캐시가 기존 서버와 회차·형 간 재사용되므로 cold-start 성능이 아니다. 캐시 때문에 API의 input_tokens도 회차별로 달라질 수 있다. 같은 서버의 기존 캐시를 지우거나 모델을 재시작하지 않았다. GLM은 계속 운영 중이었으며 별도 GLM 부하는 만들지 않았다. 세 회차 지연 차이는 관측값이며 원인을 특정하지 않는다. 일반 생성형 모델용 fixed-output/TTFT/tok/s와 직접 비교하지 않는다.

## 입력과 채점

- 사용자 제공 40쪽 PDF에서 두 단을 각각 추출했다. 모든 문항의 5개 선택지를 검증했고, 선택지 번호가 뒤에 인쇄된 16번은 별도로 파싱했다.
- 그래프·블로그·댓글·카드 뉴스·화상 회의 화면·옛한글을 원본 이미지와 대조해 텍스트로 전사했다. 이미지 데이터는 Kanana에 보내지 않았다.
- 입력에는 정답표를 포함하지 않았다. 정답표는 준비·채점 단계에서만 사용했고 추론 단계는 `cases.json`만 읽었다.
- [평가원 기출문제 게시글](https://www.suneung.re.kr/boardCnts/view.do?boardID=1500234&boardSeq=5093801&lev=0&m=0403&s=suneung)의 [공식 정답표](https://www.suneung.re.kr/boardCnts/fileDown.do?fileSeq=46c7d36aa9208016099f9a4cf2e7cc2a)에서 두 형의 정답·배점을 추출했다. 선택과목별 시험 배점 합계 100점을 검증했다.
- 모든 응답의 선택지 집합, 유한 확률, 확률 합계, 입력 길이 상한을 확인했다. 보고 입력은 최대 2,063토큰으로 서버 상한 20,480보다 작았다.

이 결과는 수기 보완한 텍스트 전사본에 대한 탐색 평가다. 시각 배치·밑줄·구간 표시·옛한글을 원본과 완전히 동등하게 전달했다고 보장할 수 없다. 특히 언어와 매체의 옛한글·화면 자료를 포함한 결과를 원본 PDF를 직접 보는 시험 점수와 동일시하지 않는다. 학습 데이터의 시험 포함 여부도 확인하지 않았다. 이 조건에서는 빠르게 선택하지만 수능 국어 문제 해결의 정확도는 낮았다.

## 실행 환경과 종료 검증

- 모델: `kakaocorp/kanana-2-v-decide-3b-2611`, commit `1489062def4145ae3a0a9261fbac4f4d88a8c6d1`.
- 노드: dgx2 (`internal.example.invalid`), NVIDIA GB10, BF16, SDPA, direct CUDA, 단일 GPU.
- runtime: `kanana-memory:20261108-direct-accelerate112`, local image ID `sha256:349154e3f5a2cf08d1971453a9ed568f3ceed703e74569540ba7d9eafc44f2c5`.
- PyTorch `2.13.0a0+9186a08b2c.nv26.07`, transformers `5.5.3`, accelerate `1.12.0`. 공식 모델 의존성의 PyTorch 2.10.0과 다른 기존 실험 이미지다.
- GLM recipe commit `13f2464ee84ab2b5dabf0bb264d1144b02cf5fb7`, 두 노드의 `glm53-spark`를 유지했다.
- 요청 직전 샘플의 dgx2 최소 MemAvailable **6.785GiB**. 이는 연속 샘플링으로 측정한 메모리 피크가 아니다. 종료 후 약 **7.08GiB** 가용.
- 종료 후 Kanana ready, GLM health ok/warming=false, 양쪽 GLM과 Kanana 모두 running/restart=0/OOMKilled=false.
- 실행 전후를 포함하는 05:38 UTC 이후 두 노드의 커널 OOM/Xid와 대상 컨테이너 CUDA/NCCL error·out-of-memory·Traceback 로그에서 일치 항목이 없었다.
- LiteLLM `/health/readiness` HTTP 200, healthy/db connected. 이번 추론은 Kanana direct API를 사용했으며 proxy 경유 Kanana 추론은 측정하지 않았다.

## 재현과 보존

스크립트 `hw/dgx/kanana-csat-bench.py`, 시각 자료 전사 `hw/dgx/kanana-csat-supplements-2026-11-08.json`, 문항별 채점 `hw/dgx/kanana-csat-graded-2026-11-08.json`, 요약 `hw/dgx/kanana-csat-summary-2026-11-08.json`.

raw 보존 경로:

- dgx2: `/home/USER/kanana-csat-20261108-1489062/`
- dgx1: `/home/USER/ds4/results/kanana-csat-20261108-1489062/`

각 경로에 실제 요청 `cases.json`, 정답표 원본·추출본, 입력 PDF SHA256, warmup, 실행 로그, 336개 응답 `results.jsonl`, 회차별 `kanana-csat-20261108-1489062-run-{1,2,3}.jsonl`, 문항별 JSON/CSV, 요약을 보존한다.

Notion 상세 결과 (private workspace reference omitted), 공통 벤치마크 DB 행 (private workspace reference omitted).

```sh
python3 hw/dgx/kanana-csat-bench.py prepare --root /tmp/csat --pdf INPUT.pdf --supplements hw/dgx/kanana-csat-supplements-2026-11-08.json
# dgx2 로컬 서버에서 실행한다. 기존 results.jsonl을 덮어쓰므로 재실행 시 새 root 사용.
python3 kanana-csat-bench.py run --root /path/to/new-run
python3 kanana-csat-bench.py grade --root /path/to/new-run
```
