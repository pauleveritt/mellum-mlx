# Mellum 2.1 Core AI and caix research brief

**Date:** 2026-10-07  
**Question:** Can Mellum 2.1 run faithfully and usefully as a Core AI `.aimodel` served by caix, preserving its hybrid cache, long-context behavior, reasoning, and tools?  
**Scope:** The cached original `JetBrains/Mellum2.1-12B-A2.5B-Thinking` checkpoint, macOS GPU inference, caix integration, and reusable model-zoo authoring work. The working deployment target is one resident model, one generation at a time, 16 GB unified memory, and 50,000 total tokens including output. The target hardware and interpretation of 50k remain assumptions. This is research and a proposed design, not a verified port.

The evidence supports a feasible authoring project, not an existing conversion command. Core AI has the necessary model-state and GPU extension mechanisms. The zoo supplies useful implementations. Mellum's specific architecture and caix's prompt, cache, and sampling contracts still need confirmation experiments. A successful export, a model that loads, and a faithful server are three different milestones.

## Evidence baseline

| Component | Inspected revision or version |
| --- | --- |
| Mellum original checkpoint | `6f239041e7c79166f75f6788dbf7d1971fe1db89`, read from the local Hugging Face snapshot |
| caix | `234a1cef066db4027e93e34f2b468df7cb9d33b5` |
| caix's CoreAILM dependency | Apple `coreai-models` revision `c21ec9e75abf1e32c49d18da1aad9a03a7630ddd`, specified in `Package.swift` |
| Core AI model zoo | `8c0b73624fc3f36e68276a564998cccb8837d235` |
| Zoo overlay base | Apple `coreai-models` revision `b1cb71b8522d99408059fa0b98b8742171bcb0b8`, specified in `conversion/overlay/BASE` |
| Apple current main, for comparison | `1953c4f90ba0214c1abc7bebcb9be5107e329a46` |
| Existing repository environment | `mlx-lm==0.32.0`, `transformers==5.19.0` in `uv.lock`; Python requirement `>=3.14` |
| Online Mellum reference source | Transformers source commit `c633787a7acb9bd11e57cd8d599be2b767bbdbaa`; the locally inspected 5.19.0 modeling file has SHA-256 `125b204f0eb4f34b6356a5cf359c80658e819be9860a601800c59d61c3584fe0` |
| Available research/build host | M5 Max, 128 GB unified memory; macOS 27.0.1 build `26A434`; Xcode 27.0 build `27A266a` |

The source checkpoint was inspected through configuration, template and tokenizer files, the weight index, and all five safetensors headers. Each shard's actual length matched its header-derived expected length. This is structural evidence, not a checksum verification or an inference test. No Core AI conversion, numerical parity test, or caix generation was run for this brief.

The SDK contains `CoreAI.framework`, but `xcrun --find coreai-build` failed on this host and no `caix` executable was found on PATH. Runtime specialization may still be available; an ahead-of-time compiler is not a prerequisite for the first macOS experiment. Confirm the actual runtime and export packages before changing the toolchain.

## Findings

### 1. Mellum's hybrid architecture is sliding plus full attention

**Claim:** A faithful Mellum port needs different attention masks and cache retention policies for sliding and full layers.

**Evidence:** The checkpoint declares 28 layers in a repeating `sliding, sliding, sliding, full` pattern. All 28 MLPs are sparse MoE. Sliding attention has a 1,024-token window; seven layers retain full attention. Maximum positions are 131,072. This is not the recurrent-state/full-attention hybrid used by Qwen3.5.

| Property | Checkpoint value | Porting implication |
| --- | --- | --- |
| Hidden width | 2,304 | Do not infer attention head size from hidden width |
| Query/KV heads | 32 / 4 | Preserve grouped-query attention; do not materialize eight copies of KV in persistent storage |
| Head dimension | 128 | Q projection is 4,096 wide, while K and V are 512 wide |
| Sliding/full layers | 21 / 7 | Use separate cache groups and separate masks |
| Experts / selected experts | 64 / 8 in every layer | Preserve sparse routing and the weighted expert sum |
| Expert intermediate width | 896 | The configured dense intermediate width of 7,168 is not the expert FFN width |
| Vocabulary | 98,304 | Preserve tokenizer IDs and the full output head |
| Embedding/head | Untied | Both weight matrices must be loaded and exported |
| Source dtype | BF16 | Establish BF16/FP32 reference behavior before choosing GPU compute precision |

**Source:** [Mellum config and card][mellum] — JetBrains, accessed 2026-10-07 through the cached pinned snapshot; `config.json`, Model Overview, and Mellum2.1 Highlights.  
**Assessment:** Fact. Separate bounded and full caches are a recommendation.

### 2. Positional encoding and normalization are easy to mis-port

**Claim:** Matching the architecture name is insufficient; per-layer positional encoding, head normalization, and numerical reductions must match Mellum's reference.

**Evidence:** Sliding layers use default RoPE with theta 500,000. Full layers use YaRN with the same theta, factor 16, original context 8,192, beta values 32 and 1, and attention factor `1.2772588722239782`. The inspected Transformers implementation normalizes Q and K over each 128-dimensional head before RoPE. RMSNorm and router softmax use FP32 reductions. Attention scale is `128**-0.5`; half-split rotation is used.

Apple already has `YarnRoPE`, so a new primitive may be unnecessary. Its initializer does not consume every Mellum config key directly; compare its frequency vector and effective scaling against the actual reference. Do not assume that selecting a `yarn` label establishes equivalence. Probe absolute positions beyond 8,192 as well as short positions. Ring slots are storage addresses, never the RoPE position.

**Sources:** [Mellum config][mellum-config] — JetBrains; [Mellum reference implementation][hf-reference] — JetBrains/Hugging Face, also inspected locally in Transformers 5.19.0; [Apple RoPE primitives][apple-rope] — Apple; all accessed 2026-10-07. Pinpoints: `MellumRotaryEmbedding`, `MellumAttention`, `MellumRMSNorm`, `MellumTopKRouter`, `YarnRoPE`, and `initialize_rope`.  
**Assessment:** Facts about the inspected implementations; equivalence of Apple and Mellum YaRN remains unverified.

### 3. The checkpoint is usable directly; GGUF is an unnecessary intermediate

**Claim:** The cached original safetensors provide the required model weights without a GGUF dequantization step; this snapshot does not contain an MTP head.

**Evidence:** The snapshot has five BF16 safetensors shards, 5,631 indexed tensors, and exactly 12,149,923,072 parameters occupying 24,299,846,144 tensor-data bytes. It contains separate per-expert `gate_proj`, `up_proj`, and `down_proj` matrices, router weights, head-sized Q/K norm weights, and separate embedding/head weights.

| Parameter group | Count |
| --- | ---: |
| Routed experts | 11,098,128,384 |
| Attention projections and Q/K norms | 594,549,760 |
| Embedding | 226,492,416 |
| Output head | 226,492,416 |
| Routers | 4,128,768 |
| Other norms | 131,328 |

More than 91% of parameters are expert weights. Compression and sparse expert execution therefore deserve separate experiments. In the inspected reference, router probabilities are softmaxed across all 64 experts, the top eight are selected and renormalized, and SiLU-gated expert outputs are combined. A loader must explicitly stack or map the checkpoint's individual experts to the chosen Core AI layout; current Transformers code uses packed expert tensors internally.

No MTP, predictor, or drafter tensor names appear in this snapshot's weight index. The card says an MTP head is coming soon. Inspect the released head's interface before full export, as specified in the dated update below; production acceleration remains conditional. Do not invent a sidecar or assume caix's existing EAGLE/MTP paths apply. FIM and repository tokens exist in the tokenizer, but that does not establish a supported FIM workflow for this Thinking checkpoint.

**Sources:** [Checkpoint index][mellum-index] and [model card][mellum] — JetBrains, accessed 2026-10-07 through the cached pinned snapshot; header inventory and Model Overview/Serving with vLLM. [Reference implementation][hf-reference], `MellumExperts` and `MellumTopKRouter`.  
**Assessment:** Facts about this snapshot. Prefer the original safetensors source as a recommendation.

### 4. Serving semantics are part of preserving Mellum

**Claim:** Reasoning and tools require preservation of the source prompt template, structured conversation history, token IDs, and output parsing.

**Evidence:** The separate `chat_template.jinja` renders ChatML turns, `<think>` reasoning, JSON inside `<tool_call>` blocks, and tool results inside `<tool_response>` blocks. It accepts assistant `reasoning_content` and structured `tool_calls`, retains reasoning for the active tool interaction, and omits older reasoning when rendering prior turns. `enable_thinking=false` adds an empty closed thinking span; its effect on model quality is not established by the template alone.

Tokenizer IDs include `<think>` = 23, `</think>` = 24, `<|im_start|>` = 27, `<|im_end|>` = 28, tool-call delimiters = 29/30, and tool-response delimiters = 31/32. Thinking/tool delimiters are added tokens marked `special=false`, so indiscriminate special-token stripping is not a substitute for parsing them. EOS is 28; BOS/pad is 0. The tokenizer uses individual-digit splitting followed by ByteLevel preprocessing.

The card recommends Qwen3 reasoning and Hermes tool parsers in vLLM. It gives temperature 0.6, top-p 0.95, top-k 20 in its quickstart and reports temperature 1.0 for its agentic benchmark. These are distinct evaluation settings, not one universal default. Reasoning consumes context and output tokens; a 512-token server default can truncate a valid thinking response.

**Sources:** [Chat template][mellum-template], [tokenizer files][mellum-tokenizer], [generation config][mellum-generation], and [card][mellum] — JetBrains, accessed 2026-10-07 through the cached pinned snapshot; full template, added tokens, Serving with vLLM, Quickstart, and Evaluation notes.  
**Assessment:** Facts about prompt/output contracts; quality of thinking suppression and FIM behavior requires separate evaluation.

### 5. Core AI provides useful mechanisms, not guaranteed advantages on Mellum

**Claim:** Core AI offers portable model assets, device specialization, mutable state, compression, and GPU extensions; their practical advantage over MLX must be measured for Mellum.

**Evidence:** Apple's documentation describes `.aimodel` as a portable model representation that is specialized for the current device. Specialized executable assets are tied to hardware and OS; subsequent loads can use a cached specialization. The macOS export path supports dynamic KV capacity. Model graphs can carry mutable state and multiple functions. Custom Metal operations can be embedded in the Core AI graph.

| Mechanism | Potential value here | What must be measured |
| --- | --- | --- |
| OS-native Swift runtime | caix can serve without a Python inference process | Exact OS/SDK/exporter compatibility |
| Graph specialization and persistent compilation cache | Reuse compiled graphs across loads; keep a hot model resident | First load, second load, post-restart load, and reshapes |
| Mutable model state | Persist separate sliding/full KV without sending the whole history each step | State mutation, resets, capacity, and cancellation |
| Multiple entry points or assets | Optimize prefill and one-token decode separately | Shared state layout and absence of duplicated resident weights |
| Compression | Fit the model into the target memory budget | Actual supported schemes, quality, packed size, and peak residency |
| Embedded custom Metal | Read only routed experts; add attention kernels if needed | Mellum shape support and actual speed on target hardware |
| Compute-unit selection | GPU/ANE/CPU execution options | Actual placement; custom Metal is GPU-only |

Compilation caching is not prompt-prefix KV reuse. Four-bit weights are not four-bit KV. Dynamic cache support is not bounded sliding-cache support. A native runtime does not establish higher throughput, lower memory, or energy savings than MLX.

The pinned Apple revision used by caix documents macOS `4bit` and `none` presets. Current Apple main documents more options, including INT8 KV and FP4/FP8 presets requiring macOS 27.2+. Those newer presets cannot be assumed available in caix's pinned stack or on this macOS 27.0.1 host. MLX's existing six-bit conversion is also not evidence for a matching Core AI recipe.

**Sources:** [Specialization and caching][apple-specialization] — Apple, retrieved through Context7, accessed 2026-10-07; Overview. [Pinned Apple export documentation][apple-export] and [current export documentation][apple-current-export] — Apple; Quantization Options and Context Length. [Custom Metal guide][zoo-metal] — john-rocky, a community source, accessed 2026-10-07; What it is & when to use.  
**Assessment:** Mechanisms are documented facts. Mellum-specific benefits are hypotheses.

### 6. caix is a useful serving shell with identifiable integration gaps

**Claim:** caix supplies the API and model-management shell, but its generic route does not yet establish faithful Mellum cache, prompt, and sampling support.

**Evidence:** caix provides model discovery/loading, persistent handles, request serialization per model, OpenAI and Anthropic API adaptation, streaming normalization, a dashboard, and model management. Its bundle loader expects `kind=llm`, an asset mapping, tokenizer files, language/vocabulary/context metadata, and optionally prefill/decode function mappings.

The inspected Apple architecture registries and caix's static support list have no `mellum` entry or remapping. The zoo catalog/source tree also has no Mellum-specific recipe. Adding a preset name alone would not supply the missing authored graph or establish compatibility.

The generic fast route uses Apple's CoreAILM engine. The legacy/direct `LLMEngine` binds `keyCache` and `valueCache`; it also has named support for `convState` and `recState`. This is not a generic four-state implementation for Mellum's `slidingKeyCache`, `slidingValueCache`, `fullKeyCache`, and `fullValueCache`. Descriptors drive allocations, but the accepted names and semantics remain specific.

There are also concrete prompt and sampling concerns:

- `ModelHandle.stringMessages` returns only role/content for the generic persistent backend, dropping assistant tool calls and reasoning fields.
- API requests decode `chat_template_context`, but the generic persistent branch does not forward that context. Mellum's thinking switch would therefore need explicit propagation.
- `PipelinedLLM` builds `SamplingConfiguration` with `topP: nil`. An accepted `top_p` field does not currently establish its use on that path.
- `OutputFormat.detect` recognizes Mellum's template markers as Qwen/ChatML-like, and the streaming normalizer handles reasoning/tool markers. This is encouraging compatibility evidence, not proof of a complete multi-turn tool round trip.
- `MonolithicPrefillPolicy` defaults to at most 16 query tokens on the stateful monolithic path because of observed trace-shape/determinism issues. At 50k tokens, that is roughly 3,125 prefill calls before counting any other overhead.

The source supports a `COREAI_DIRECT_RUNTIME=1` build that avoids CoreAILM's FoundationModels dependency and a full `COREAI_RUNTIME=1` build with CoreAILM. Try both where needed; select a production path explicitly. Do not use Qwen recurrent-state flags or rename sliding KV to recurrent state to force a Mellum bundle into an unrelated route.

**Sources:** [Package/build modes][caix-package], [conversion support check][caix-support], [bundle manifest][caix-manifest], [persistent routing][caix-persistent], [direct engine][caix-engine], [model manager][caix-manager], [API types][caix-api], [pipelined engine][caix-pipelined], [output normalizer][caix-output], and [prefill policy][caix-prefill] — RedHillsMediaFL; [pinned architecture registry][apple-registry] — Apple; all accessed 2026-10-07; named types/functions above.  
**Assessment:** Facts about the inspected source. A Mellum-specific direct engine is a provisional recommendation.

### 7. The zoo supplies separable building blocks

**Claim:** The zoo can reduce authoring and validation work, but its recipes and runtime patches require Mellum-specific adaptation and revision reconciliation.

**Evidence:** Its current conversion README and overlay README package authored Python models and pipeline changes against a pinned Apple base. The older caveat in `PORTING.md` saying the overlay is not packaged is superseded by those current files. Swift patches are separate. Its overlay and caix's runtime dependency use different Apple revisions.

| Zoo resource | Useful part | Mellum-specific adaptation |
| --- | --- | --- |
| Gemma 4 stateful authoring | Separate sliding/full caches, ring mask, state routing | 21/7 cache slots, common head dimension 128, no Gemma KV sharing, PLE, softcap, or extra norms |
| Muse Glimmer exporter | Three sliding layers followed by one full layer; per-type positions | Mellum uses YaRN full layers rather than NoPE; Mellum FFNs are MoE |
| `moe_metal.py` / Qwen3.6 MoE exporter | `gather_qmm`, selected-expert weights, quantized expert layout | 64 experts, top eight, width 896, Mellum router/combine semantics; measure decode and batched prefill separately |
| `BatchedMetalSwitchGLU` | Multiple token/expert pairs and expert grouping | Confirm tracing, quantization, scratch memory, and crossover against ordinary batched operations |
| Export helpers and overlay | State-preserving export, metadata/tokenizer packaging, pinned dependencies | Introduce `mellum`, retain provenance, reconcile rather than blindly apply overlays |
| `coreai_gate.py` / `zoo_verify.py` | Numeric vs packaging verification as separate checks | Add a Mellum reference; the existing architecture choices are not automatic Mellum coverage |
| Generic N-state Swift runner | Prove the four-state model independently of serving | Port the proved binding/reset logic into caix; zoo success alone is insufficient |

Stock MoE over-read and custom-kernel speedups are reported on other models. They motivate an experiment; they are not Mellum performance predictions. The zoo includes both ring and linear sliding-cache paths, so a published Gemma bundle must be inspected rather than assumed to use the ring.

**Sources:** [Zoo conversion README][zoo-conversion], [overlay README and BASE][zoo-overlay], [overlay source patch][zoo-patch], [Muse exporter][zoo-muse], [Qwen MoE exporter][zoo-moe], [runtime notes][zoo-runtime], and [porting guide][zoo-porting] — john-rocky/community, accessed 2026-10-07; relevant class/function names and Verification/Track L sections.  
**Assessment:** Facts about reusable source. Reuse choices are recommendations.

### 8. Ring-cache chunk correctness is a first-stage experiment

**Claim:** A width-W ring that overwrites an entire new chunk before attention can lose keys required by earlier queries; limiting chunk size to W does not prove correctness.

The zoo's Gemma ring implementation writes a block into a width-W buffer before attention. It explicitly assumes `offset % W + query_len <= W` and acknowledges a chunked-prefill-at-offset caveat. Even an aligned block that does not cross the physical end can overwrite old keys needed by its earlier queries once the window is full. Bounding chunk size by W does not resolve this.

For example, with W=4, cached positions 0..3, and a new block 4..5, writing both tokens replaces slots containing 0 and 1. Query 4 should still see positions 1..4, but position 1 is already gone. Its mask cannot reconstruct the missing key. A final query having the right keys at one layer does not establish whole-model equivalence: earlier incorrect hidden states become keys/values in later layers.

Start with S=1 as the correctness baseline. For chunk prefill, preserve the previous W-1 keys plus all C current keys through attention, then commit the retained tail to the ring. That needs a temporary attention view of at most W-1+C positions, or another design proven equivalent. Test every query's output, wraparound, subsequent decode, and a multi-layer stack. Masks must use absolute positions and reference window inclusivity.

**Sources:** [Cache notes][zoo-cache] and [Gemma `Attention.forward_stateful` / `_ring_mask`][zoo-patch] — john-rocky/community, accessed 2026-10-07.  
**Assessment:** The implementation assumptions are source facts. The W=4 example and proposed preservation strategy are analytical deductions, to be confirmed numerically.

### 9. Memory looks promising, but long prefill is an independent feasibility gate

**Claim:** Bounded sliding caches materially reduce persistent KV memory, while weight residency, temporary allocations, and long-context prefill remain separate feasibility questions.

For one request with four KV heads, head dimension 128, and two bytes per K/V element, the idealized persistent hybrid cache upper bound is:

```text
2 (K,V) × 4 heads × 128 dimensions × 2 bytes × (7T + 21 × 1024)
```

| Total tokens T | Bounded sliding + full KV | All 28 layers full-length KV |
| --- | ---: | ---: |
| 4,096 | 0.096 GiB | 0.219 GiB |
| 16,384 | 0.260 GiB | 0.875 GiB |
| 50,000 | 0.709 GiB | 2.670 GiB |
| 131,072 | 1.791 GiB | 7.000 GiB |

Raw all-parameter weight lower bounds are 5.66 GiB at four bits, 8.49 GiB at six bits, 11.32 GiB at eight bits, and 22.63 GiB at 16 bits. They exclude scales, codebooks, mixed precision, alignment, compilation, duplicate assets, activation/scratch tensors, other resident models, and the OS. Six bits is a comparison with the MLX option, not a confirmed Core AI scheme. An 8-bit baseline on the 128 GB host is useful even if it is too tight on the eventual 16 GB machine.

The seven full-attention layers still need increasingly long histories. Efficient chunking bounds activation memory but does not remove the quadratic aggregate attention work during long prompt ingestion. A fast S=1 decode kernel does not prove useful 50k prefill. Measure prefill wall time, time to first answer after reasoning, peak memory, cold/warm loads, and long-context correctness separately from decode tokens/s.

**Sources:** Checkpoint config/index above; [caix prefill policy][caix-prefill].  
**Assessment:** Calculations under stated assumptions, not measured allocations or performance.

## Staged research and confirmation experiments

The first two stages establish whether the port deserves a full-model implementation. Later stages qualify correctness, serving, and deployment separately. All runtime experiments below remain pending; source and host inspection are the completed research baseline.

| Stage | Research question and experiment | Evidence required before continuing |
| --- | --- | --- |
| 0. Reproduce the baseline | Confirm the target memory/context meaning; pin source, exporter, zoo, caix, OS, and SDK; export and load a tiny graph | Source/environment manifests and one working Python-to-Core-AI-to-Swift path |
| 1. Confirm the contracts | Probe four mutable cache states through caix; reproduce ring chunk errors; compare YaRN/QK norms; test routed-expert kernels and exact rich prompt rendering | Numerical/state transcripts, negative controls, prompt token-ID matches, supported sampling options, and a selected runtime ABI |
| 2. Prove real-weight authoring | Load the first four real layers and compare intermediate activations, routing, prefill, and decode against the pinned Mellum reference | Strict weight mapping and exported multi-layer parity across window boundaries |
| 2.5. Inspect MTP before freezing the interface | Inspect the forthcoming head/reference, reproduce synthetic rejection across ring boundaries, then test the real acceptance loop | Released head contract, safe restore/replay, and an explicit final export/acceleration decision |
| 3. Validate the full model | Export all 28 layers with a diagnostic precision; separately check packaging and computation | Complete weight binding, reproducible oracle transcripts, correct 4k generation, and measured residency |
| 4. Find a useful deployment recipe | Compare quantization quality and batched prefill through 50k against original Mellum and MLX | Quality/memory/latency measurements supporting a specific precision and prefill strategy |
| 5. Qualify caix serving | Exercise OpenAI/Anthropic streaming, reasoning, multi-turn tools, parameter propagation, cancellation, and resets | Endpoint transcripts matching reference prompts and independent-runner behavior |
| 6. Test the actual target | Repeat realistic prompt/output splits on the intended 16 GB machine | Measured 50k correctness, memory headroom, and useful latency on that hardware |

**Decision rule:** Continue only when the preceding stage has produced its evidence. Revise the cache/runtime design when a small experiment disproves it. Stop or reduce the qualified scope when no candidate meets the target; retain MLX as the working alternative. A model listing, successful export, plausible response, or large-machine memory estimate cannot substitute for the relevant gate.

The [implementation plan](../superpowers/plans/2026-10-07-mellum-coreai-caix.md) expands these stages into named probes, fixtures, files, and acceptance criteria. MTP interface discovery is now a gate before full export; production acceleration remains conditional. Prefix reuse, KV quantization, ANE tuning, FIM qualification, and full-131k performance remain optional follow-on research.

## Open questions and limits

- Is the actual deployment target a 16 GB Apple silicon machine, and does 50k mean total tokens or prompt tokens plus additional output? The available 128 GB build host cannot prove a 16 GB fit.
- Can the installed OS/SDK and a pinned export environment run mutable states, SDPA, and the zoo's custom kernels together? Most zoo workaround evidence was measured on beta builds, not this installed build.
- Does Apple YaRN match this Mellum configuration without a small adapter? Does FP16 compute preserve the BF16 source's numerical range on real activations?
- Can four cache states and shared prefill/decode weights be served with a small caix extension, or does the existing staged path offer a better fit after probing?
- Which prefill method is correct, fast, and memory-efficient at 50k? Which expert quantization passes Mellum-specific quality evaluation?
- Where should accepted sampling, thinking, and tool-history fields be handled in the Mellum route? Any unsupported option must be explicit rather than silently ignored.
- Does a future Mellum MTP artifact become available with a documented contract? None was found in the inspected checkpoint.

## Proposed design constraints

Use the original pinned safetensors source and leave the existing MLX converter/environment intact. Start with macOS GPU execution, one model, batch size one, and ordinary autoregressive generation. Preserve all 28 layers, top-eight routing, both RoPE regimes, untied embedding/head, tokenizer IDs, and reasoning/tool prompt behavior. Keep sliding cache residency independent of T and full-cache residency proportional to seven layers. Stop before a full export if the primitive or caix contract experiments fail.

The provisional model-state ABI has `slidingKeyCache` and `slidingValueCache` shaped `[21, 1, 4, 1024, 128]`, and `fullKeyCache` and `fullValueCache` shaped `[7, 1, 4, capacity, 128]`. Use separate prefill/decode functions with matching state descriptors if useful; a single graph remains a valid first experiment. The final ABI and production route are outputs of the early experiments, not assumptions to conceal behind metadata.

Require MTP interface discovery and synthetic speculative rollback confirmation before full export; defer production MTP/EAGLE acceleration until its correctness, sampling, memory, and performance gates pass. Defer cross-request prefix reuse/rewind, ANE optimization, concurrent generation, KV quantization, full 131k qualification, and product claims about FIM. Include normal reasoning/tool support in the first faithful server milestone. Static-shape ANE authoring is a separate future project if measurements justify it.

## Recommendation

Proceed with small contract experiments before implementing or exporting all 12.15B parameters. Confidence is medium that the available authoring primitives and zoo code can preserve Mellum, and low on a useful 50k/16 GB production result until prefill, quantization, and caix integration are measured. The immediate next step is a reproducible environment and a tiny four-state sliding/full model, followed by isolated YaRN and expert-kernel checks. Keep MLX as the measured baseline and fallback.

The [staged plan](../superpowers/plans/2026-10-07-mellum-coreai-caix.md) defines experiments, acceptance criteria, decision points, and later implementation work.

## 2026-10-07 update: MTP arrival and export timing

**Claim:** Expected MTP availability changes when to freeze the graph interface, rather than making the reusable porting research obsolete.

**Evidence:** The user reports that Mellum's MTP head will arrive in the next few days and accepted the approach of continuing confirmation experiments while postponing the full export. No published head or decoding implementation has been inspected. The earlier finding that the pinned snapshot lacks MTP weights remains valid.

**Source:** User-provided release expectation and agreed sequencing in this conversation, 2026-10-07; not an independently confirmed publisher release date.  
**Assessment:** The expected arrival is user-provided evidence. Continuing reusable research and gating full export are recommendations adopted for this plan.

Continue source/runtime, cache, YaRN, MoE, and prompt checks now, followed by four-layer real-weight authoring. Synthetic speculative acceptance/rejection fixtures can also be built before the head arrives. When released, inspect its target revision, weights/configuration, required hidden-state outputs, state ownership, draft/verify functions, and reference acceptance algorithm before freezing the target ABI.

Verification may overwrite committed sliding-ring keys before a rejected draft is discarded. Rewinding only a full-cache length cannot recover those keys. The conservative experiment should snapshot sliding states and other mutable state, restore after rejection, reset the full-cache cursor, and replay the accepted prefix. For the target's 16-bit sliding KV, the snapshot is about 42 MiB; head state/weights and verification scratch add unknown costs. Verify every accepted-prefix length, window boundaries, EOS, cancellation, and the next request against fresh autoregressive replay.

Full-model export resumes after the head contract is inspected and a dated interface/acceleration decision is recorded. Head incompatibility or an unfavorable MTP speed/memory result can justify an autoregressive first release; neither warrants mislabeling acceleration as supported. If the release is late, independent experiments continue while this export gate remains pending. Lossless greedy equivalence does not by itself establish correct stochastic sampling.

[mellum]: https://huggingface.co/JetBrains/Mellum2.1-12B-A2.5B-Thinking/tree/6f239041e7c79166f75f6788dbf7d1971fe1db89
[mellum-config]: https://huggingface.co/JetBrains/Mellum2.1-12B-A2.5B-Thinking/blob/6f239041e7c79166f75f6788dbf7d1971fe1db89/config.json
[mellum-index]: https://huggingface.co/JetBrains/Mellum2.1-12B-A2.5B-Thinking/blob/6f239041e7c79166f75f6788dbf7d1971fe1db89/model.safetensors.index.json
[mellum-template]: https://huggingface.co/JetBrains/Mellum2.1-12B-A2.5B-Thinking/blob/6f239041e7c79166f75f6788dbf7d1971fe1db89/chat_template.jinja
[mellum-tokenizer]: https://huggingface.co/JetBrains/Mellum2.1-12B-A2.5B-Thinking/blob/6f239041e7c79166f75f6788dbf7d1971fe1db89/tokenizer.json
[mellum-generation]: https://huggingface.co/JetBrains/Mellum2.1-12B-A2.5B-Thinking/blob/6f239041e7c79166f75f6788dbf7d1971fe1db89/generation_config.json
[hf-reference]: https://github.com/huggingface/transformers/blob/c633787a7acb9bd11e57cd8d599be2b767bbdbaa/src/transformers/models/mellum/modeling_mellum.py
[apple-rope]: https://github.com/apple/coreai-models/blob/c21ec9e75abf1e32c49d18da1aad9a03a7630ddd/python/src/coreai_models/primitives/macos/rope.py
[apple-specialization]: https://developer.apple.com/documentation/coreai/managing-model-specialization-and-caching
[apple-export]: https://github.com/apple/coreai-models/blob/c21ec9e75abf1e32c49d18da1aad9a03a7630ddd/models/README.md
[apple-current-export]: https://github.com/apple/coreai-models/blob/1953c4f90ba0214c1abc7bebcb9be5107e329a46/models/README.md
[caix-package]: https://github.com/RedHillsMediaFL/caix/blob/234a1cef066db4027e93e34f2b468df7cb9d33b5/Package.swift
[caix-support]: https://github.com/RedHillsMediaFL/caix/blob/234a1cef066db4027e93e34f2b468df7cb9d33b5/python/converter/check_support.py
[apple-registry]: https://github.com/apple/coreai-models/blob/c21ec9e75abf1e32c49d18da1aad9a03a7630ddd/python/src/coreai_models/models/registry.py
[caix-manifest]: https://github.com/RedHillsMediaFL/caix/blob/234a1cef066db4027e93e34f2b468df7cb9d33b5/Sources/PipelineRuntime/BundleManifest.swift
[caix-persistent]: https://github.com/RedHillsMediaFL/caix/blob/234a1cef066db4027e93e34f2b468df7cb9d33b5/Sources/PipelineRuntime/PersistentModel.swift
[caix-engine]: https://github.com/RedHillsMediaFL/caix/blob/234a1cef066db4027e93e34f2b468df7cb9d33b5/Sources/PipelineRuntime/LLMEngine.swift
[caix-manager]: https://github.com/RedHillsMediaFL/caix/blob/234a1cef066db4027e93e34f2b468df7cb9d33b5/Sources/CoreAIServer/ModelManager.swift
[caix-api]: https://github.com/RedHillsMediaFL/caix/blob/234a1cef066db4027e93e34f2b468df7cb9d33b5/Sources/CoreAIServer/APITypes.swift
[caix-pipelined]: https://github.com/RedHillsMediaFL/caix/blob/234a1cef066db4027e93e34f2b468df7cb9d33b5/Sources/PipelineRuntime/PipelinedLLM.swift
[caix-output]: https://github.com/RedHillsMediaFL/caix/blob/234a1cef066db4027e93e34f2b468df7cb9d33b5/Sources/CoreAIServer/OutputNormalizer.swift
[caix-prefill]: https://github.com/RedHillsMediaFL/caix/blob/234a1cef066db4027e93e34f2b468df7cb9d33b5/Sources/PipelineRuntime/MonolithicPrefillPolicy.swift
[zoo-metal]: https://github.com/john-rocky/coreai-model-zoo/blob/8c0b73624fc3f36e68276a564998cccb8837d235/knowledge/custom-metal-kernels.md
[zoo-cache]: https://github.com/john-rocky/coreai-model-zoo/blob/8c0b73624fc3f36e68276a564998cccb8837d235/knowledge/stateful-kv-cache.md
[zoo-conversion]: https://github.com/john-rocky/coreai-model-zoo/blob/8c0b73624fc3f36e68276a564998cccb8837d235/conversion/README.md
[zoo-overlay]: https://github.com/john-rocky/coreai-model-zoo/tree/8c0b73624fc3f36e68276a564998cccb8837d235/conversion/overlay
[zoo-patch]: https://github.com/john-rocky/coreai-model-zoo/blob/8c0b73624fc3f36e68276a564998cccb8837d235/conversion/overlay/patches/python-overlay.patch
[zoo-muse]: https://github.com/john-rocky/coreai-model-zoo/blob/8c0b73624fc3f36e68276a564998cccb8837d235/conversion/export_muse_glimmer_decode_pipelined.py
[zoo-moe]: https://github.com/john-rocky/coreai-model-zoo/blob/8c0b73624fc3f36e68276a564998cccb8837d235/conversion/export_qwen3_6_moe_metal_decode_pipelined.py
[zoo-runtime]: https://github.com/john-rocky/coreai-model-zoo/blob/8c0b73624fc3f36e68276a564998cccb8837d235/knowledge/swift-runtime.md
[zoo-porting]: https://github.com/john-rocky/coreai-model-zoo/blob/8c0b73624fc3f36e68276a564998cccb8837d235/PORTING.md
