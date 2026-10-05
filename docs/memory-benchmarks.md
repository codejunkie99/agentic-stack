# Production memory retrieval benchmark

`python3 scripts/benchmark-memory.py` exercises the real `ContextPacks.prepare`, `MemorySources`, `KnowledgeGraph`, and `MemoryLedger` against an isolated temporary store. It never discovers personal conversations or opens the user's workspace database. This is a retrieval benchmark, not an answer-generation or coding-success benchmark. **99.9% is an aspirational target; these runs do not establish it.**

The LongMemEval adapter follows the [official dataset format](https://github.com/xiaowu0162/LongMemEval#-dataset-format). The cleaned S corpus includes distractor histories. Oracle includes only evidence sessions and must be reported separately as an optimistic retrieval diagnostic. Each supplied query gets its own scoped history store.

Before ingestion, the adapter separates the query/history input from answer text, `has_answer`, and `answer_session_ids` labels. Input validation rejects unexpected fields. History is inserted through production ledger APIs with an explicit benchmark-only acceptance policy. This does not test the quality of extraction, consolidation or automatic review. Turns above 10,000 characters become exact contiguous chunks; all chunks retain the original turn and session identity. Duplicate session IDs in the public S corpus get occurrence-specific turn IDs. The original IDs remain the session-recall identity.

The fixed split is `sha256-id-v1-dev20`: SHA-256 of question ID modulo five assigns zero to dev and everything else to held-out. On these 500-case files that gives 98 dev / 402 held-out questions. Reordering the dataset or changing answers cannot change assignments. Keep held-out results out of retrieval tuning; hash fingerprints and exact split IDs let a reviewer reject mismatched comparisons.

Metrics have distinct meanings:

- `turn_source_recall`: fraction of labeled answer-bearing turn IDs represented among returned refs. A bounded excerpt can omit the useful part of a retrieved turn.
- `session_recall`: fraction of labeled evidence sessions represented by returned refs.
- `exact_span_recall`: fraction of separate `{evidence_id, text}` gold spans appearing verbatim in returned excerpts. It is null for LongMemEval, which supplies turn labels rather than exact answer spans. Spans crossing ingestion chunk boundaries may be missed.
- `answer_accuracy`: always null. No generator or official answer judge ran. Abstention questions have no retrieval location; they are retained as cases but contribute no gold location denominator. Empty refs are not evidence of a correct abstention response.
- Integrity errors: excerpt differs from its exact source slice or digest differs from the full source body's SHA-256. Source identity and exact answer correctness are separate checks.

Failures are retained, with safe exception type/stage rather than raw exception text. Ingestion failures contribute zero retrieval hits while retaining their gold denominator. No report emits query, evidence or answer text. Reports include raw per-sample wall-clock milliseconds, case/repeat/phase, actual cache hits, status, provider label, configuration, architecture/CPU/RAM where discoverable, Python version and production source fingerprints. Missing metadata or scores stays null.

Cold is a fresh `ContextPacks` instance with an already ingested corpus, **not** a flushed OS or SQLite cache. Warm is the next identical request on that instance. Latency covers the whole production `prepare` call using `perf_counter_ns`, includes unsuccessful retrieval attempts, and excludes corpus ingestion. Three repeats give 1,206 cold and 1,206 warm samples for 402 cases. p50/p95 use nearest rank. Quality uses only the first cold sample per case. Baseline and change should run serially on the same machine; background workload remains a limitation, and overlapping runs must not support speedup claims.

## Reproduce

Download the public cleaned files explicitly, outside the repository:

```sh
curl -L --fail https://huggingface.co/datasets/xiaowu0162/longmemeval-cleaned/resolve/main/longmemeval_s_cleaned.json -o /tmp/longmemeval_s_cleaned.json
curl -L --fail https://huggingface.co/datasets/xiaowu0162/longmemeval-cleaned/resolve/main/longmemeval_oracle.json -o /tmp/longmemeval_oracle.json
python3 scripts/benchmark-memory.py --longmemeval /tmp/longmemeval_s_cleaned.json --split held-out --repeats 3 --output /tmp/baseline.json
# After making the change, with exactly the same corpus/labels/split:
python3 scripts/benchmark-memory.py --longmemeval /tmp/longmemeval_s_cleaned.json --split held-out --repeats 3 --baseline /tmp/baseline.json --output /tmp/comparison.json
python3 -m pytest tests/test_memory_benchmark.py -q
```

For a sanitized custom dataset, provide separate `--inputs inputs.json --gold gold.json`. Input rows contain `id`, `query`, `evidence` (`id`, `body`, optional `session_id`, `status`) and optional category/date. Gold is a dictionary keyed by question ID with `evidence_ids`, `session_ids`, optional `answer`, `abstention`, and `evidence_spans`. An answer label is never a retrieval input.

Default execution is offline and does not load provider settings. `--variant jev` without a configured provider reports unavailability honestly. A live public evaluation requires **all** of `--public-live-jev --provider-root <explicit-config-root> --longmemeval <public-file> --variant jev`; custom/private input mode cannot enable the live CLI path. This flag is authorization to send the supplied public corpus, not evidence that arbitrary user-supplied files are public. Do not use private files with it. Hosted fallback/unavailability must stay visible in report status/provider fields.

## Other relevant benchmarks

[VibeMemBench](https://arxiv.org/abs/2609.23570) measures executable repository task resolution under declared memory conditions: 111 targets, 90 repositories and 3,634 history trajectories. Applying it requires repository task environments, held-out solver configuration and test execution with matched memory-off controls. Source recall alone cannot establish a coding benefit. The paper reports eleven of twelve retrieved-memory system/solver pairings failed to improve the matched memory-off baseline.

[MemCalib](https://arxiv.org/abs/2609.24259) measures whether a model gives memories an appropriate influence, including over-use and under-use. It requires generated responses and the benchmark's calibration evaluation; returning a relevant source is insufficient.

[DolphinBench](https://arxiv.org/abs/2609.24971) evaluates task completion on three knowledge-work personas with approximately 500k history tokens per persona and 200 tasks each, requiring cost and latency alongside accuracy. The [official site](https://dolphinbench.ai) is linked by the paper as the dataset/evaluation source. Applying it requires an action-capable task agent and its execution/evaluation environment. This retrieval harness does not execute those workflows or establish their task-success scores.

These three September 2026 papers address complementary downstream capabilities; none of their published scores is a score for this repository.

## Recorded runs, 2026-10-05

The machine reports Darwin 25.6.0, arm64, Apple M5 (Mac17,2), 10 logical CPUs, 16 GiB RAM, Python 3.14.6. Hardware model/RAM/CPU were obtained with an authorized read-only `sysctl` query because they were unavailable inside the sandbox. Other background application activity was uncontrolled. Full S baseline and v1 retrieval runs were sequential. Oracle v1 overlapped full S ingestion, so its latency is diagnostic and supports no speedup claim.

| Corpus/version | Turn/source recall | Session recall | Cold p50/p95 ms | Warm p50/p95 ms | Failed cases |
| --- | ---: | ---: | ---: | ---: | ---: |
| S cleaned baseline | 26/727 (3.576%) | 30/726 (4.132%) | 18.57 / 26.63 | 14.25 / 20.95 | 3/402 |
| S cleaned v1 exact windows | 26/727 (3.576%) | 30/726 (4.132%) | 20.15 / 28.14 | 12.14 / 17.25 | 3/402 |
| Oracle baseline | 552/727 (75.928%) | 627/726 (86.364%) | 5.60 / 9.82 | 4.42 / 6.84 | 0/402 |
| Oracle v1 exact windows | 555/727 (76.341%) | 627/726 (86.364%) | 6.60 / 11.46 | 4.14 / 6.31 | 0/402 |

S has 1,197 timed samples of 1,206 requested in each phase; the nine missing timings per phase come from three rejected corpora repeated three times. Production secret detection rejected credential-like text in those public histories. The harness preserves the rejection and zero-hit gold denominator instead of stripping text or weakening the production safeguard. Oracle has 1,206 timings per phase. Every recorded run has zero source integrity errors. Exact-span recall and answer accuracy are unmeasured. The first improvement did not improve full S recall.

There are 23 held-out abstention cases. The initial baseline runs counted their location annotations, then the official retrieval protocol was checked and those location counts were removed from stored samples. Retrieval outputs/timings and all non-abstention scores are unchanged. Reports preserve the original gold fingerprint and this scoring adjustment in `scoring_provenance`; final comparisons use the corrected common gold fingerprint. Abstention answer correctness remains unmeasured.

Dataset SHA-256:

- S cleaned: `d6f21ea9d60a0d56f34a05b609c79c88a451d2ae03597821ea3d5a9678c3a442`
- Oracle: `821a2034d219ab45846873dd14c14f12cfe7776e73527a483f9dac095d38620c`

Sanitized reports retain all case IDs and timing samples, full input/gold hashes, exact split IDs and production source fingerprints: [S baseline](benchmarks/results/longmemeval-s-baseline.json), [S v1](benchmarks/results/longmemeval-s-v1.json), [oracle baseline](benchmarks/results/longmemeval-oracle-baseline.json), [oracle v1](benchmarks/results/longmemeval-oracle-v1.json). Source files were snapshotted before each production revision; baseline/context-pack fingerprint is `69d7702f5c49ba526fb11306eff510ffc0ae9e24beaa2a7d7815c88b32733939`, baseline/memory-source fingerprint is `77892d5573f723e18b0323c1e8d79057344d2fcfcbeb833f81cff7f2a6c8f39f`. The complete changed fingerprints are in each report.

The full S gap and missing answer-generation/calibration/task-completion evaluation prevent a 99.9% claim. These runs also ingest raw conversation turns as benchmark-approved ledger records; a complete memory-system evaluation must additionally measure extraction, consolidation, review and downstream answering.
