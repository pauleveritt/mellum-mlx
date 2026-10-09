"""Convert the cached Mellum 2.1 checkpoint to MLX with its native hybrid cache."""

import argparse
import json
from pathlib import Path

from huggingface_hub import snapshot_download
from huggingface_hub.errors import LocalEntryNotFoundError
from mlx_lm import convert


MODEL_ID = "JetBrains/Mellum2.1-12B-A2.5B-Thinking"


def validate_source(source: Path) -> tuple[int, int]:
    """Check the indexed tensors and shard lengths before allocating a model."""
    config = json.loads((source / "config.json").read_text())
    if config.get("model_type") != "mellum":
        raise ValueError("The source must be a Mellum checkpoint.")
    if "quantization" in config or "quantization_config" in config:
        raise ValueError("Use the original unquantized checkpoint as the source.")
    for name in ("tokenizer.json", "tokenizer_config.json"):
        if not (source / name).is_file():
            raise ValueError(f"Missing tokenizer file: {source / name}")

    index = json.loads((source / "model.safetensors.index.json").read_text())
    weight_map = index["weight_map"]
    shard_names = sorted(set(weight_map.values()))
    if not shard_names:
        raise ValueError("The weight index contains no shards.")
    total_bytes = 0
    for name in shard_names:
        shard = source / name
        size = shard.stat().st_size
        with shard.open("rb") as stream:
            prefix = stream.read(8)
            header_size = int.from_bytes(prefix, "little")
            if len(prefix) != 8 or not 0 < header_size <= size - 8:
                raise ValueError(f"Invalid safetensors header: {shard}")
            header = json.loads(stream.read(header_size))
        tensor_end = max(
            int(tensor["data_offsets"][1])
            for key, tensor in header.items()
            if key != "__metadata__"
        )
        if size != 8 + header_size + tensor_end:
            raise ValueError(f"Incomplete or invalid weight shard: {shard}")
        for tensor_name, shard_name in weight_map.items():
            if shard_name == name and tensor_name not in header:
                raise ValueError(f"Missing tensor {tensor_name} in {shard}")
        total_bytes += size
    return len(shard_names), total_bytes


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source",
        type=Path,
        help="Local checkpoint directory; defaults to the cached HF snapshot (offline).",
    )
    parser.add_argument("--bits", type=int, choices=(4, 5, 6, 8), default=6)
    parser.add_argument(
        "--output",
        type=Path,
        help="Output directory; defaults to ~/models/Mellum2.1-12B-A2.5B-Thinking-Nbit.",
    )
    parser.add_argument(
        "--check", action="store_true", help="Validate the source without converting."
    )
    args = parser.parse_args()
    output = (
        args.output
        or Path.home() / "models" / f"Mellum2.1-12B-A2.5B-Thinking-{args.bits}bit"
    ).expanduser().resolve()
    try:
        if output.exists() and not args.check:
            raise ValueError(f"Output already exists; choose a new directory: {output}")
        source = args.source
        if source is None:
            cached = snapshot_download(MODEL_ID, local_files_only=True, dry_run=False)
            if not isinstance(cached, str):
                raise ValueError("Could not resolve a cached snapshot directory.")
            source = Path(cached)
        source = source.expanduser().resolve()
        count, size = validate_source(source)
        print(f"Source: {source}", flush=True)
        size_gib = round(size / 1_073_741_824, 2)
        print(f"Verified {count} shards ({size_gib} GiB).", flush=True)
        if args.check:
            return
        print(f"Output: {output}", flush=True)
        convert(
            hf_path=str(source),
            mlx_path=str(output),
            quantize=True,
            q_bits=args.bits,
            q_group_size=64,
            q_mode="affine",
            dtype="bfloat16",
        )
    except (OSError, ValueError, LocalEntryNotFoundError) as error:
        parser.error(str(error))
    print(
        f"Saved {args.bits}-bit weights; native BF16 hybrid cache and context settings preserved.",
        flush=True,
    )


if __name__ == "__main__":
    main()
