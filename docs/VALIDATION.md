# 레시피 검증 — 2026-11-08

## 실제 DGX Spark에서 확인

| 항목 | 결과 |
|---|---|
| Docker ARM64 이미지 빌드 | 통과 |
| `torch.cuda.is_available()` | true |
| CUDA 장치 | NVIDIA GB10 |
| PyTorch / Transformers / Accelerate | `2.13.0a0+9186a08b2c.nv26.07` / `5.5.3` / `1.12.0` |
| 기반 NGC 이미지 | README의 고정 digest 사용 |
| 모델 snapshot 다운로드 | 고정 revision의 20개 파일 확인, 기존 동일 snapshot 파일 재사용 |
| 가중치 전체 SHA256 | README의 `528930fa…da3b`와 일치 |
| 시작 전 메모리 부족 검사 | 실제 MemAvailable 19.24GiB < 기본 25GiB: 시작 거부 |
| 운영 중인 Kanana의 health/models | 통과 |
| 신규 smoke client의 choice/noul/score | 통과, [실제 응답](validation/live-api-smoke.json) |
| 기존 양쪽 GLM과 worker Kanana | running, restart=0, OOMKilled=false 유지 |

최종 검증 빌드 이미지 ID는 `sha256:78176d792a50a1293460038bd7f3007236900b891bad24e2cdd8a104a6052a5d`이다. 기존 벤치마크의 local image ID `349154e3…`와 혼동하지 않는다. 로컬 빌드 ID는 NGC registry digest와도 다르다.

다운로드 검증은 기존 모델 폴더를 마운트한 실제 Docker 실행으로 수행했다. 인터넷에서 모든 가중치 바이트를 처음 받는 cold 다운로드 시간은 측정하지 않았다. 모델 가중치는 재로딩하지 않았으며 실제 판정 smoke는 운영 중인 서버에 요청했다. 새 이미지 전체 GPU 로딩·최종 localhost 기동은 운영 모델을 중단하지 않기 위해 재실행하지 않았다. 동일 snapshot/BF16/SDPA/direct CUDA 방식의 실제 로딩·추론 결과는 벤치마크 아카이브에 별도로 보존되어 있다.

## 로컬·CI 검사

- 모든 shell 스크립트 `bash -n`과 Python compile 검사.
- 공개 raw 267개의 SHA256과 manifest 일치 검사.
- 저장된 336개 응답을 재채점해 원본 summary와 전체 항목 일치 검사.
- 외부 컨테이너 소유권: start/stop에서 종료·삭제·생성을 호출하지 않음.
- 부족한 메모리: 시작 거부.
- 메모리 하한 guard: 지정된 label의 해당 컨테이너만 stop 호출.
- 공개 파일에서 인증키 패턴·내부 주소·사용자 경로 검사.

```bash
for script in *.sh scripts/*.sh benchmarks/*.sh; do bash -n "$script"; done
python3 -m compileall -q scripts benchmarks/scripts tests
python3 tests/check_artifacts.py
python3 -m unittest discover -s tests -v
```

GitHub Actions는 GPU 없는 runner에서 위 문법·자료·보호 로직을 검사한다. Actions 통과를 DGX GPU 실행 성공으로 표시하지 않는다.
