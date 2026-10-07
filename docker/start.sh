#!/bin/bash
# AI Empire · H3 Video Cloner pod start-up
#  1. JupyterLab on 8888 (upload photos / videos while models download)
#  2. downloads the models into /workspace/models (skipped if already there)
#  3. starts ComfyUI on 8188
#
# Environment variables (all optional):
#   FRAMES_MODE=1      also download the first/last-frame model (+23 GB)
#   HF_TOKEN=hf_...    NOT required (every repo is open); only speeds up downloads if Hugging Face rate-limits you
#   JUPYTER_PASSWORD   protects JupyterLab (empty = no password)
set -e

WS=/workspace
M=$WS/models
mkdir -p "$M/diffusion_models" "$M/loras" "$M/text_encoders" "$M/vae" "$WS/output" "$WS/input"
cp -n /opt/aiempire/input/* "$WS/input/" 2>/dev/null || true

nohup jupyter lab --allow-root --no-browser --ip=0.0.0.0 --port=8888 \
  --ServerApp.token="${JUPYTER_PASSWORD:-}" --ServerApp.password="" \
  --ServerApp.allow_origin='*' --ServerApp.root_dir="$WS" \
  --FileContentsManager.delete_to_trash=False \
  > "$WS/jupyter.log" 2>&1 &
echo "[AI Empire] 📁 JupyterLab on port 8888"

AUTH=()
if [ -n "${HF_TOKEN:-}" ]; then AUTH=(--header="Authorization: Bearer ${HF_TOKEN}"); fi

fetch() {
  local dir="$1" name="$2" url="$3"
  if [ -s "$dir/$name" ] && [ ! -f "$dir/$name.aria2" ]; then
    echo "[AI Empire] ✔ $name already downloaded"
    return 0
  fi
  echo "[AI Empire] ⬇ downloading $name ..."
  aria2c -x 16 -s 16 -k 1M -c --console-log-level=warn --summary-interval=30 \
    "${AUTH[@]}" -d "$dir" -o "$name" "$url"
}

HF=https://huggingface.co
H3="$HF/Comfy-Org/MiniMax-H3/resolve/main"
TURBO="$HF/lightx2v/Minimax-h3-Turbo/resolve/main"

echo "[AI Empire] ⏳ First boot downloads ~66 GB (about 10-20 min). Restarts skip this."
PIDS=""
# MiniMax H3 reference mode (Comfy-Org repack, MiniMax H3 Community License)
fetch "$M/diffusion_models" "minimax_h3_ref2va_pruned_int8_convrot.safetensors" "$H3/diffusion_models/minimax_h3_ref2va_pruned_int8_convrot.safetensors" & PIDS="$PIDS $!"
fetch "$M/text_encoders" "qwen3vl_32b_minimax_h3_int8_convrot.safetensors" "$H3/text_encoders/qwen3vl_32b_minimax_h3_int8_convrot.safetensors" & PIDS="$PIDS $!"
fetch "$M/vae" "minimax_h3_video_vae_fp16.safetensors" "$H3/vae/minimax_h3_video_vae_fp16.safetensors" & PIDS="$PIDS $!"
fetch "$M/vae" "minimax_h3_audio_vae_fp32.safetensors" "$H3/vae/minimax_h3_audio_vae_fp32.safetensors" & PIDS="$PIDS $!"
# Turbo 8-step LoRA for reference mode (lightx2v, Apache-2.0)
fetch "$M/loras" "minimax_h3_ref2v_turbo_8step_v1.0_768p_comfyui_bf16.safetensors" "$TURBO/minimax_h3_ref2v_turbo_8step_v1.0_768p_comfyui_bf16.safetensors" & PIDS="$PIDS $!"
# Realism people LoRA (fal)
fetch "$M/loras" "h3-realism-people-t2v-i2v-r2v.safetensors" "$HF/fal/MiniMax-H3-Realism-People-LoRA/resolve/main/h3-realism-people-t2v-i2v-r2v.safetensors" & PIDS="$PIDS $!"
# AI brain: Gemma 4 12B, watches + listens to the viral video (Apache-2.0)
fetch "$M/text_encoders" "gemma4_12b_int8_convrot.safetensors" "$HF/Comfy-Org/gemma-4/resolve/main/text_encoders/gemma4_12b_int8_convrot.safetensors" & PIDS="$PIDS $!"

if [ "${FRAMES_MODE:-0}" = "1" ]; then
  fetch "$M/diffusion_models" "minimax_h3_fl2va_pruned_int8_convrot.safetensors" "$H3/diffusion_models/minimax_h3_fl2va_pruned_int8_convrot.safetensors" & PIDS="$PIDS $!"
  fetch "$M/loras" "minimax_h3_fl2v_turbo_8step_v1.0_768p_comfyui_bf16.safetensors" "$TURBO/minimax_h3_fl2v_turbo_8step_v1.0_768p_comfyui_bf16.safetensors" & PIDS="$PIDS $!"
fi

for p in $PIDS; do
  wait "$p" || { echo "[AI Empire] 🛑 a model failed to download. Restart the pod to resume (finished files are kept)."; exit 1; }
done

echo "[AI Empire] ✅ Models ready. Starting ComfyUI on port 8188..."
cd /opt/ComfyUI
exec python main.py --listen 0.0.0.0 --port 8188 \
  --output-directory "$WS/output" --input-directory "$WS/input" ${COMFY_ARGS}
