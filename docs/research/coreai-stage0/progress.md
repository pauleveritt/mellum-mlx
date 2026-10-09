# Stage 0 progress — 2026-10-07

**Plan:** [Mellum Core AI and caix](../../superpowers/plans/2026-10-07-mellum-coreai-caix.md).

**Scope:** The user authorized the first step. Confirm the deployment target and record the independently observable baseline; later Stage 0 work remains pending.

- Deployment details: requested from the user; assumptions remain unconfirmed in [target.json](target.json).
- Build host and SDK: rechecked and recorded in [environment.json](environment.json). Hardware identifiers unique to this machine are omitted.
- Source metadata: rechecked the pinned configuration and index. No new checksum, tensor-header, or numerical verification is claimed.
- Runtime/export: not run. No Python toolchain was invoked, no dependencies were installed, and no model export was attempted.

Ruling: Interpret “first step” as Stage 0's target-confirmation step, with independent read-only baseline checks while awaiting the answer. This avoids starting later implementation before the target is established; it postpones source-inventory implementation to the next step.

Ruling: Keep this step to research artifacts in the existing docs directory. No source implementation is underway, so worktree creation and implementation test setup are deferred to the first code task. Existing MLX changes remain intact.

**Completion gate:** Record the actual target chip/memory, context interpretation, and representative reasoning/output allowance before marking the first Stage 0 checkbox complete. The 128 GB build host cannot substantiate a 16 GB deployment claim.

## Source-inventory step — completed 2026-10-07

**Scope:** The user's “next” advances the independent source-inventory check. Target confirmation remains pending; this does not satisfy Stage 0's runtime exit gate.

**Evidence:** [source_manifest.json](source_manifest.json), generated from the pinned local snapshot. All five safetensors headers contain exactly the expected 5,631 BF16 tensors and 12,149,923,072 parameters. The audit checks every expected tensor name and shape, index/header mapping in both directions, contiguous nonoverlapping byte ranges, per-tensor byte counts, and exact shard lengths. All snapshot files are hashed; each hash matches the content address used by the snapshot link (SHA-256 for weight files, Git blob SHA-1 for ordinary Git files). No additional safetensors or MTP tensor names were found in this snapshot.

**Verification:** The external audit exited 0 after six synthetic corruption controls and all real-source checks passed. The complete tensor layout and replayable audit script are retained outside Git at `/Users/pauleveritt/.cache/mellum-coreai/stage0/6f239041e7c79166f75f6788dbf7d1971fe1db89/`; the manifest records their paths and SHA-256 hashes. Tensor payload bytes were streamed for hashing, never decoded or allocated as model tensors.

**Limits:** This verifies consistency with the local cache's content addresses. Publisher checksums were not independently fetched. Tensor values, model inference, Core AI exports, and numerical parity remain untested. MTP absence applies only to this pinned revision.

Ruling: Use an external Node audit for this research step, preserving the MLX environment and avoiding repository implementation changes. The planned reusable `source_inventory.py` remains pending for the code phase; this costs one later implementation task but provides the source evidence now.

**Correction:** The IDE environment tool is available. `get_python_environment` for `main.py` reports the project's Python 3.14 virtual environment and uv package manager. The previous “tool unavailable” note in the environment manifest has been corrected. No Python toolchain command or environment mutation was needed for this audit.

**Audit correction:** The initial run incorrectly compared a weight's hash against the final storage filename in a two-level cache symlink chain. The calculated SHA-256 already matched the snapshot's immediate repository blob name. The corrected audit compares against that name and passes for every snapshot file; no source file was changed.

**Next at this point:** Capture and validate the exact configuration, layer/MLP types, RoPE, normalization/activation settings, tokenizer IDs, template bytes, and generation configuration. This is completed in the next entry.

## Configuration and tokenizer contract — completed 2026-10-07

**Evidence:** [model_contract.json](model_contract.json), extracted from the pinned JetBrains checkpoint's `config.json`, `tokenizer.json`, `tokenizer_config.json`, `special_tokens_map.json`, `chat_template.jinja`, and `generation_config.json`. All six file hashes match the preceding source inventory. The replayable audit and its SHA-256 are recorded in the contract.

**Checks passed:** Complete configuration equality, including all 28 attention/MLP types, default/YaRN parameters, RMSNorm epsilon, SiLU, normalized top-eight routing, head dimensions, and untied embedding/head. Full-attention layers are 3, 7, 11, 15, 19, 23, and 27 (zero-based). All 56 Q/K norm tensors have width 128. The tokenizer has a bijective 98,304-entry vocabulary, 98,013 merges, and 35 added-token descriptors agreeing between the vocabulary and tokenizer configuration. BOS/EOS and tokenizer pad/unknown mappings agree across artifacts; individual-digit splitting and ByteLevel settings match the inspected baseline. Six negative controls reject altered layer types, YaRN scaling, norm epsilon, head dimension, EOS ID, and thinking-token special status.

**Serving findings:**

- The exact 4,849-byte UTF-8 template is captured in the contract. It is a separate `chat_template.jinja`, with no embedded template in `tokenizer_config.json`; bundle packaging and loading must preserve that file.
- Thinking IDs 23/24 and tool delimiter IDs 29–32 are marked `special=false`. ChatML IDs 27/28 are special tokens. Preserve these distinctions when parsing output and constructing stop behavior.
- `generation_config.json` contains BOS 0, EOS 28, `_from_model_config`, and the source Transformers version. It contains no temperature, top-p, top-k, sampling flag, or output limit. The model-card examples are separate recommendations, not defaults from this file.
- The BPE model has no unknown-token fallback, although the tokenizer configuration assigns `<|endoftext|>` to its `unk_token`, pad, and BOS properties. Preserve the actual artifacts rather than rebuilding a tokenizer from role-token IDs alone.

**Assessment:** Facts about the pinned source artifacts. Packaging and parsing consequences are recommendations. No source drift was found.

**Limits:** Template rendering, exact prompt token-ID fixtures, Swift/caix tokenizer equivalence, and numerical RoPE/router/norm behavior remain untested. The configured 131,072-position limit is distinct from the initially qualified runtime capacity. No model weights were loaded and no environment was changed.

**Next:** Record installed MLX/Python package versions and the exact Transformers Mellum reference, then investigate how its packed expert representation maps the checkpoint's separate expert tensors. Target confirmation and the tiny Core AI runtime path remain pending.
