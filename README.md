# Kanana-2-v-decide-3b-2611 for DGX Spark

**English** | [한국어](README.ko.md)

**Powered by Kanana** · NVIDIA GB10 / Linux aarch64 · BF16 / SDPA · single GPU

A Docker recipe for running [Kakao's Kanana-2-v-decide-3b-2611](https://huggingface.co/kakaocorp/kanana-2-v-decide-3b-2611) on NVIDIA DGX Spark. This model returns **decisions and probabilities for multiple choice (`choice`), yes/no (`noul`), and rating (`score`) tasks**. It does not generate chat responses. Its API endpoint is `/v1/systemone`.

## One-command installation

Run on a DGX Spark with Docker, NVIDIA Container Toolkit, `git`, `python3`, and `nvidia-smi` installed. Your user must be able to run Docker. Allow disk space for the NGC image and model weights; the weights alone occupy approximately 7.33GB.

```bash
curl -fsSL https://raw.githubusercontent.com/yangs1202/Kanana-2-v-decide-3b-2611-dgx-sparks/main/install.sh | bash
```

To inspect the recipe before running it:

```bash
git clone https://github.com/yangs1202/Kanana-2-v-decide-3b-2611-dgx-sparks.git
cd Kanana-2-v-decide-3b-2611-dgx-sparks
./setup.sh
```

`setup.sh` performs **image build → pinned snapshot download and SHA256 verification → memory/port checks → server startup → smoke test**. The first installation downloads the model and NGC image. NVIDIA image terms and the [Kanana license](docs/KANANA-LICENSE.txt) apply.

- Default API: **`http://127.0.0.1:18889`**, localhost only, using Docker host networking.
- Default container: `kanana-dgx-sparks`, with no automatic restart.
- Model and logs: `$HOME/.cache/kanana-dgx-sparks/{model,logs}`.
- Requires at least **25GiB of available unified memory** before starting.
- Stops only the recipe's container if available memory falls below **8GiB** during execution.
- Does not automatically stop or reconfigure GLM or other models.

The 25GiB startup threshold adds headroom to the measured 17.12GiB maximum additional system memory under standalone load. It cannot guarantee protection against OOM caused by rapid allocation between samples or other processes.

## API usage

```bash
curl -sS http://127.0.0.1:18889/v1/systemone \
  -H 'Content-Type: application/json' \
  -d '{
    "state": "My order arrived damaged. Please send a replacement.",
    "questions": {
      "intent": {
        "type": "choice",
        "instructions": "Classify the customer request.",
        "criteria": {"exchange": "Product replacement", "delivery": "Delivery inquiry", "payment": "Payment inquiry"}
      }
    }
  }'
```

The response includes `answers.intent.choice`, `confidence`, `probabilities`, and `usage`. `output_tokens` is 0. A `noul` answer is a value between 0 and 1 without a separate probabilities object. A `score` answer includes a rating and probabilities for the scale. See the [official request specification](https://huggingface.co/kakaocorp/kanana-2-v-decide-3b-2611/blob/1489062def4145ae3a0a9261fbac4f4d88a8c6d1/README.md).

```bash
./smoke.sh                        # Check health, models, and choice/noul/score
./stop.sh                         # Stop only the container owned by this recipe
./start.sh                        # If already running, smoke-test without restarting
docker logs -f kanana-dgx-sparks
```

Candidates are cached, and the official server lock is retained. **Concurrent HTTP requests still execute GPU inference serially.** Inputs support up to 20,480 tokens and 10 images. Oversized inputs are truncated according to upstream defaults. Supply images as base64 data URLs.

## Configuration

```bash
cp .env.example .env
# Edit the required values, then run ./setup.sh or ./start.sh
```

| Variable | Default | Description |
|---|---|---|
| `KANANA_IMAGE` | `kanana-dgx-sparks:2611` | Locally built image |
| `KANANA_CONTAINER` | `kanana-dgx-sparks` | Container name |
| `KANANA_PORT` | `18889` | Localhost API port |
| `KANANA_HOME` | `$HOME/.cache/kanana-dgx-sparks` | Data and log directory |
| `KANANA_MODEL_DIR` | `$KANANA_HOME/model` | Verified model directory |
| `KANANA_MIN_START_GIB` | `25` | Minimum startup MemAvailable |
| `KANANA_MIN_FREE_GIB` | `8` | Runtime MemAvailable stop threshold |
| `KANANA_READY_TIMEOUT` | `300` | Readiness timeout in seconds |
| `DECISION_API_KEY` | Unset | Enables Bearer authentication for models/inference |

`.env` and model files are excluded from Git. To change the port or model directory, run `./stop.sh`, update the configuration, then run `./start.sh`. For remote access, use an SSH tunnel:

```bash
ssh -L 18889:127.0.0.1:18889 USER@SPARK_HOST
# Access http://127.0.0.1:18889 from your local computer
```

## Pinned runtime

| Component | Value |
|---|---|
| Model | `kakaocorp/kanana-2-v-decide-3b-2611` |
| Model revision | `1489062def4145ae3a0a9261fbac4f4d88a8c6d1` |
| Weights SHA256 | `528930fa261b31ed1f47eecbe7d08efd2e226207508124ae186e1a65dbbbda3b` |
| Base image | `nvcr.io/nvidia/pytorch@sha256:2140e699b3beaf7f96a0081fd9c9406bc3832b435cdb60dfa2d261f7d2f34a1c` |
| PyTorch | NVIDIA `2.13.0a0+9186a08b2c.nv26.07` |
| Transformers / Accelerate | `5.5.3` / `1.12.0` |
| Inference | BF16, SDPA, `device_map='cuda'`, 8 CPU threads |

The recipe retains the NVIDIA image's GB10 build instead of installing the upstream requirements' torch 2.10.0/torchvision 0.25.0. Model custom code and the official `Decider`/`SystemOneServer` are loaded from the pinned snapshot. The wrapper loads directly onto CUDA. Direct CUDA loading did not substantially reduce the initial memory peak.

## Measured benchmarks — 2026-11-08

All records: **[Benchmark guide](benchmarks/README.md)** · [Detailed reports](benchmarks/reports/) · [Published raw data](benchmarks/raw/) · [Publication manifest](benchmarks/publication-manifest.json). Detailed reports are currently in Korean.

### Memory and loading

Memory figures represent the decrease in system `MemAvailable` on GB10 unified memory, rather than adding CUDA allocator usage to CPU RSS. Baselines and cache policies differ between experiments; consult the individual reports.

| Experiment | Observation |
|---|---|
| Initial CPU→CUDA load, single observation | 53.67s; additional system peak **15.42GiB**, 8.69GiB immediately afterward |
| Three independent direct CUDA loads | Mean **49.73s**; peaks **15.39 / 14.47 / 14.43GiB** |
| Maximum under heavy standalone HTTP load | **17.12GiB** additional system memory |
| After 30 seconds idle following heavy load | **16.07GiB** additional system memory retained |
| GLM 512K + Kanana concurrent load | 30 Kanana + 202 GLM requests succeeded; worker minimum available memory **5.89GiB** |

These results do not establish coexistence with the previous 1M GLM configuration. Concurrent load used a specific GLM configuration with its context limit reduced to **524,288**. Maximum-length GLM requests, C8, and prolonged soak testing were not measured. The Kanana TP2 experiment was canceled; this recipe uses one GPU.

### Request latency

| Condition | Standalone mean HTTP latency | Mean HTTP latency with GLM load |
|---|---:|---:|
| Short text, C1 | **0.038s** | **0.092s** |
| 20,480-token text, C1 | 4.665s | 10.634s |
| Ten 1280×1280 synthetic images, C1 | 7.504s | 22.389s |
| Long text + ten images, C6 | 50.239s | 128.102s |

Each condition is a three-wave average. C6 latency includes queueing at the serial server. Images are synthetic random fixtures, so these measurements do not assess image decision accuracy. The standalone and concurrent-load fixtures also use different random generators.

### 2026 Korean CSAT language exam — text multiple choice

The supplied exam covered odd and even forms, the common section, and both electives: **56 unique questions**, 56 inputs per form over three runs, **336/336 successful requests**. All three predictions for each input were identical. Grading used the official KICE answer key.

| Exam combination | Odd form: raw score / correct answers | Even form: raw score / correct answers |
|---|---:|---:|
| Common + Speech and Writing | **54/100 · 25/45** | **56/100 · 26/45** |
| Common + Language and Media | **43/100 · 19/45** | **45/100 · 20/45** |

Mean HTTP latency was **0.309s**, P95 **0.685s**, using an already loaded server and candidate caching, excluding warmup. This is not token generation throughput. Tables, screen layouts, and historical Korean text were transcribed into text for an exploratory evaluation; equivalence to the original visual exam is not guaranteed. The earlier standalone reading-question failure is also published. The full-exam run answered that question correctly with a different input format.

## Validation scope

Verified: ARM64 image build, CUDA/GB10 detection, pinned snapshot download and hash validation, startup rejection with insufficient available memory, and smoke tests for all three decision APIs on the running model. See [validation records](docs/VALIDATION.md). A full GPU reload with the new image was not repeated to avoid interrupting production models. The recipe uses the same previously verified direct CUDA loader and pinned runtime versions.

## Credits and licenses

- Model and official server: [Kakao Kanana](https://huggingface.co/kakaocorp/kanana-2-v-decide-3b-2611), [Kanana Open License](docs/KANANA-LICENSE.txt).
- Recipe installation scripts and wrapper: [MIT](LICENSE). MIT does not cover model weights, NGC images, or third-party exam passages.
- Packaging format reference: [MiaAI-Lab DGX Spark recipe](https://github.com/MiaAI-Lab/GLM-5.3-Flash-EXL3-2x-DGX-Sparks). This repository is not affiliated with that project.
- Exam questions and answer key: [Korea Institute for Curriculum and Evaluation](https://www.suneung.re.kr/boardCnts/view.do?boardID=1500234&boardSeq=5093801&lev=0&m=0403&s=suneung). Transcribed exam inputs retain their original copyright and are provided as evaluation reproduction materials.
