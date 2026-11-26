#!/usr/bin/env bash

set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

MODEL_DIR="$PROJECT_DIR/modelos_IA/qwen2.5-coder-1.5b"

MODEL_FILE="qwen2.5-coder-1.5b-instruct-q4_k_m.gguf"

MODEL_URL="https://huggingface.co/Qwen/Qwen2.5-Coder-1.5B-Instruct-GGUF/resolve/main/$MODEL_FILE"

mkdir -p "$MODEL_DIR"

if [[ ! -f "$MODEL_DIR/$MODEL_FILE" ]]; then
    echo "Downloading SQListo language model..."

    curl -fL --retry 3 \
        "$MODEL_URL" \
        -o "$MODEL_DIR/$MODEL_FILE.part"

    mv "$MODEL_DIR/$MODEL_FILE.part" "$MODEL_DIR/$MODEL_FILE"
else
    echo "Model already exists."
fi

echo "Verifying SHA-256 checksum..."

cd "$PROJECT_DIR/modelos_IA"

sha256sum -c SHA256SUMS

echo "Model successfully verified."

