# Mellum MLX conversion

This project converts the original Mellum 2.1 Thinking safetensors checkpoint into a six-bit MLX model. The conversion uses eight-bit routers and native hybrid attention caches. It includes a Python conversion script and local serving validation. `corpus.py` is an independent large source document for retrieval checks; `notes.md` contains obsolete test data.
