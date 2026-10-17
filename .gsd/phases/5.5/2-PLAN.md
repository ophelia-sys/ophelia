---
phase: 5.5
plan: 2
wave: 2
depends_on: [5.5.1]
---

# Plan 5.5.2: PyTorch Thread-Count & Forecast Batching Benchmarks

## Objective
Benchmark TimesFM CPU inference under 1, 2, 3, and 4 PyTorch threads, and compare serial vs batched inference across realistic multi-instrument workloads, verifying numerical forecast equivalence.

## Context
- [.gsd/SPEC.md](file:///c:/Users/dopa.mine/Desktop/ophelia/.gsd/SPEC.md)
- [PROJECT_RULES.md](file:///c:/Users/dopa.mine/Desktop/ophelia/PROJECT_RULES.md)
- [control_plane/forecast_service.py](file:///c:/Users/dopa.mine/Desktop/ophelia/control_plane/forecast_service.py)

## Tasks

<task type="auto">
  <name>PyTorch Thread-Count Benchmark</name>
  <files>scratch/vps_phase55_threads.py</files>
  <action>
    Benchmark TimesFM CPU inference on VPS across thread counts:
    - 1 thread (`torch.set_num_threads(1)`)
    - 2 threads (`torch.set_num_threads(2)`)
    - 3 threads (`torch.set_num_threads(3)`)
    - 4 threads (`torch.set_num_threads(4)`)
    Record for each: p50 latency, p95 latency, peak CPU %, avg CPU %, RAM, swap activity, and critical service latency.
    Verify numerical equivalence of outputs across all configurations using np.allclose against single-thread baseline.
  </action>
  <verify>python scratch/vps_phase55_threads.py</verify>
  <done>Thread benchmark produces comparative latency/CPU/RAM metrics and proves numerical forecast equivalence across all thread counts.</done>
</task>

<task type="auto">
  <name>Forecast Batching Benchmark</name>
  <files>scratch/vps_phase55_batching.py</files>
  <action>
    Compare realistic TimesFM workloads on VPS:
    - Workload A: 5 individual serial inference calls (batch size 1)
    - Workload B: Batch size 2
    - Workload C: Batch size 3
    - Workload D: Batch size 5
    Record: total wall time, total CPU time, CPU peak %, RAM peak MB, per-series latency, throughput (series/sec), and forecast numerical correctness.
  </action>
  <verify>python scratch/vps_phase55_batching.py</verify>
  <done>Batching benchmark provides empirical wall time and throughput curve to determine optimal multi-symbol inference strategy.</done>
</task>

## Success Criteria
- [ ] PyTorch thread counts (1..4) benchmarked with proven numerical equivalence
- [ ] Batch sizes (1, 2, 3, 5) evaluated with measured memory and throughput tradeoffs
