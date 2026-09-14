#!/bin/bash
# MVP serve for TaxAgent: Qwen3.6-35B-A3B (35B total / 3B active MoE) on 4 GPUs.
# Deliberately low-footprint: TP=4 on GPUs 1-4 (avoids the busy GPU 0),
# gpu-memory-utilization 0.45, 32k context, low concurrency.
# OpenAI-compatible endpoint on :8011, served model name "qwen".
set -euo pipefail

export CUDA_VISIBLE_DEVICES=${CUDA_VISIBLE_DEVICES:-1,2,3,4}
export PATH="/work/mingze/miniconda3/envs/vllmserve/bin:$PATH"

exec /work/mingze/miniconda3/envs/vllmserve/bin/vllm serve /work/mingze/models/Qwen3.6-35B-A3B \
  --served-model-name qwen \
  --host 127.0.0.1 --port 8011 \
  --tensor-parallel-size 4 \
  --max-model-len 32768 \
  --gpu-memory-utilization 0.45 \
  --max-num-batched-tokens 8192 \
  --max-num-seqs 8 \
  --chat-template /work/mingze/qwen36_nothink_template.jinja \
  --enable-auto-tool-choice --tool-call-parser qwen3_coder
