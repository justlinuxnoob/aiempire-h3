# 👑 AI Empire · H3 Video Cloner (RunPod pod)

Copy any viral short-form video with **your own AI character**, voice included, using MiniMax H3.
A local AI brain (Gemma 4, runs on the pod, **no API key**) watches and listens to the viral clip and
writes the H3 prompt for you.

```
viral video ──▶ 🧠 Gemma 4: breakdown ──▶ 🧠 Gemma 4: H3 prompt ──▶ 🎬 MiniMax H3 (+ your photos/voice) ──▶ 💾 MP4 with audio
```

## What's in this repo
| Path | What it is |
|---|---|
| `docker/` | The pod image: ComfyUI (pinned) + VideoHelperSuite + JupyterLab. **No model weights inside.** |
| `docker/start.sh` | First boot downloads ~66 GB of open models into `/workspace/models` (no Hugging Face token needed) |
| `prompts/` | The AI Empire system prompts (video analyst + two H3 prompt builders) |
| `workflows/` | The two ComfyUI workflows for members (shared through Skool, not baked into the image) |
| `tools/build_workflows.py` | Rebuilds the workflows from `prompts/`. Edit a prompt → run this → done |

## Workflows
- **AI_Empire_H3_Reference.json** (main): face photo + full-body photo (+ optional voice sample) + viral video.
- **AI_Empire_H3_FirstLast.json**: start and/or end image + viral video. Needs `FRAMES_MODE=1`.

## RunPod template settings
| Setting | Value |
|---|---|
| Container image | `aiempire/aiempire-h3:latest` |
| Container disk | 30 GB |
| Volume | **100 GB** network volume at `/workspace` (models download once) |
| HTTP ports | `8188` (ComfyUI), `8888` (JupyterLab) |
| Env (optional) | `FRAMES_MODE=1` (first/last-frame mode, +23 GB) · `JUPYTER_PASSWORD` · `HF_TOKEN` (not required) |

### GPUs (on-demand prices, Oct 2026)
| GPU | VRAM / RAM | $/hr | Verdict |
|---|---|---|---|
| **RTX PRO 6000** | 96 GB / 188 GB | ~$2.09 | ⭐ Recommended: every model fits in VRAM, fastest |
| RTX 6000 Ada | 48 GB / 167 GB | ~$0.84 | 💰 Budget: works by swapping models through RAM |
| L40S | 48 GB / 94 GB | ~$1.09 | OK |
| A100 80 GB | 80 GB / 117-125 GB | ~$1.59 | OK |
| RTX 4090 / 5090 / A6000 | ≤50 GB RAM | — | ❌ Too little system RAM |

## Models (all ungated)
| File | Source | Licence |
|---|---|---|
| `minimax_h3_ref2va_pruned_int8_convrot` (+ `fl2va` with FRAMES_MODE) | Comfy-Org/MiniMax-H3 | MiniMax H3 Community License |
| `qwen3vl_32b_minimax_h3_int8_convrot`, video + audio VAE | Comfy-Org/MiniMax-H3 | MiniMax H3 Community License |
| `minimax_h3_ref2v_turbo_8step_v1.0_768p_comfyui_bf16` (+ fl2v) | lightx2v/Minimax-h3-Turbo | Apache-2.0 (on top of H3) |
| `h3-realism-people-t2v-i2v-r2v` (trigger `r34l1sm`) | fal/MiniMax-H3-Realism-People-LoRA | MiniMax H3 Community License |
| `gemma4_12b_int8_convrot` | Comfy-Org/gemma-4 | Apache-2.0 |

## ⚖️ Licence notice
MiniMax H3 is distributed under the **MiniMax H3 Community License Agreement**
(https://huggingface.co/MiniMaxAI/MiniMax-H3/blob/main/LICENSE). Its territory clause excludes the
**European Union, the United Kingdom, South Korea and the United States**, including use and display
of outputs there. This image does not contain or redistribute H3 weights; they are downloaded by the
user at runtime. Users are responsible for checking the licence covers them.

Third-party code: ComfyUI (GPL-3.0), ComfyUI-VideoHelperSuite (GPL-3.0). Source: links above.

## Updating
- Change a system prompt: edit `prompts/*.txt`, run `python3 tools/build_workflows.py`, commit.
- Change the image: edit `docker/`, push to `main` → GitHub Actions builds and pushes to Docker Hub.

Join: https://www.skool.com/aiempire
