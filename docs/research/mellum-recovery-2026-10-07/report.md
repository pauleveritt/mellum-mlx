# Mellum 2.1 Thinking: failure isolation and a working Pi workaround

With Superpowers and pi-subagents, Mellum chose inappropriate workflows and repeated invalid agent calls. Evidence points to skill-routing and error-recovery weaknesses under these instructions; the exact internal cause remains unproven. Remediation: disable automatic workflow loading, keep thinking enabled, and use focused file searches.

**Follow-up:** [OpenCode trials and scoped SQLite telemetry](opencode-report.md)
confirm focused retrieval and coding success in a second harness. The corrected
configured OpenCode conversation also completed; no historical unknown-agent
loop was reproduced. Model files and the original conclusions below are unchanged.

Date: 2026-10-07. Model: `JetBrains/Mellum2.1-12B-A2.5B-Thinking`, revision
`6f239041e7c79166f75f6788dbf7d1971fe1db89`.

## Outcome

**A useful workaround is verified. A universal model fix is not.** Keep the
existing six-bit MLX checkpoint and native hybrid cache. Run Pi with a clean
profile, thinking enabled, and a small set of file tools. Search documents on
disk for relevant lines rather than inserting an entire 50k-token document into
the prompt. This recovered the original failing document's exact values,
retrieved all nine values from three new large fixtures, answered a three-turn
conversation appropriately, and completed a small coding fix with three
independently passing tests.

**Q6 quantization is not the sole cause of the failures.** Relevant retrieval
failures also occur with original BF16 weights in direct MLX and an independent
llama.cpp implementation. Sampled quantization/configuration checks found no
conversion defect. These results favor a limitation of the original Thinking
model under the tested prompts and inference settings, with additional harness
interaction in the historical session. They do not prove that every runtime is
correct or establish a defect in JetBrains' canonical serving stack.

This report concerns the **original Thinking checkpoint**. “Original” does not
mean that the separate non-thinking Foundation model was tested.

The full historical Superpowers/subagent session has not been replayed or fixed
end to end. The workaround removes that machinery. Long-context retrieval
remains sensitive to content, placement, and runtime; there is no demonstrated
universal 50k quality guarantee or universally safe shorter context cutoff.

## Evidence and environment

The portable [evidence.json](evidence.json) contains experiment outputs, token
hashes, settings, sampled conversion checks, authoritative Pi final messages,
tool calls/results, and setup interruptions. The [handoff](handoff.md) identifies
open questions and the highest-value next experiments. No weights, credentials,
or private historical session messages are included in this bundle.

| Component | Recorded version/configuration |
| --- | --- |
| Hardware | Apple M5 Max, 128GB unified memory |
| Direct MLX | MLX-LM 0.32.0, MLX 0.32.3 |
| Pi server | oMLX 0.6.4, bundled MLX-LM 0.31.3 |
| Pi | 1.0.2, `@earendil-works/pi-coding-agent` |
| Independent runtime | llama.cpp build 9580, commit `b4e3dc613baa92a3884d4151e3d631395c81934a` |
| Q6 weights | Affine six-bit, group size 64; eight-bit MoE routers |
| Diagnostic GGUF | Original matrices stored as BF16; some norms/router tensors F32; no weight quantization |
| Attention | 21 sliding layers, window 1,024; seven full-attention layers |
| Full-attention RoPE | YaRN factor 16, original context 8,192, theta 500,000, attention factor about 1.277259 |
| Direct generation | 512-token prefill/batches; native caches; no cache quantization |

The sampled conversion audit checked 64 rows from four embedding/layer-0
matrices and the layer-0 query normalization vector. Recomputed packed weights,
scales, and biases were identical for those samples. Configuration differed
only by quantization; tokenizer and chat template bytes matched. This is strong
evidence against the suspected transform error, **not an audit of every tensor**.

Prompt hashes use SHA-256 over little-endian signed int32 token IDs. Every new
native control's verbose token dump matched its recorded count and hash. Earlier
thinking comparisons also matched the full token sequence across runtimes.
No server was used for the direct MLX or llama.cpp comparisons.

## What happened in the historical session

The supplied telemetry diagnosis documented skill names used as unregistered
agents, repeated attempts after errors, a supervisor response using the wrong
request identifier, and a challenge turn without a substantive answer. Its
parent contexts were about 13.5k–33.1k tokens, computed as input plus cache-read
tokens. Large cumulative usage totals reflected repeated processing, not a
single context window exceeding 50k.

Earlier reconstructed continuations showed skill/path confusion with original
BF16 weights as well as Q6. Those continuations omitted the original bootstrap
and translated harness messages. They support a broader behavioral concern;
they do not recreate the exact unknown-agent loop. The shareable bundle excludes
the private continuation prompts. Synthetic retrieval, conversation, and coding
fixtures provide independent, shareable evidence.

## Direct retrieval experiments

The original document contains `EARLY_CODE = "orchid7381"` and
`LATE_CODE = "maple4627"`. The task asks for both literal values in order.
Thinking produces 50,000 prompt tokens; the no-thinking template produces
50,006. These are distinct rendered prompts, not a token-identical comparison
between thinking modes. Within each matched runtime comparison, input tokens
are identical.

| Original document trial | Result |
| --- | --- |
| Thinking, greedy, 4,096 output tokens, BF16 MLX | Exhausted budget inside thinking; no completed answer |
| Same trial, Q6 MLX | Exhausted budget inside thinking; no completed answer |
| Same trial, BF16 llama.cpp | Exhausted budget inside thinking; no completed answer |
| Thinking, BF16 llama.cpp, temperature 1 / top-p .95 / top-k 20, seed 42 | Exhausted 4,096 tokens; no completed answer |
| Thinking, greedy, BF16 llama.cpp, **16,384** output tokens | Still exhausted budget inside repetitive thinking |
| No thinking, Q6 MLX | Incorrect duplicate `orchid7381` |
| No thinking, BF16 MLX | Incorrect duplicate `maple4627` |
| No thinking, BF16 llama.cpp, 4,096 output allowance | Incorrect duplicate `maple4627`; finished after 27 generated tokens |

Increasing the output allowance did not repair the long-document retrieval.
Disabling thinking removed the loop but did not repair literal accuracy. Raising
weight precision or replacing oMLX alone is therefore not an established fix.

### There is no universal hard 50k limit

The next matrix changed content, length, positions, and instructions. The direct
score requires exact case-sensitive literal values in order, with no extra
matching value occurrences; commas/newlines versus spaces are tolerated.
Pi retrieval uses a stricter exact one-line string comparison.

| No-thinking control | Q6 MLX | Original BF16 MLX | Original BF16 llama.cpp |
| --- | --- | --- | --- |
| Repetitive source, 965 / 3,976 / 7,994 / 15,989 / 23,984 / 31,979 tokens | All six pass | Not tested at these shorter lengths | Not tested at these shorter lengths |
| Repetitive source, 49,993 tokens | Pass | Pass | Pass; also passed portable rerun |
| Diverse source, 7,929 / 23,931 tokens | Both pass | Not tested | Not tested |
| Diverse source, 49,931 tokens | Fail | Not tested | Not tested |
| Original document, both constants moved to about 10% and 90%, 50,008 tokens | Pass | Pass | Fail; returned duplicate `orchid4627` |
| C++ source control, 23,928 tokens | Pass | Not tested | Not tested |
| C++ source control, 49,928 tokens | Fail | Fail exact case: `SPruce50171` with correct `hazel50439` | Fail; continued source code and exhausted 512 tokens |

The first row describes six shorter cases; together with the 49,993-token row,
the repetitive series contains seven successful Q6 cases. These fixtures differ
from the original document in more than length, so their success does not define
a reliable context threshold for arbitrary prompts.

Additional Q6 changes to the original document were unsuccessful: moving only
the early constant, moving only the late constant, strengthening the final
instruction, and asking only for the early constant. Asking only for the late
constant succeeded. Moving both succeeded in MLX but failed in llama.cpp.
Position sensitivity is a plausible contributor; it is not a general repair.

The initial diverse-source prompts contain zero literal `<|im_start|>` or
`<|im_end|>` markers. A separate C++-only control also failed at 50k. Chat-control
marker contamination does not explain away these results.

Runtime disagreements matter: agreement on the original failure rejects a
Q6-only explanation, but the moved-constant trial shows that implementations or
numerics can affect outcomes. A canonical vLLM comparison remains necessary
before attributing every failure to model weights.

## Pi workaround and iterations

Pi ran headlessly against the existing Q6 oMLX server. A separate temporary
`PI_CODING_AGENT_DIR` preserved the global configuration. Automatic extensions,
skills, prompt templates, themes, and context files were disabled. Only an
explicit diagnostic capture extension was loaded. Retrieval exposed `grep`;
coding exposed `read`, `edit`, and `bash`. This is a bounded tool workflow,
without delegation or mandatory skill selection.

Requests confirm `chat_template_kwargs.enable_thinking=true` and
`preserve_thinking=true` for the successful thinking trials. The Pi `reasoning`
usage counter was zero even when thinking blocks were present; that counter was
not used to infer whether thinking was enabled.

| Pi trial | Outcome |
| --- | --- |
| Original 50k source on disk, two separate literal searches, thinking off | Exact `orchid7381 maple4627` |
| Same file searches, thinking high | Same exact answer |
| Three new approximately 50k fixtures, thinking high, temperature 0 | All nine values exact, zero tool errors; decoy files ignored |
| Fixture 101, temperature 1 / top-p .95 / top-k 20, seeds 42/43/44 | All three answers exact; seed 44 recovered from one wrong-path tool error and an unsuccessful literal regex search |
| Clean three-turn greeting / README summary / methodological challenge, thinking high | Substantive answers; appropriate README read; no tool on challenge |
| Same conversation, thinking off | Greeting and summary appropriate; challenge returned self-directed analysis instead of a finished answer |
| Small coding task, thinking high | Correct price-times-quantity patch; tests unchanged; all three tests independently pass |
| Packaged runner reruns | Direct MLX short control, native 49,993-token control, Pi retrieval, coding, and conversation completed successfully |

The three greedy retrieval fixtures kept final model contexts around
2,129–2,454 tokens, measured as input plus cache-read tokens. Their source files
were large; their model prompts were small. The workaround does **not** demonstrate
reliable unaided 50k in-context retrieval.

Early iterations identified avoidable setup and prompt issues:

- A relative file path was resolved under the wrong working directory. Pi's
  `find` also required missing `fd`; it was installed before later runs. That
  trial ended at an external six-request guard and is not a clean model-only
  failure.
- A regex supplied with `literal:true` returned no matches. Separate plain
  literal searches recovered the values; the first successful recovery still
  violated the requested one-line format. Explicit search instructions then
  produced exact output.
- The first coding run fixed the code and passed tests, but the external
  six-request guard aborted its final response. A fresh run from the buggy
  fixture with a larger diagnostic bound completed normally. The portable
  runner also independently verified the fix.

This is why the recommendation keeps thinking enabled for agent work and uses
explicit file retrieval. Universal thinking-off and shorter-context-only
recommendations are not supported by these trials.

## Recommended operating path

1. Keep `Mellum2.1-12B-A2.5B-Thinking-6bit`. No model files, names, or weights were
   changed during recovery testing. The BF16 GGUF is a diagnostic reference.
2. Keep native hybrid caches and cache quantization disabled. Sliding layers
   retain local state; every fourth layer retains global state. Replacing this
   layout with a different attention/cache policy has not been validated here.
3. Keep the existing single-request oMLX setup. The earlier serving validation
   used a 56,000-token serving limit, 4,096 output tokens, a 14GiB memory guard,
   and measured about 11.744GiB physical peak on the 128GB machine. This is
   capacity evidence, not proof of 50k answer quality or physical 16GB-machine
   behavior. Current overlapping experiments are not performance benchmarks.
4. Use the clean Pi profile in [README.md](README.md). Start ordinary tasks with
   thinking high and a 4,096-token output cap; expand output only for a task that
   needs it. “High” maps to enabled thinking here, not a separately supported
   reasoning-effort parameter.
5. Keep files on disk. Specify the exact file and literal term, retrieve relevant
   lines, then inspect a bounded surrounding region when needed. Keep active
   prompt/history focused. The approximately 24k diverse controls passed, but
   24k is not a guaranteed quality threshold. Prefer the few-thousand-token
   contexts used by the successful workaround when possible.
6. For more complex agent tasks, widen the tool set gradually and validate each
   addition. Reintroduce Superpowers/delegation only as a separate experiment
   with explicit recovery rules and correct agent/request identifiers.

The hybrid cache helps memory capacity. It does not guarantee that the model
will retrieve every literal correctly or recover from every tool error. The
workaround preserves that cache and avoids relying on large-context retrieval
for exact facts that tools can obtain deterministically.

## Reproduction and questions for Mellum maintainers

The [bundle instructions](README.md) provide direct MLX/llama.cpp and headless Pi
commands. Twenty public/synthetic prompt cases are included, together with
goldens, fixtures, a pinned source-fragment license, and the evidence JSON.
Hashes in `manifest.sha256` cover the package files. Direct diagnostic commands
can finish with process exit zero while `passed:false`; inspect the result JSON.

The most valuable maintainer comparison is the pinned original Thinking
checkpoint on the documented vLLM stack: original legacy retrieval at 4k and
16k output, repetitive 50k positive control, moved-both control, and diverse
49,928-token control. Run exact input token checks and score literal accuracy
separately from whether thinking closes and a final answer appears. See
[handoff.md](handoff.md) for the experiment order.

Specific questions:

- Does canonical vLLM reproduce the repeated-thinking and incorrect-literal
  results with these exact prompts? Which supported versions/settings should
  be the reference?
- Is disabling thinking intended to be supported for this Thinking checkpoint,
  including tool work? The no-thinking final-answer failure merits separate
  treatment from retrieval accuracy.
- Is the MLX-versus-llama.cpp difference on `legacy-move-both` expected from
  numerics, or evidence of an attention/RoPE implementation mismatch?
- Are there recommended history/tool-result budgets or prompt conventions for
  hybrid-attention literal retrieval and recovery after failed tool calls?

## Sources and limitations

- [Pinned Mellum model card](https://huggingface.co/JetBrains/Mellum2.1-12B-A2.5B-Thinking/blob/6f239041e7c79166f75f6788dbf7d1971fe1db89/README.md), JetBrains, accessed 2026-10-07. Documents vLLM with Hermes tool parsing and Pi agentic evaluation (Pi 0.73.1, 114k context, up to 16k tokens/turn, Mellum temperature 1). Local tests do not reproduce that evaluation protocol.
- [Pinned llama.cpp Mellum converter](https://github.com/ggml-org/llama.cpp/blob/b4e3dc613baa92a3884d4151e3d631395c81934a/conversion/mellum.py) and [model graph](https://github.com/ggml-org/llama.cpp/blob/b4e3dc613baa92a3884d4151e3d631395c81934a/src/models/mellum.cpp), ggml-org, accessed 2026-10-07.
- [Pi source/docs](https://github.com/earendil-works/pi/tree/v1.0.2/packages/coding-agent), corresponding local installed 1.0.2 package documentation used for headless mode and temporary profiles.
- [Local experiment evidence](evidence.json), 2026-10-07; independent of the private historical prompts for the new synthetic/public trials.

These are targeted diagnostic experiments, not an error-rate estimate or general
coding benchmark. Three fixture seeds and one small coding task do not establish
broad reliability. BF16 tests require substantially more memory than the intended
16GB configuration. No physical 16GB machine was tested. Equal random seeds
across runtimes do not produce equivalent sampling paths. Global Pi/oMLX
configuration was preserved; clean profiles are temporary. No report was sent
to a third party.
