#!/usr/bin/env bash
# Explicit Hugging Face URL downloads into a user-selected ComfyUI model directory.
set -euo pipefail
BASE_DIR="${MODEL_BASE_DIR:-${XDG_DATA_HOME:-$HOME/.local/share}/comfyui/models}"
DRY_RUN=false
URLS=(); EXTRA=(); GLOBAL=()
usage() {
  echo 'Usage: bash download_models.sh [--dry-run] URL... [-- HF_ARGUMENT...]'
  echo 'MODEL_BASE_DIR selects the model directory; HF_EXTRA_ARGS accepts shell-quoted arguments (never evaluated).'
}
while [[ $# -gt 0 ]]; do
  case "$1" in
    --help|-h) usage; exit 0 ;;
    --list|-l) echo 'No named presets; use an explicit Hugging Face URL or a recipe.'; exit 0 ;;
    --dry-run) DRY_RUN=true; shift ;;
    --) shift; EXTRA=("$@"); break ;;
    https://huggingface.co/*) URLS+=("$1"); shift ;;
    *) echo 'Error: expected an explicit HTTPS Hugging Face resolve/blob URL' >&2; exit 1 ;;
  esac
done
[[ ${#URLS[@]} -gt 0 ]] || { usage >&2; exit 1; }
if [[ ${#EXTRA[@]} == 0 && -n "${HF_EXTRA_ARGS:-}" ]]; then
  parsed=$(python3 -c 'import json,os,shlex; print(json.dumps(shlex.split(os.environ["HF_EXTRA_ARGS"])))') || exit 1
  mapfile -d '' -t GLOBAL < <(python3 -c 'import json,sys; [sys.stdout.write(x+"\0") for x in json.loads(sys.argv[1])]' "$parsed")
  EXTRA=("${GLOBAL[@]}")
fi
detect_model_subfolder() {
  local filename="$1"
  local filepath="${2:-}"
  local filename_lower=$(echo "$filename" | tr '[:upper:]' '[:lower:]')

  # Priority 1: Check if filepath already contains a known ComfyUI folder
  if [[ "$filepath" =~ (checkpoints|diffusion_models|unet|loras|text_encoders|clip_vision|clip|vae|upscale_models|latent_upscale_models|controlnet|embeddings|hypernetworks|photomaker|ipadapter) ]]; then
    echo "${BASH_REMATCH[1]}"
    return 0
  fi

  # Priority 2: Detect by filename patterns
  # CLIP vision models (sigclip, vision_encoder, etc.)
  if [[ "$filename_lower" =~ (sigclip|clip.*vision|vision.*patch) ]]; then
    echo "clip_vision"
  # Text encoders (T5, CLIP text, UMTO, Qwen, ByT5, etc.)
  elif [[ "$filename_lower" =~ (t5|qwen|byt5|text_encoder|textenc|umto|xxl.*encoder) ]] && [[ ! "$filename_lower" =~ vision ]]; then
    echo "text_encoders"
  # LoRA models
  elif [[ "$filename_lower" =~ lora ]]; then
    echo "loras"
  # VAE models
  elif [[ "$filename_lower" =~ vae ]]; then
    echo "vae"
  # Latent upscale models
  elif [[ "$filename_lower" =~ latent.*upscal ]]; then
    echo "latent_upscale_models"
  # Upscale models
  elif [[ "$filename_lower" =~ (upscale|esrgan|realesrgan|swinir) ]]; then
    echo "upscale_models"
  # ControlNet
  elif [[ "$filename_lower" =~ controlnet ]]; then
    echo "controlnet"
  # Diffusion models (main models, UNet, etc.)
  elif [[ "$filename_lower" =~ (diffusion|unet|_fp8|_fp16|_bnb|flux|sd15|sdxl|sd3|wan|cogvideo) ]]; then
    echo "diffusion_models"
  # Default to checkpoints for other safetensors/ckpt files
  elif [[ "$filename_lower" =~ \.(safetensors|ckpt|pt|pth)$ ]]; then
    echo "checkpoints"
  else
    echo "checkpoints"
  fi
}


# Validate every URL before creating a directory or invoking a downloader.
for url in "${URLS[@]}"; do
  [[ "$url" =~ ^https://huggingface\.co/([A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+)/(resolve|blob)/([^/?#]+)/([^?#]+)(\?[^#]*)?$ ]] || { echo 'Error: unsupported Hugging Face URL' >&2; exit 1; }
  file="${BASH_REMATCH[4]}"
  [[ "$file" != /* && ! "$file" =~ (^|/)\.\.(/|$) ]] || { echo 'Error: unsafe model path' >&2; exit 1; }
done
if ! $DRY_RUN; then command -v hf >/dev/null || { echo 'Error: install the Hugging Face hf CLI before downloading' >&2; exit 1; }; fi
for url in "${URLS[@]}"; do
  [[ "$url" =~ ^https://huggingface\.co/([A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+)/(resolve|blob)/([^/?#]+)/([^?#]+) ]]
  repo="${BASH_REMATCH[1]}"; revision="${BASH_REMATCH[3]}"; file="${BASH_REMATCH[4]}"
  folder=$(detect_model_subfolder "${file##*/}" "$file")
  target="$BASE_DIR/$folder"
  if $DRY_RUN; then printf 'Would download %s/%s at revision %s into %s\n' "$repo" "$file" "$revision" "$target"; continue; fi
  mkdir -p "$target"
  hf download "$repo" "$file" --revision "$revision" --local-dir "$target" "${EXTRA[@]}"
done
