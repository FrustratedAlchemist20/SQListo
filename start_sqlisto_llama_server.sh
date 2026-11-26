#!/usr/bin/env bash

# ============================================================
# SQListo - Inicio sencillo de llama-server
# Modifica únicamente las variables de esta sección.
# ============================================================

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

LLAMA_SERVER="${LLAMA_SERVER:-$HOME/llama.cpp/build/bin/llama-server}"

MODEL="${MODEL:-$PROJECT_DIR/modelos_IA/qwen2.5-coder-1.5b/qwen2.5-coder-1.5b-instruct-q4_k_m.gguf}"


HOST="127.0.0.1"
PORT="8080"

CONTEXT_SIZE="8192"
PARALLEL_REQUESTS="1"
THREADS="3"
BATCH_THREADS="3"

LOG_FILE="$HOME/llama_server_sqListo.log"
PID_FILE="$HOME/llama_server_sqListo.pid"

# ============================================================
# No es necesario modificar nada a partir de aquí.
# ============================================================

set -u

SERVER_URL="http://${HOST}:${PORT}"
HEALTH_URL="${SERVER_URL}/health"

print_header() {
    echo
    echo "=============================================="
    echo "           SQListo llama-server"
    echo "=============================================="
}

fail() {
    echo "ERROR: $1" >&2
    exit 1
}

is_server_ready() {
    curl --silent --fail --max-time 2 "$HEALTH_URL" >/dev/null 2>&1
}

print_header

command -v curl >/dev/null 2>&1 \
    || fail "No se encuentra curl en el sistema."

[[ -x "$LLAMA_SERVER" ]] \
    || fail "No se encuentra llama-server o no es ejecutable: $LLAMA_SERVER"

[[ -f "$MODEL" ]] \
    || fail "No se encuentra el modelo GGUF: $MODEL"

if is_server_ready; then
    echo "El servidor ya está funcionando."
    echo "Dirección: $SERVER_URL"
    exit 0
fi

if [[ -f "$PID_FILE" ]]; then
    OLD_PID="$(cat "$PID_FILE" 2>/dev/null || true)"

    if [[ -n "${OLD_PID:-}" ]] && kill -0 "$OLD_PID" 2>/dev/null; then
        echo "Existe un proceso anterior con PID $OLD_PID."
        echo "Esperando a que responda el servidor..."
    else
        rm -f "$PID_FILE"
    fi
fi

if [[ ! -f "$PID_FILE" ]]; then
    echo "Iniciando llama-server..."
    echo "Modelo: $MODEL"
    echo "Dirección: $SERVER_URL"
    echo "Log: $LOG_FILE"
    echo

    nohup "$LLAMA_SERVER" \
        -m "$MODEL" \
        --host "$HOST" \
        --port "$PORT" \
        -c "$CONTEXT_SIZE" \
        --parallel "$PARALLEL_REQUESTS" \
        --threads "$THREADS" \
        --threads-batch "$BATCH_THREADS" \
        >"$LOG_FILE" 2>&1 &

    SERVER_PID=$!
    echo "$SERVER_PID" > "$PID_FILE"

    echo "Proceso iniciado con PID $SERVER_PID."
fi

echo "Esperando a que el modelo termine de cargar..."

for attempt in $(seq 1 60); do
    if is_server_ready; then
        echo
        echo "Servidor listo."
        echo "Dirección: $SERVER_URL"
        echo "PID: $(cat "$PID_FILE")"
        echo "Log: $LOG_FILE"
        echo
        echo "Ya puedes ejecutar SQListo."
        exit 0
    fi

    if [[ -f "$PID_FILE" ]]; then
        CURRENT_PID="$(cat "$PID_FILE" 2>/dev/null || true)"

        if [[ -n "${CURRENT_PID:-}" ]] && ! kill -0 "$CURRENT_PID" 2>/dev/null; then
            rm -f "$PID_FILE"
            echo
            echo "El servidor se cerró durante el arranque."
            echo "Últimas líneas del log:"
            tail -n 20 "$LOG_FILE" 2>/dev/null || true
            exit 1
        fi
    fi

    printf "."
    sleep 1
done

echo
echo "El servidor no respondió después de 60 segundos."
echo "Revisa el log:"
echo "  $LOG_FILE"
exit 1
