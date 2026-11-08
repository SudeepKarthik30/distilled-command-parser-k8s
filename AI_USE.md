# Record of AI Tool Utilization & Verification

**Student:** Thirumalasetty Karthik  
**Roll Number:** 230101007  
**Course:** Cloud Computing Mini Project  

---

## 1. AI Platforms Employed
* **Antigravity (Gemini 3.8 Flash)**: Interactive pair programming, code refactoring, infrastructure debugging, and artifact compilation.
* **Anthropic Claude**: Architecture conceptualization, troubleshooting Kubernetes readiness probes, and mathematical validation of CIDR calculations.

---

## 2. Scope of AI Assistance
* **Task Decomposition & Architecture**: Assisting with decomposing the multi-tier assignment into discrete operational milestones (knowledge distillation, containerization, SeaweedFS bootstrapping, and traffic evaluation).
* **Code Modernization & Refactoring**:
  * Transitioning `service/app.py` from legacy `@app.on_event` startup hooks to FastAPI's async `lifespan` manager with Pydantic request models.
  * Modularizing `worker/clean.py` into distinct validation passes for JSON integrity, intent domains, and slot boundary checks.
* **Networking & NACL Validation**:
  * Calculating VLSM subnet partition boundaries for `10.20.0.0/16`.
  * Simulating packet traversal with custom rule sequences using `tools/nacl_sim.py`.
* **Troubleshooting & Performance Tuning**:
  * Diagnosing latency degradation under CPU constraints by constraining OpenMP and MKL thread pools (`OMP_NUM_THREADS=1`, `MKL_NUM_THREADS=1`) to avoid multi-thread contention on CPU-limited containers.
  * Formulating accurate unit economics formulas using the cost rate card.

---

## 3. Human Verification & Quality Assurance Methodology
* **Direct Execution & Measurement**: Every terminal command, shell pipeline, and manifest was executed locally within PowerShell and WSL, with output inspected directly prior to inclusion.
* **Automated Test Validation**: 
  * Tested Network Access Control List rules against `network/packets_sample.jsonl` using `tools/nacl_sim.py` (achieved 6/6, 100% test accuracy).
  * Validated schema conformity and accuracy using `tools/score.py` against `data/validation.jsonl`.
  * Ran Locust benchmarking with concurrent simulated users to verify p50 and p95 latencies in real time.
* **Dataset Integrity**: Teacher distillation prompts were generated exclusively via Phi-3.5 on Ollama and parsed programmatically; no training responses were fabricated or manually hallucinated.

---

## 4. Identified AI Inaccuracies & Corrections
1. **Makefile Execution Precedence**: An early AI suggestion placed `train` as the initial rule, which caused a bare `make` invocation to launch hours of model fine-tuning instead of deploying the cluster. I corrected the Makefile by defining explicit `.PHONY` targets and ordering `up: cluster storage app` with a default `all: up` target.
2. **Kubernetes Lifespan Handshake**: The model suggested an asynchronous model loading inside FastAPI's startup event that initially caused race conditions where Kubernetes readiness probes passed before weights were loaded from SeaweedFS. I updated `service/app.py` so `/readyz` strictly returns HTTP 503 until the model loading thread signals completion.
3. **CIDR Boundary Edge Cases**: AI originally proposed allocating the management subnet before the data subnet; I corrected the allocation sequence to adhere strictly to descending order of host requirements (1,000 -> 250 -> 100 -> 20), avoiding fragmentation of the `10.20.0.0/16` block.
