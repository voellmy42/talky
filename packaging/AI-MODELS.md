# Optional AI models

Talky uses MLX-LM (MIT) for local language-model execution. Model weights are
downloaded only after an explicit installation action, separately from the app.

The editing preview model is an MLX Community 4-bit conversion of Qwen3-4B, developed
by the Qwen team at Alibaba Cloud, licensed under Apache License 2.0.
Qwen3-1.7B remains a legacy polishing/benchmark model under the same license.

- https://huggingface.co/Qwen/Qwen3-1.7B
- https://huggingface.co/Qwen/Qwen3-4B
- https://huggingface.co/mlx-community/Qwen3-1.7B-4bit
- https://huggingface.co/mlx-community/Qwen3-4B-4bit
- https://www.apache.org/licenses/LICENSE-2.0
- https://github.com/ml-explore/mlx-lm/blob/main/LICENSE

Exact conversion revisions, file sizes and integrity hashes are recorded in
`tools/model_manifests.json`. No model weights are committed or included in the
application bundle. Preserve applicable notices if redistributing model weights.
