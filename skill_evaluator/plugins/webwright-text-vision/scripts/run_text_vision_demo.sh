#!/usr/bin/env bash
set -euo pipefail

MODEL_CONFIG="${WEBWRIGHT_MODEL_CONFIG:-model_codex_oauth_text_vision.yaml}"
TASK="${WEBWRIGHT_TASK:-Search for flights from SEA to JFK on 2026-08-15 to 2026-08-20}"
START_URL="${WEBWRIGHT_START_URL:-https://www.google.com/flights}"
TASK_ID="${WEBWRIGHT_TASK_ID:-demo_text_vision}"
OUTPUT_DIR="${WEBWRIGHT_OUTPUT_DIR:-outputs/text_vision_default}"
EXTRA_CONFIGS="${WEBWRIGHT_EXTRA_CONFIGS:-}"
DEBUG="${WEBWRIGHT_DEBUG:-0}"

command=(python -m webwright.run.cli main \
  -c base.yaml \
  -c "${MODEL_CONFIG}" \
  -t "${TASK}" \
  --start-url "${START_URL}" \
  --task-id "${TASK_ID}" \
  -o "${OUTPUT_DIR}")

if [[ "${DEBUG}" == "1" || "${DEBUG}" == "true" ]]; then
  command+=(--debug)
  export WEBWRIGHT_HEADLESS=0
fi

if [[ -n "${EXTRA_CONFIGS}" ]]; then
  read -r -a extra_config_array <<< "${EXTRA_CONFIGS}"
  for config_spec in "${extra_config_array[@]}"; do
    command+=(-c "${config_spec}")
  done
fi

exec "${command[@]}"
