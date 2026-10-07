# AI Empire · H3 Video Cloner pod
# ComfyUI + VideoHelperSuite. NO model weights inside: start.sh downloads them
# on first boot into /workspace (attach a network volume so it happens once).
FROM nvidia/cuda:12.8.1-base-ubuntu24.04

ENV DEBIAN_FRONTEND=noninteractive \
    PIP_NO_CACHE_DIR=1 \
    PYTHONUNBUFFERED=1 \
    PATH=/opt/venv/bin:$PATH

# ---- layer 1: system packages (rarely changes) ----
RUN apt-get update && apt-get install -y --no-install-recommends \
        python3 python3-venv python3-dev build-essential \
        git aria2 ffmpeg wget curl ca-certificates libgl1 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

RUN python3 -m venv /opt/venv && pip install --upgrade pip wheel setuptools

# ---- layer 2: PyTorch, the heavy download (CUDA 12.8: 4090, 5090, L40S, A100, H100, RTX PRO 6000) ----
RUN pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu128

# ---- layer 3: ComfyUI pinned to the commit the workflows were validated on (v0.39 line, has MiniMax H3 + Gemma 4) ----
ARG COMFY_REF=c9d8a6e69c4b5ab7fa0f789e7b988c172cd31fc9
RUN git clone https://github.com/Comfy-Org/ComfyUI.git /opt/ComfyUI \
    && cd /opt/ComfyUI && git checkout ${COMFY_REF} \
    && pip install -r requirements.txt

# ---- layer 4: tools ----
RUN pip install jupyterlab

# ---- layer 5: custom nodes (pinned so an update can't break members' pods) ----
# VideoHelperSuite (GPL-3.0): loads the viral video at exactly 24 fps for the AI brain
RUN cd /opt/ComfyUI/custom_nodes \
    && git clone https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite.git \
    && git -C ComfyUI-VideoHelperSuite checkout 4d907bee61e92c2e65af3bd6383a4e4d356126d1 \
    && pip install -r ComfyUI-VideoHelperSuite/requirements.txt

# ---- layer 6: small AI Empire files (changes most often, so it sits last) ----
COPY docker/extra_model_paths.yaml /opt/ComfyUI/extra_model_paths.yaml
COPY docker/make_assets.py /opt/aiempire/make_assets.py
RUN python /opt/aiempire/make_assets.py /opt/aiempire/input
COPY docker/start.sh /start.sh
RUN chmod +x /start.sh

# boot ComfyUI once on CPU at build time: a broken node import fails the BUILD, not a member's pod
RUN cd /opt/ComfyUI && (timeout 300 python main.py --quick-test-for-ci --cpu 2>&1 | tee /tmp/quicktest.log || true) \
    && ! grep -E "IMPORT FAILED.*(VideoHelperSuite|nodes_textgen|nodes_minimax_h3|nodes_string|nodes_logic|nodes_math)" /tmp/quicktest.log \
    && rm -f /tmp/quicktest.log

EXPOSE 8188 8888
CMD ["/start.sh"]
