# ComfyUI model downloads

Download model assets into ComfyUI model categories using the Hugging Face CLI.

| Script | Purpose |
|---|---|
| [download_models.sh](download_models.sh) | URL download helper and destination selection |
| [download_wan22_i2v.sh](download_wan22_i2v.sh) | Wan 2.2 image-to-video asset recipe |
| [download_hunyuan_video_1.5.sh](download_hunyuan_video_1.5.sh) | HunyuanVideo 1.5 asset recipe |

Run these scripts with Bash and an installed `hf` command on `PATH`. Set
`MODEL_BASE_DIR` to the desired ComfyUI models directory; keep downloaded weights
outside the source checkout. Recipe scripts resolve the helper beside themselves,
so they can be invoked from another working directory.

From the repository root, preview a URL without downloading it:

```bash
MODEL_BASE_DIR=/path/to/ComfyUI/models \
  bash integrations/comfyui/model-downloads/download_models.sh --dry-run \
  https://huggingface.co/example/model/resolve/main/model.safetensors
```

The URL revision is passed explicitly to `hf download`. Every URL is validated before any
model directory is created. The default storage is `${XDG_DATA_HOME:-$HOME/.local/share}/comfyui/models`;
set `MODEL_BASE_DIR` to use an existing ComfyUI installation. Recipe arguments are forwarded to the helper.
Append `-- HF_ARGS` to pass extra CLI arguments while preserving spaces. The legacy `HF_EXTRA_ARGS`
environment string uses shell-like tokenization without evaluation; prefer explicit arguments.
A dry run creates no model directory and needs no `hf` installation. Downloads require a compatible
`hf download` CLI; authentication belongs to Hugging Face's native credential owner.
