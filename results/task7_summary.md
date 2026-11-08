# Task 7 Summary (Measured, Standard Locust Run: 4 users, 2 min, 2 replicas)

**Student:** Thirumalasetty Karthik (Roll 230101007)

| Measure | Value |
|---|---|
| Requests / Failures | 342 / 2 (0.58% error rate) |
| p50 / p95 Latency | 1250 ms / 2700 ms |
| Throughput | 2.85 req/s |
| CPU per Pod (kubectl top) | 1928m and 1915m (limit 2000m) |
| Memory per Pod | 742 MiB and 758 MiB (limit 1 GiB) |
| Replica split | 172 / 168 (50.6% / 49.4%) |
| Cold start (median of 3) | 7.1 s |

Cost: (2 x 3.50 + 1 x 0.45) = 7.45 INR/replica/h; 2 replicas = 14.90 INR/h; 2.85 x 3600 = 10260 req/h; cost per 1000 requests = (14.90 / 10260) x 1000 = 1.45 INR.  
SLO: 99% of requests succeed per run. Budget 3.42 requests; used 2 (58.5%).

| Component | Evidence (measured) | Limitation | Improvement |
|---|---|---|---|
| Data and storage | Model download of 7 files from SeaweedFS at each start | Single-node object storage, no replication | Replicated storage, model cached on persistent volume |
| Model quality | 2 of 342 outputs rejected as invalid (0.58%) | 70M student makes format and slot errors | More distillation data, constrained decoding |
| Latency and throughput | p50 1250 ms, p95 2700 ms, 2.85 req/s | CPU-bound; thread contention occurred prior to clamping OMP/MKL | Quantised model, continuous batching |
| Resource utilisation | CPU 1928m of 2000m, memory 758 MiB of 1 GiB | Pods saturated at 4 users | Smaller model, more replicas on multi-node cluster |
| Reliability and recovery | Cold start median 7.1 s; replicas split 50.6/49.4 | Single-node k3d cluster; HPA bounded by 2 replicas | Multi-node cluster, higher HPA maximum, PodDisruptionBudget |
| Security and cost | Credentials from Secret s3-creds; 1.45 INR per 1000 reqs | Secret only base64; no TLS on Ingress | Sealed secrets/Vault, automated TLS via cert-manager |

## Recovery & Autoscaling Observations
* **Pod Recovery (deleted under load)**: 450 requests, 4 failures (0.89%), all transient HTTP 500. Replacement Pod Ready in 17.5 s.
* **HPA scale up**: 1 to 2 replicas when aggregate CPU exceeded 195% against 70% target.
* **HPA scale down**: 2 to 1 replica approximately 5 minutes after load ended.
