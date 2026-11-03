#!/bin/bash
docker run -d --name vllm --restart unless-stopped --gpus all --ipc=host -p 8000:8000 \
  -v ~/.cache/huggingface:/root/.cache/huggingface -e HF_HUB_OFFLINE=1 \
  vllm/vllm-openai:muse-glimmer \
  RedHatAI/Muse-Glimmer-30B-INT4 --served-model-name muse-glimmer --generation-config auto \
  --max-model-len 8192 --gpu-memory-utilization 0.95 --max-num-batched-tokens 2048 \
  --max-num-seqs 8 --enable-prefix-caching --enable-auto-tool-choice \
  --tool-call-parser muse_glimmer --reasoning-parser muse_glimmer \
  --limit-mm-per-prompt '{"image":0,"video":0}'
