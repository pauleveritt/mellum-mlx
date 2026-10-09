# Mellum Core AI and caix staged implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans for native implementation, or superpowers:subagent-driven-development if the user explicitly selects delegation. Steps use checkbox syntax for tracking. This plan is research-first: later implementation choices are conditional on the early experiment results.

**Goal:** Prove the reusable Mellum Core AI and caix work now, inspect the forthcoming MTP head before freezing the graph interface or running a full export, then qualify a faithful 50k-context deployment within the target 16 GB memory budget.

**Architecture:** Author Mellum from the original safetensors using Core AI GPU primitives, retaining distinct sliding/full cache states and positional encodings. Keep ordinary autoregressive execution as the correctness baseline; use small probes to establish MTP's target/head interface and transactional cache behavior when its reference implementation arrives. Freeze the export interface after that evidence, then integrate the proved route into caix and benchmark it against MLX.

**Tech Stack:** Pinned Apple Core AI runtime/export packages, PyTorch/Transformers oracle, the model-zoo overlay and Metal kernels, Swift caix, and the existing MLX-LM baseline.

**Spec:** [Research brief and proposed design constraints](../../research/2026-10-07-mellum-coreai.md).

## Revision and immediate scope

**2026-10-07 update:** The user reports that Mellum's MTP head is expected in the next few days. Availability, head architecture, target revision, and reference decoding algorithm have not been independently confirmed. The current checkpoint still has no MTP weights. This revision adopts the agreed approach: continue inexpensive reusable work now, and hold the full-model export until the release has been inspected and the interface decision recorded.

| Work | When it can proceed |
| --- | --- |
| Source/environment checks, cache/YaRN/MoE/prompt probes | Now, using the pinned target checkpoint |
| Four-layer real-weight authoring and small diagnostic exports | After the existing primitive gates pass; interfaces remain provisional |
| Synthetic speculative rollback tests | Now, with deterministic draft fixtures and no claim about Mellum's actual head |
| Actual head authoring and reference-acceptance tests | After a published compatible head and decoding reference are available |
| Final graph interface and full-model export | After Stage 2.5's decision is recorded |
| MTP production enablement | Only after correctness, supported sampling, actual speed, and memory gates pass |

Head arrival does not by itself require stopping the port or enabling acceleration. If it is late, continue the independent probes; leave the full export gate pending. Calendar time is not evidence that an unavailable contract is safe to guess.

## Global constraints

- Source: `JetBrains/Mellum2.1-12B-A2.5B-Thinking` revision `6f239041e7c79166f75f6788dbf7d1971fe1db89`; original BF16 safetensors, not GGUF or an already quantized conversion.
- Preserve 28 layers, 21 sliding / 7 full, sliding window 1,024, 32 Q heads / 4 KV heads, head dimension 128, 64 experts / top eight, and untied 98,304-token embedding/head.
- Preserve per-type RoPE, YaRN factor 16 and attention factor `1.2772588722239782`, head-sized Q/K RMSNorm, router softmax/renormalization, tokenizer IDs, and chat-template behavior.
- Initial deployment scope: macOS GPU, one resident Mellum model, one generation at a time, ordinary autoregressive decoding as the required baseline. MTP contract discovery precedes full export; enabling MTP is conditional on its own gates.
- Working target assumption: 16 GB total unified memory; 50,000 total tokens including generated reasoning/output. Confirm these in Stage 0. Allocate capacity for the entire admitted request, not just its prompt.
- Keep the existing Python `>=3.14`, MLX converter, lockfile, and user edits intact. Give incompatible Core AI export dependencies their own environment/module rather than changing the MLX environment to accommodate them.
- Before any Python toolchain execution, follow `python-tools` and obtain the configured PyCharm environment for the file/module. Before long builds/exports use `command-monitor`; serialize heavy GPU jobs. Apply PyCharm inspections after inspectable code edits.
- Pin caix, Apple, zoo, runtime-wheel, tokenizer, and oracle revisions; record installed OS/SDK builds. Do not mix overlays or Swift patches from unrelated revisions without an explicit experiment.
- Store large weights, graph assets, transcripts, and reference tensors outside Git. Preserve source bundles; export into new directories. Keep scripts, manifests, small fixtures, and reports reviewable in the repo.
- No unverified MTP/EAGLE, prefix reuse, KV quantization, ANE tuning, concurrent inference, or full-131k performance claim. A served autoregressive model remains a valid first milestone after MTP interface discovery.
- Do not freeze extra target outputs, draft count, head functions, cache ownership, acceptance algorithm, or sampling restrictions before reading the released Mellum reference. No head tensors or draft architecture may be invented to fill missing release evidence.

## Review focus

1. Window boundaries and multi-token prefill: writing a ring block must not evict keys still needed by its earlier queries; check every query and subsequent layers.
2. Long absolute positions: ring indices must not reset RoPE, and YaRN behavior beyond 8,192 must match the pinned reference.
3. Rich chat history: assistant reasoning/tool calls, consecutive tool results, thinking options, and Unicode/numeric tokenization must survive both APIs.
4. Request lifetime and speculation: cancellation, rejected capacity, partial draft acceptance, and a following request must not expose stale state, overwrite committed ring history, or allocate a full-context sliding cache.
5. Precision/performance interaction: low-bit experts, shape specialization, separate graph assets, and trace-width prefill must not conceal quality regressions or duplicate resident weights.

Each concern has experiments below. Do not infer a pass from fluent text or a small fixed-length smoke test.

## File and artifact map

These are proposed files for execution, not files created by this planning task. Begin with focused experiment scripts; promote proved code into the reusable port only after the feasibility decision.

| Location | Responsibility |
| --- | --- |
| `experiments/coreai/source_inventory.py` | Header-only source inventory, provenance, exact parameter/layout checks |
| `experiments/coreai/probe_runtime.py` | Tiny graph export/load, mutation, specialization, and caix ABI experiments |
| `experiments/coreai/probe_cache.py` | Sliding/full cache reference, wrap/chunk/multi-layer comparisons |
| `experiments/coreai/probe_rope.py` | Mellum default/YaRN and Q/K norm parity at selected positions |
| `experiments/coreai/probe_moe.py` | Selected-expert, quantized-kernel, decode and batched-prefill comparisons |
| `experiments/coreai/mtp_inventory.py` | Released head/target compatibility, required hidden-state outputs, functions, and decoding-reference manifest |
| `experiments/coreai/probe_speculation.py` | Synthetic accept/reject transactions and, after release, head/reference comparisons |
| `experiments/coreai/prompt_fixtures.py` | Reference Jinja prompts, token IDs, rich history and parser fixtures |
| `experiments/coreai/gate_model.py` | Layer/logit comparisons and teacher-forced/free-running transcripts |
| `experiments/coreai/benchmark.py` | Reproducible memory, load, prefill, decode, and endpoint measurements |
| `coreai_port/config.py`, `weights.py` | Checkpoint interpretation, strict original-to-authored weight mapping |
| `coreai_port/model.py`, `cache.py` | Faithful Mellum graph and proved cache update/masking |
| `coreai_port/speculation.py` | Proved cache checkpoint/restore/replay; promote only after the speculation probe passes |
| `coreai_port/mtp.py` | Conditional authored head from the actual published contract; never scaffold a guessed model |
| `coreai_port/export.py`, `bundle.py` | Separate conversion entry point, compression recipe, packaging and provenance |
| `tests/coreai/` | Small meaningful numerical/contract regression tests; Core AI environment only |
| External pinned caix checkout | Mellum routing, cache allocation/lifecycle, rich prompts, API option support |
| External work directory | Checkouts, environments, `.aimodel`, reference NPZs, and measured run directories |
| `docs/research/2026-10-07-mellum-coreai.md` | Design/evidence baseline; append corrections or decisions with dates |

Every probe takes an explicit output directory and writes a JSON report with `status`, exact versions, input case IDs, metrics, mismatches, and artifact paths. Use `PASS`, `FAIL`, or `BLOCKED` rather than treating a skipped runtime check as passing. Later stages consume the reports and fixtures, not prose claims.

## Stage 0: Reproduce the research and define the target

**Outcome:** A locked source/runtime manifest and an executable experiment environment. No full-model export.

**Files:** Create `experiments/coreai/source_inventory.py`; create an environment/revision manifest under the external work directory; retain a small copy of the resulting inventory in `docs/research/`.

**Inputs:** The research brief, existing `main.py` source validator, local source snapshot, host/toolchain information.  
**Outputs:** `source_manifest.json`, `environment.json`, `target.json`; these become required provenance for every later run.

- [ ] Confirm target machine, whether 16 GB is total unified memory, and whether 50k includes output. Record a representative output/reasoning allowance so admission tests can separate prompt and generation limits.
- [x] Reproduce the header inventory without loading tensors: five valid shards, 5,631 indexed tensors, 12,149,923,072 parameters, all expected shapes/dtypes, complete index-to-header mapping, no unexpected MTP sidecar. Record source file hashes and total sizes. Evidence: [Stage 0 source manifest](../../research/coreai-stage0/source_manifest.json). The audit ran with an external Node script; reusable Python inventory implementation remains pending.
- [x] Record all layer types, MLP types, RoPE parameters, norm/activation settings, tokenizer IDs, template bytes, and generation config. Fail the inventory if this source differs from the research baseline rather than silently applying a Mellum2.1 label. Evidence: [Stage 0 model contract](../../research/coreai-stage0/model_contract.json); source settings and bytes verified, rendered-prompt and numerical parity remain later gates.
- [ ] Save the existing MLX environment/version baseline. Record the exact Transformers Mellum reference used for oracle generation; its packed expert layout differs from the checkpoint's per-expert files, so prove the loader's mapping explicitly.
- [ ] Create isolated pinned Apple/zoo/caix checkouts. First try caix's specified Apple revision with minimal authored code. If zoo additions require its different base, use a separate export environment and make compatibility an experiment. Apply overlays only to their declared base.
- [ ] Check Core AI Python export/runtime imports and Swift framework linking with a tiny example. Investigate the missing `coreai-build` utility without assuming AOT is necessary or changing Xcode globally. Record which full/direct caix build modes are available.
- [ ] Freeze the experiment matrix and proposed quality/performance criteria below; keep all heavy jobs serialized and large artifacts out of the workspace's tracked tree.

**Exit gate:** Valid source inventory and at least one tiny Python-to-Core-AI-to-Swift runtime path. If exports/runtime cannot work with a coherent pinned stack, report the compatibility issue and stop before model authoring.

## Stage 1: Confirmation experiments with tiny graphs

Run in this order so a runtime/ABI failure is found before expensive work. Each experiment is independently reviewable and ends in a report. Tests should first expose the relevant wrong implementation, then pass with the proved one; avoid mocks that merely repeat the implementation.

### 1A. Four mutable states and caix routing

**Files:** `probe_runtime.py`, `tests/coreai/test_runtime_contract.py`; a throwaway Swift runner and caix checkout patch if required.  
**Consumes:** Stage 0 manifests.  
**Produces:** `runtime_report.json` and `bundle_contract.json` with function names, input/state/output names, dtypes, shapes, dynamic axes, positional contract, and selected engine.

- [ ] Export a tiny deterministic graph with separate sliding K/V and full K/V, mutate all four states, invoke repeatedly, and verify that updates persist and reset correctly. Use tiny layer/head sizes before testing Mellum-sized descriptors without model weights.
- [ ] Load it in Python and a minimal Swift N-state runner. Compare output/state bytes against the tensor reference for two calls, a reset, and a new request. Test FP16 first, then BF16 if the selected GPU path supports it.
- [ ] Test one graph versus matched `prefill`/`decode` functions. Verify compatible descriptors, a shared state history, and documented position inputs. Trace at a nonzero past offset so query length and absolute history are not accidentally tied together.
- [ ] Package a tiny `kind=llm` fixture with tokenizer files and function mapping, then attempt caix's default, legacy, and direct routes where supported. Record actual selected engines and precise rejection points; do not count listing in `/v1/models` as an inference pass.
- [ ] If four-state binding fails, make the smallest throwaway caix direct-runner adaptation that binds the declared states. Keep semantic names; never disguise sliding KV as conv/recurrent state or allocate all 28 layers at full capacity.
- [ ] Test a request reset and two sequential HTTP requests. Prove that the second matches an independently fresh reference.

**Exit gate:** Python, Swift, and at least a minimally adapted caix route give the same tiny outputs/state evolution. Adopt the four-state ABI unless another measured layout preserves its memory bounds with less integration cost. Record whether multiple functions share weights or require duplicated graph assets.

### 1B. Sliding cache, window masks, and chunk prefill

**Files:** `probe_cache.py`, `tests/coreai/test_cache_parity.py`.  
**Consumes:** Stage 1A state/position contract.  
**Produces:** `cache_report.json` and reference input/output fixtures, including expected failures of the naive ring update.

- [ ] Build an explicit full-history sliding-attention reference. Define validity using the reference's exact window convention; for W=4, query 4 sees keys 1..4.
- [ ] Reproduce the W=4, cached 0..3, new 4..5 failure for write-whole-chunk-then-attend. This negative control must fail for query 4 even if a final-query-only check passes.
- [ ] Establish S=1 ring decode equivalence through several wraps using W=4/8. Repeat with W=1,024 at offsets 0, 1, 1,023, 1,024, 1,025, 2,047, and 2,048.
- [ ] For chunk sizes 2, 16, 64, 256, 1,024, and 1,025, compare every query output at aligned and unaligned offsets. Any unsupported shape must be rejected or split explicitly rather than silently producing an approximate result.
- [ ] Implement correct chunk attention over the retained W-1 prior keys plus current keys, then commit the tail. Start with chronological concatenation for clarity; optimize the representation only after parity. Export this path to verify its slices, masks, and mutable writes survive lowering.
- [ ] Compare chunked prefill, one-token prefill, and full-reference prefill followed by decode in a four-layer sliding/sliding/sliding/full stack. This catches hidden-state error propagation missed by checking one layer's final query.
- [ ] Measure persistent allocation at capacities 4k, 16k, and 50k: sliding residency must remain bounded; only full states grow. Record temporary prefill memory separately.

**Exit gate:** No missing/duplicate/stale keys, exact logical position masks, and all-query/multi-layer parity for each admitted chunk size. S=1 is a diagnostic fallback, not a 50k performance solution.

### 1C. RoPE, YaRN, GQA, and norm parity

**Files:** `probe_rope.py`, `tests/coreai/test_rope_attention_parity.py`.  
**Consumes:** The pinned Mellum config/reference and Stage 1B positions.  
**Produces:** `rope_report.json` containing reference frequency/scaling arrays and positional comparisons.

- [ ] Compare default and Apple YaRN primitives with Mellum's reference at positions 0, 1, 1,023, 1,024, 8,191, 8,192, 16,383, 49,999, and 131,071. Use sparse selected positions for this small experiment, not 131k-token prefill.
- [ ] Verify inverse frequencies, half-split rotation, and scaling for both Q and K, including the explicit attention factor. Add a small Mellum adapter only if the measured primitive differs.
- [ ] Test head-sized Q/K norm before RoPE, FP32 reductions, RMS epsilon `1e-6`, attention scale `128**-0.5`, and eight query heads per KV head with real Mellum dimensions.
- [ ] Use normalized and large-amplitude inputs to expose FP16 overflow/precision loss. Compare FP32/BF16/FP16 reference envelopes; do not choose FP16 solely because another model used it.
- [ ] Negative controls: omit Q/K norm, substitute default RoPE for full layers, use ring slot as the position, and infer head dimension as hidden/heads. Each must be detected by the fixtures.

**Exit gate:** Positional/norm/GQA equivalence in eager FP32 and the exported precision envelope. Proposed eager-module bar: cosine at least 0.99999 and max absolute error at most `1e-4` on fixed normalized fixtures. Report any failure and its cause; never relax a bar merely to pass it.

### 1D. MoE routing, selected-expert kernels, and batching

**Files:** `probe_moe.py`, `tests/coreai/test_moe_parity.py`.  
**Consumes:** Original first-layer weights, pinned routing reference, zoo `moe_metal.py`.  
**Produces:** `moe_report.json` with quality, timing, allocation, expert selection, and supported shapes for each scheme.

- [ ] Load only one real layer's experts/router initially. Map individual up/gate/down weights into the authored layout; verify shape and expert order. Account for this layer's roughly 0.40B parameters before loading FP32 copies.
- [ ] Compare a simple selected-expert reference with the Core AI primitive at 64 experts, top eight, hidden 2,304, intermediate 896, SiLU, FP32 softmax across all experts, and normalized top-k weights.
- [ ] Compare the zoo's `sym8` and `aff4` kernel to an eager reference using the same packed/dequantized weights. Separately compare each quantized reference to original BF16/FP32. Conversion error and quantization loss must be reported separately.
- [ ] Verify tensor dimensions, packing/group sizes, router/combine dtypes, and activation semantics. Preserve router/norm precision initially. Negative controls must detect expert permutation, swapped gate/up matrices, and missing top-k normalization.
- [ ] Measure S=1 decode and S=16/64/256 prefill with both ordinary batched operations and `BatchedMetalSwitchGLU`. Confirm the batched export runs on the actual OS; a decode-only matvec is not the prefill solution.
- [ ] Record the actual sparse-kernel gain rather than extrapolating another model's reported speed. Inspect whether expert over-read reproduces here.

**Exit gate:** Routing agrees away from documented numeric ties; selected expert outputs match the same-quantization reference within the measured GPU envelope. At least one compressed candidate is stable enough to warrant full-model evaluation. Keep a stock-operation baseline even if the custom kernel wins.

### 1E. Prompt and API fidelity without a full model

**Files:** `prompt_fixtures.py`, `tests/coreai/test_prompt_fixtures.py`; caix Swift fixture tests in its pinned checkout.  
**Consumes:** Source template/tokenizer and caix API/normalizer implementation.  
**Produces:** `prompt_cases.json`, expected rendered bytes/token IDs, and `prompt_report.json` for both HTTP dialects.

- [ ] Render in the pinned Transformers/Jinja reference: simple chat, system plus user, multiple prior turns, active tool interaction with reasoning, assistant tool calls as object/string arguments, consecutive tool results, text content blocks, and thinking enabled/disabled.
- [ ] Include Unicode identifiers, whitespace-sensitive Python, individual digits, JSON escapes, and missing/empty optional fields. Use token IDs as the contract, not just readable strings.
- [ ] Render the same rich objects in Swift. Check that a separate `chat_template.jinja` is found when the tokenizer config has no embedded template; compare the exact generated prompt IDs and EOS behavior.
- [ ] Inject deterministic raw outputs into caix's normalizer. Split every thinking/tool delimiter at every character boundary and test streaming/non-streaming equivalence, multiple tool calls, incomplete spans, EOS, stop reasons, and usage accounting.
- [ ] Demonstrate current generic-path loss of `tool_calls`/`reasoning_content` and `chat_template_context` with fixtures, then prototype a rich Mellum prompt route. Confirm `enable_thinking=false` reaches rendering; do not yet claim the model is equally capable in that mode.
- [ ] Inspect and test accepted temperature/top-k/top-p parameters on the selected engine, using fixed logits and seeds. Demonstrate or fix the fast-path `topP:nil` discrepancy for the Mellum route. Reject explicitly any unsupported options.

**Exit gate:** Exact reference token IDs for all prompt cases and correct normalized API responses. A detected Qwen-like output family is insufficient unless the input-history and parameter checks also pass.

### Stage 1 decision

Write a short dated decision containing the proved ABI, runtime revisions, compute/cache dtype, prefill algorithm, expert implementation, and prompt path. List remaining failures explicitly. Choose among:

- **Proceed:** primitives work and the caix changes are bounded; use a Mellum direct route initially, retaining the server's existing API/model-management shell.
- **Revise:** an existing staged caix route or different pinned environment demonstrably reduces integration cost; update the ABI/plan before a full export.
- **Stop:** runtime incompatibility, numerical mismatch, or a memory/latency bottleneck has no credible solution in scope; retain MLX and publish the experiment evidence.

The direct route is the working recommendation, not a pre-approved bypass of failed experiments.

## Stage 2: Faithful authored model with real four-layer weights

**Outcome:** A reusable model implementation and strict loader, proved before all-layer export.

**Files:** `coreai_port/config.py`, `weights.py`, `model.py`, `cache.py`; `gate_model.py`; `tests/coreai/test_weights.py`, `test_model_parity.py`.  
**Consumes:** Stage 1 decision/fixtures.  
**Produces:** A four-layer authored model, strict mapping inventory, and `authoring_report.json`.

- [ ] Implement config interpretation and original checkpoint mapping. Test an exact first-four-layer selection, expert ordering, untied embedding/head, missing tensor, wrong shape, and unexpected live tensor. Derived RoPE buffers must be initialized explicitly; no uninitialized `to_empty()` constants.
- [ ] Implement the proved 3:1 attention pattern, head normalization, positional encoding, sparse experts, residual/norm order, and ordinary output head. Reuse zoo/Apple primitives selectively; omit Gemma-only KV sharing, per-layer embeddings, softcaps, extra norms, and Qwen recurrent-state machinery.
- [ ] Build a four-layer HF reference with the same real layer weights. Capture embedding, each layer, routing choices/weights, final norm, and logits with fixed token IDs and teacher forcing. Use at least one prompt crossing 1,024 and selected high absolute positions.
- [ ] Run authoring parity in FP32 first, then candidate compute precision. Add negative-control tests for the concrete failure modes from Stage 1.
- [ ] Export the four-layer graph, invoke it through Python and Swift, and reproduce the chunk-prefill plus decode transcript. Check every relevant layer/query, not only the output token.

**Exit gate:** Zero missing/unexpected live weights, correct derived buffers, and no unexplained numerical/routing divergence. Proposed exported-logit bar: cosine at least 0.999 on fixed teacher-forced cases plus identical greedy choices for clear-margin cases; log near-tie flips and the baseline precision envelope. This is a conversion gate, not yet a quantization-quality gate.

## Stage 2.5: Inspect MTP and prove speculative state before full export

**Outcome:** A measured MTP interface decision and safe accepted-prefix recovery. This stage is a mandatory decision gate before Stage 3, not a promise to ship MTP immediately.

### Task 2.5A: Capture the released head's real contract

**Files:** Create `experiments/coreai/mtp_inventory.py`; create `tests/coreai/test_mtp_inventory.py`; retain a small `mtp_contract.json` and dated decision in `docs/research/`.  
**Consumes:** Source/environment manifests, published head files/card, and the authoritative decoding reference.  
**Produces:** `mtp_contract.json` with `status`, head source/revision/hashes, compatible target source/revision, tokenizer relationship, required target outputs, entry points, state ownership, draft limits, acceptance rules, precision, sampling restrictions, and unresolved evidence. Use `BLOCKED` when release evidence is missing; do not guess required fields.

- [ ] Before release, write fixture tests that reject missing target provenance, wrong tensor shapes, incompatible vocabulary/token IDs, unknown required target outputs, and unsupported decoding modes. This testable manifest validation can proceed without head weights.
- [ ] After release, pin and inventory the head's real files, card, tensor shapes, configuration, tokenizer assumptions, and license. Determine whether this is a separate sidecar, appended target layers, or another arrangement from the files/reference, not its marketing name.
- [ ] Establish whether it uses this exact target checkpoint, a compatible documented revision, or updated base weights. If the base/config/tokenizer changes, keep both snapshots and repeat the affected Stage 0/1/2 gates before reusing parity evidence.
- [ ] Read the reference draft/verify/accept/correction loop. Record each target hidden-state dependency, normalization/projection, special position input, head state, supported proposal length, EOS handling, and acceptance/sampling policy.
- [ ] Compare those requirements to caix's EAGLE/MTP contracts and the zoo's speculative exporters. Adopt a path only where interfaces and algorithms actually match; reuse framework patterns otherwise.
- [ ] Determine whether additional hidden-state outputs or a separate verification function are needed. Use a small four-layer diagnostic export to measure output transfer and graph/state compatibility; preserve shared target weights wherever supported.
- [ ] Validate the manifest against the original head/reference load on a short fixed-input case. Missing reference behavior is a documented blocker, not permission to infer a lossless algorithm.

**Exit gate:** A reproducible, compatible head/reference contract or an explicit incompatibility report. No full-model export while head availability or required target interfaces remain unknown.

### Task 2.5B: Establish cache transactions independently of head quality

**Files:** Create `experiments/coreai/probe_speculation.py`, `tests/coreai/test_speculative_cache.py`; promote proved code into `coreai_port/speculation.py` after the probe.  
**Consumes:** Stage 1 cache/position contract and deterministic draft fixtures; actual head/reference contract is needed only for the subsequent Mellum algorithm gate.  
**Produces:** `speculation_report.json` recording draft proposals, accepted counts, correction tokens, emitted history, target-processed history, draft-processed history, positions, cache checks, and committed outputs. `draft_count`, `accepted_count`, and processed offsets must be separate fields.

- [ ] Write a regression test that demonstrates why full-cache truncation alone fails. With W=4 and committed positions 0..3, speculative writes 4..5 followed by total rejection must restore all four original ring positions and their post-RoPE K/V values.
- [ ] Use these initial test assertions for the tiny fixture: after rollback, `ring_positions == [0, 1, 2, 3]`, sliding K/V equal the pre-verification snapshot, and full-cache active length equals 4. After replaying accepted position 4, logical retained sliding positions equal `[1, 2, 3, 4]` and full-cache active length equals 5. Physical ring order may differ; assert the logical position/value mapping.
- [ ] Implement the conservative baseline: snapshot committed sliding states and all other reference-required mutable state before verification; on rejection restore, reset the full-cache cursor, and replay the accepted prefix through the proved target path. Mask all inactive full-cache tails. Restore/rebuild the head state according to its actual reference.
- [ ] Track separately what was emitted and what each model has processed. At a chosen stable comparison boundary, process pending correction/bonus tokens as the reference requires before comparing to a fresh autoregressive replay. Do not assume an emitted token is already in either cache.
- [ ] Parameterize synthetic proposals of length 1, 2, and 4, with every accepted prefix from 0 through K. Include first/middle/last rejection, all accepted with a bonus token if the algorithm uses one, and zero remaining output capacity. Actual head tests use only its supported draft counts.
- [ ] Repeat at W=1,024 with committed lengths 1,023, 1,024, 1,025, and 2,047. Verify logical sliding contents, active full contents, absolute positions, next-step logits, and subsequent generation against fresh reference replay. Include multi-layer verification, not just cache arrays.
- [ ] Cover EOS within proposals, output exhaustion, cancellation during draft/verification, capacity exhaustion near 50k, failed verification, and the following fresh request. No rejected or unverified draft token may reach the client stream or committed usage count.
- [ ] Once the reference is available, compare the actual greedy acceptance/correction loop against ordinary autoregressive generation for fixed prompts. Require identical committed tokens and correct EOS/limits, with near-tie numerical differences investigated rather than hidden.
- [ ] Run the small transaction through Python Core AI, the Swift runner, and the proposed caix route. Verify that restoring state does not invalidate model handles or require recompilation per rollback.
- [ ] Measure checkpoint/restore/replay time and allocation. The target's full sliding snapshot is about 42 MiB at 16-bit KV, independent of T; head states, verification scratch, and head weights are additional measured costs. Optimize to a slot journal only if the baseline is correct and rollback cost is material.

**Verification:** In the configured Core AI experiment environment, run `pytest tests/coreai/test_speculative_cache.py -v`; every synthetic transaction and replay comparison must pass. Run `probe_speculation.py` with the fixed fixture/output directory and require `status=PASS` with zero unexplained mismatches. The script must also emit the expected failure of the cursor-only negative control. Add actual-head test cases only after Task 2.5A declares a supported contract.

**Exit gate:** Restored/replayed committed state matches the fresh target reference for every accepted-prefix case, and no speculative token leaks through streaming. A synthetic pass proves transaction mechanics, not compatibility or speed of Mellum's unreleased head.

### Task 2.5C: Freeze the interface and decide acceleration scope

**Files:** A dated MTP decision in `docs/research/`; update the export contract and later recipes from measured requirements.  
**Consumes:** Stage 2.5A contract, Stage 2.5B reports, and Stage 2 model parity.  
**Produces:** `export_contract.json` declaring the target functions/outputs, state layouts, compatible head revision, enabled modes, and the chosen initial acceleration policy.

- [ ] Record one of three evidence-backed decisions: shared target plus separate compatible head; an integrated/multi-function export required by the reference; or an explicitly autoregressive initial release after MTP inspection shows an unsupported contract.
- [ ] Retain autoregressive generation as an independent mode and oracle. Do not make a valid base-model port depend on successful head quantization or a speculative speed win.
- [ ] If greedy MTP is correct, carry it to later performance qualification. If sampling is restricted to greedy, keep sampled requests on the faithful autoregressive path until the reference-compatible stochastic acceptance algorithm is implemented and tested.
- [ ] If actual MTP correctness remains unresolved, hold MTP enablement. A baseline-only export may proceed only after its interface choice is justified by the released contract and the unresolved acceleration work is recorded. Do not silently skip unavailable-head inspection because a few days elapsed.
- [ ] Update Stage 3/4/5 bundle and runtime requirements; then proceed to full export. Review the small contract/transaction results before spending the full-model conversion cost.

**Exit gate:** The released head has been inspected, speculative recovery has a passing synthetic baseline, and the final target interface and initial acceleration scope are explicit. This is the point where the expensive artifact work resumes.

## Stage 3: Full-model oracle and export on the build host

**Outcome:** A correct 28-layer baseline artifact with reproducible provenance.

**Files:** `coreai_port/export.py`, `bundle.py`; `gate_model.py`; `tests/coreai/test_bundle_contract.py`; a small conversion recipe manifest.  
**Consumes:** Stage 2 model/source manifest and Stage 2.5's export contract and decision.  
**Produces:** Baseline `.aimodel`, tokenizer/metadata bundle, pinned oracle transcripts, full binding and parity reports.

- [ ] Freeze an evaluation set: 20 small coding tasks with executable expected results, 8 rich tool/reasoning conversations, and 8 long-context retrieval cases with facts at beginning/middle/end. Keep correctness controls and performance cases separate.
- [ ] On the 128 GB host, create original BF16/FP32 oracle results without unnecessarily retaining all long-context logits. Store input IDs, per-step selected logits/metrics, generated tokens, and revision hashes. Use only last-token logits where that preserves the test.
- [ ] Load all 28 layers and verify all 5,631 source tensors are accounted for. Export a high-precision diagnostic baseline if it fits the build host; otherwise use a proved eight-bit baseline and disclose the distinct reference precision.
- [ ] Package source template/tokenizer/generation files and metadata with model type, source revision, context cap, precision, cache ABI, supported entry points, selected engine, and compression recipe. Include head provenance, compatibility, required target outputs, and acceleration restrictions only where qualified. Keep logical context 131,072 separate from the initially qualified runtime cap of 4,096.
- [ ] Test structural load, teacher-forced logits, multi-step greedy generation, chunk equivalence, EOS, fresh-request reset, and repeated deterministic runs at 4k. Gate against the same-precision authored reference before comparing quality to original Mellum.
- [ ] Measure cold specialization, warm reload, post-restart reload, and model residency. If prefill/decode are separate assets, measure weight duplication and state transfer explicitly; prefer a shared-weights multi-function artifact where supported.
- [ ] Re-run packaging verification independently from numerical parity. Adapt the zoo's gate for Mellum rather than passing an unrelated `--arch` value.
- [ ] If Stage 2.5 selected actual MTP, first preserve the ordinary autoregressive parity artifact, then export the head/verification functions under the recorded contract and compare committed greedy sequences to that artifact. This includes a rejected proposal crossing the sliding-window boundary.

**Exit gate:** Full-layer binding and conversion parity at 4k, coherent task outputs matching the reference's capability envelope, and valid caix bundle metadata. No 50k or 16 GB claim yet.

## Stage 4: Quantization and useful long prefill

**Outcome:** A measured quality/memory/performance frontier and a deployable candidate, or a justified stop.

**Files:** Compression recipes consumed by `export.py`; `benchmark.py`; meaningful quantization/cache regression fixtures.  
**Consumes:** Stage 3 oracle/artifact and Stage 1 expert/prefill implementations.  
**Produces:** Per-candidate quality reports, memory profiles, and an explicit selected recipe.

- [ ] Compare the supported all-weight four-bit baseline, selected-expert `aff4`, and mixed expert-four-bit/non-expert-eight-or-16-bit candidates. Use `sym8` as a diagnostic quality/performance baseline. Do not advertise six-bit Core AI or newer FP4/FP8/KV presets until they are proved on the chosen stack.
- [ ] For each candidate, first compare Core AI to its identically quantized eager reference, then compare quality to original Mellum and the existing six-bit MLX option. Report teacher-forced loss, clear-margin argmax changes, coding test outcomes, tool structure, and examples of any changed behavior.
- [ ] Proposed initial quality gate: no gross corruption/non-finite logits, no systematic malformed tools or tokenizer drift, coding outcomes within one solved task of the original reference on the frozen 20-case set, and mean teacher-forced NLL increase at most 0.1 nat/token on the frozen representative corpus. Treat this as a project acceptance proposal, not a benchmark claim or proof of universal equivalence.
- [ ] Benchmark prefill at 1k, 4k, 8k, 16k, 32k, and 50k with candidate chunks 16/64/256/1,024 and their admitted boundary-splitting policy. Compare ordinary batched experts and the batched custom kernel; include S=1 only as the correctness baseline.
- [ ] At each supported length, follow prefill with generation and retrieval tests. Repeat selected cases with different chunk schedules; long-context cache allocation alone is not a pass.
- [ ] Record wall time, prompt tokens/s, first streamed token, first final-answer token, decode tokens/s, CPU/process memory, available unified memory, accelerator allocation when observable, and compilation-cache growth. Process RSS alone does not establish GPU or system memory headroom.
- [ ] If native SDPA fails for Mellum's actual 32-query-head, 128-head-dimension shapes, reproduce it in a small case first. Evaluate the zoo's custom attention kernels only after reproducing a failure or measured bottleneck; Gemma's different head geometry is not proof that Mellum needs one.
- [ ] Select the simplest candidate satisfying quality/memory with useful prefill. Use the matched MLX baseline as a decision comparator. If Core AI is substantially slower, document whether caix's deployment convenience is enough value to continue; do not claim an acceleration advantage.
- [ ] If MTP is qualified, compare identical target quantization with MTP off/on at fixed prompts/output counts. Include head weight/state residency, the roughly 42 MiB sliding checkpoint, verification scratch, rejection/replay costs, acceptance rate, and total wall time. Evaluate head quantization separately from the target; a low acceptance rate is a performance result, not justification to alter acceptance correctness.

**Exit gate:** A candidate preserving bounded sliding memory and quality at 50k, with measured prefill suitable for the agreed workload. If the candidate only works at shorter context or on 128 GB, label that limit and stop short of the target claim.

## Stage 5: Production caix integration

**Outcome:** A faithful served Mellum, including tool round trips and reasoning.

**Files in the pinned external caix checkout:** `Sources/PipelineRuntime/MellumEngine.swift`, `MellumPrompt.swift`; targeted changes in `BundleManifest.swift`, `PersistentModel.swift` or `CoreAIServer/ModelManager.swift`; tests in `Tests/PipelineRuntimeTests/` and `Tests/CoreAIServerTests/`. Use the Stage 1 decision to avoid introducing a second route if the staged route already proves preferable.  
**Consumes:** Stage 4 candidate and exact prompt/state/option contracts.  
**Produces:** Reviewable caix patch, model bundle, and OpenAI/Anthropic integration transcripts.

- [ ] Route explicitly by a Mellum bundle capability/model-type declaration, with descriptor validation at load time. Define required names, shapes, dtypes, positional contract, function mapping, and supported context. Reject mismatched bundles before allocating state.
- [ ] Bind separate sliding/full states and proved prefill/decode logic; keep graph/tokenizer hot, serialize generation, and reset request state. Add capacity checks for prompt plus max output before admission.
- [ ] Carry rich message objects and template context to rendering. Preserve assistant `tool_calls`, current reasoning, grouped tool results, `enable_thinking`, and the source template's handling of earlier reasoning.
- [ ] Honor temperature/top-k/top-p on this route using the tested sampler. Either support or explicitly reject constrained JSON, acceleration flags, and other accepted options; do not inherit silent no-ops from the generic fast route.
- [ ] Test `/v1/models`, OpenAI `/v1/chat/completions`, and Anthropic `/v1/messages`, streaming and non-streaming. Replay the frozen prompt cases and compare prompt IDs to the reference. Complete two consecutive tool-call/result turns without losing structured history.
- [ ] Test cancellation during prefill/reasoning/tool output, output-token limits, over-capacity prompts, load/unload/reload, and the following fresh request. Check resets, released per-request scratch, accounting, and useful errors.
- [ ] Verify packaging/discovery from the normal caix exports directory and dashboard. Disable unrelated model prewarming/residency during constrained-memory qualification. Document ordinary autoregressive support, qualified MTP modes if any, and unsupported ANE/prefix-reuse capabilities clearly.
- [ ] If MTP is enabled, stream only committed tokens; expose explicit acceleration selection and restrictions. Test rejected drafts, EOS, cancellation, output limits, and a next request through both APIs. Auto selection must use the measured capability and preserve sampled-request semantics via autoregressive fallback where required.

**Exit gate:** Both APIs preserve reference prompts/options/output structure, numerical generation is consistent with the local runner, and request-lifetime tests pass. The server must not require manual environment workarounds that alter model semantics.

## Stage 6: Qualify the actual target and decide what to ship

**Outcome:** Evidence for the requested 16 GB / 50k configuration, or a precise smaller supported configuration.

**Files:** Reproducible benchmark recipe and results summary; README usage added only after the tested interface is stable.  
**Consumes:** Stage 5 caix build/bundle, Stage 4 recipe, Stage 0 target requirements.  
**Produces:** Final conversion/serving instructions, qualified context and memory limits, and a comparison with MLX.

- [ ] Repeat the frozen workload on the actual target hardware. A memory estimate, artificial process limit, or run on the 128 GB host cannot substitute for a 16 GB test.
- [ ] Test 50k total capacity with realistic prompt/output splits, such as 45k prompt plus 5k output, as well as a near-50k prompt with a small continuation. Include long reasoning so output reservation is real rather than nominal.
- [ ] Require no process termination, no non-finite results, correct long-context answers, green memory pressure without sustained new swapping, and at least 2 GiB available system headroom after warmup under the agreed background workload. If 16 GB is not unified memory, revise this budget explicitly in Stage 0.
- [ ] Compare caix/Core AI and MLX with the same source revision, prompts, capacity, output count, hardware, warm/cold conditions, and actual quantization recipes. Disclose precision differences; do not compare unmatched quantizations as pure runtime speed.
- [ ] Measure installation steps, load times, time to first token/answer, prefill, decode, and peak memory. Keep OS/toolchain/revision/command/raw-log evidence with each result; performance is conditional on those inputs.
- [ ] If MTP is available, qualify off/on on the actual target. Retain it as default only if it preserves supported semantics, fits the headroom budget including rollback costs, and gives a repeatable end-to-end benefit on the representative workload. Prefer explicit opt-in or disable it if those conditions fail.
- [ ] Publish a local usage recipe and capability table: preserved architecture/cache, reasoning/tools, tested context, quantization, GPU path, and optional features. Provide a caix patch upstream as a reviewable contribution if appropriate; publishing/merging remains a separate action.

**Exit gate:** The declared target actually passes quality, context, memory, and serving checks. If not, report the measured supported context/precision and recommend the MLX fallback or a larger-memory target.

## Stage 7: Optional follow-on work

Only after the initial result is useful:

- Qualify the full 131,072 context; allocation capability alone is insufficient.
- Evaluate prefix reuse with ring-history semantics, cancellation, and rewind. A generic full-cache trim cannot restore sliding keys already overwritten.
- Evaluate KV quantization if supported by the chosen runtime and necessary after weights/prefill optimization.
- Extend MTP beyond the modes qualified in Stage 2.5, for example verified stochastic acceptance or faster journaling, only after the initial result is useful. Existing caix EAGLE/MTP support remains insufficient evidence of Mellum compatibility.
- Investigate ANE separately if energy or deployment requirements justify static-shape authoring; embedded Metal expert kernels remain GPU-specific.
- Evaluate FIM as a separate raw-prompt capability against a documented reference; token presence alone is insufficient.

## Verification and handoff

Stages 0–1, followed by four-layer authoring and synthetic Stage 2.5B transactions, are the next executable work. Actual Stage 2.5A head inspection awaits the release. Stage 3 remains gated on Stage 2.5C; do not start a full export or freeze hidden-state outputs early. Review the reports before selecting later architecture/recipes. After each independently testable stage, retain its scripts and evidence in a focused change; do not commit large artifacts or mix the user's MLX work into Core AI commits.

The planning task performed source inspection, safetensors header/length checks, and read-only host/toolchain checks. All numerical probes, model conversion, builds, serving, and benchmarks above are pending. This project has no Sphinx setup, so the planning documents are plain Markdown; verify links and formatting without installing a documentation toolchain solely for this plan.
