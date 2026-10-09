# Mellum 2.1 native-cache serving validation

Validated on October 7, 2026, on an M5 Max with 128GB unified memory.

## Running configuration

- oMLX 0.6.4, using its bundled MLX-LM 0.31.3.
- API base URL: `http://127.0.0.1:8001/v1`.
- API model ID: `Mellum2.1-12B-A2.5B-Thinking-6bit`.
- Model settings: context window 56,000, generation budget 4,096, cache quantization disabled.
- Global settings: one concurrent request, RAM hot cache disabled, custom 14 GiB memory guard enabled.
- Only Mellum was loaded during the serving checks. SSD prefix caching remained enabled.

The server's native Mellum implementation creates 21 rotating caches with a
1,024-token window and 7 full-attention caches. The converted model retains BF16
native state, 6-bit affine weights with group size 64, and 8-bit MoE routers.
Its native context configuration remains 131,072; the smaller limit is a serving setting.

## Model identity and storage

The directory and shard filenames did not change:

```text
~/.cache/huggingface/hub/Mellum2.1-12B-A2.5B-Thinking-6bit/
  model-00001-of-00002.safetensors
  model-00002-of-00002.safetensors
```

The first shard is 5,293,425,543 bytes; the second is 4,579,675,825 bytes.
oMLX discovers the same folder through an existing symlink at
`~/.cache/huggingface/hub/mlx-community/JetBrains/Mellum2.1-12B-A2.5B-Thinking-6bit`.
The link adds no second copy of the weights and preserves the API model ID.

The previous settings were backed up before changes:

```text
~/.omlx/settings.json.bak-native-mellum-2026-10-07T20-33-13-820Z
~/.omlx/model_settings.json.bak-native-mellum-2026-10-07T20-33-13-820Z
```

The server required a managed `omlx restart` after its admin restart endpoint
left the menu bar supervisor reporting an unresponsive server. The managed restart
restored service. The running API subsequently confirmed the saved limits.

## Capacity and memory checks

| Check | Observed result |
| --- | --- |
| `/v1/models` | Model ID present, `max_model_len` 56,000 |
| Short arithmetic before the long run | `2 + 2` returned `4` |
| Cold long prompt | Exactly 50,000 prompt tokens, 0 cached tokens |
| Generation budget | Exactly 4,096 generated tokens, finish reason `length` |
| Total sequence | 54,096 tokens |
| Long request elapsed time | 48.179 seconds, including client observation overhead |
| Sampled oMLX physical memory peak | 11.744 GiB, approximately 12.61 GB |
| Memory sampling | 223 samples, approximately every 200 ms plus request overhead |
| Short arithmetic after long requests | `3 + 4` returned `7`; `6 * 7` returned `42` |

The prompt was measured through oMLX's cache-probe endpoint, and completion usage
confirmed the same count. The 4,096-token output was deliberately requested as a
long sequence of numbered comments to exercise the entire generation budget.
The memory number is a sampled process physical footprint, not an exact MLX
allocator high-water mark; sampling can miss short-lived peaks. It stayed below
the 14 GiB guard, and requests completed without memory-guard rejection.

## Retrieval-quality findings

Capacity and factual retrieval were checked separately. Both synthetic 50k
retrieval tests failed:

1. A prompt with repeated `alpha` padding placed identifiers at opposite ends.
   The output combined the earlier identifier's prefix with the later number.
2. A document containing 1,000 small Python functions and padding placed
   `EARLY_CODE = "orchid7381"` near the beginning and
   `LATE_CODE = "maple4627"` near the end. oMLX generated 2,048 tokens without
   correctly extracting both values.

Direct MLX generation with MLX-LM 0.32.0, native caches, a prefill step of 512,
and the same tokenized code-document prompt also failed to extract both values
within 2,048 generated tokens. It used temperature 1, top-p 0.95, and top-k 20,
matching the model's saved serving sampling settings, with a fixed native RNG
seed. The native run's reported MLX peak was 11.186 GB. The random streams and
prefill schedules were not identical, so this comparison does not isolate a cause.

The server can handle the requested sequence size within the observed memory
budget, but these tests do not establish reliable 50k factual retrieval. They
also do not establish performance on real repository-editing workloads or on a
machine with only 16GB total unified memory. No cache quantization or model
reconversion was introduced in response to the retrieval failures.

## Later comparison: original BF16 weights

On October 7, a [matched BF16-versus-Q6 investigation](2026-10-07-mellum-bf16-q6.md)
also reproduced the 50k retrieval failure with the original unquantized weights
under MLX. A reconstructed telemetry continuation at temperature 1 also produced
an unregistered-agent call with original BF16 weights. Quantization is therefore
not necessary for these failure classes. Original Mellum behavior and a shared
MLX implementation issue still require an independent-runtime comparison to
distinguish.
