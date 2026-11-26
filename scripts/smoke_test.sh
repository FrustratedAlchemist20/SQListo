
#!/usr/bin/env bash

# ============================================================
# SQListo - Scientific Software Smoke Test
#
# Validates the complete local installation:
# Python, SQLite, llama.cpp, GGUF model and AI assistant.
# ============================================================

set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_DIR"

# ============================================================
# Configuration
# ============================================================

PYTHON_BIN="${PYTHON_BIN:-$PROJECT_DIR/.venv/bin/python}"

if [[ ! -x "$PYTHON_BIN" ]]; then
    PYTHON_BIN="$(command -v python3.11 || command -v python)"
fi

DB_FILE="$PROJECT_DIR/DBs/azc_dfcz_ub3_z3.db"

MODEL_FILE="$PROJECT_DIR/modelos_IA/qwen2.5-coder-1.5b/qwen2.5-coder-1.5b-instruct-q4_k_m.gguf"

LLAMA_DIR="$PROJECT_DIR/.local/llama.cpp/build/bin"

if [[ ! -x "$LLAMA_DIR/llama-server" ]]; then
    LLAMA_DIR="$HOME/llama.cpp/build/bin"
fi

LLAMA_SERVER="${LLAMA_SERVER:-$LLAMA_DIR/llama-server}"
LLAMA_CLI="${LLAMA_CLI:-$LLAMA_DIR/llama-cli}"

HOST="127.0.0.1"
PORT="${SMOKE_TEST_PORT:-18080}"
THREADS="${THREADS:-3}"

SERVER_URL="http://${HOST}:${PORT}"

LOG_DIR="$PROJECT_DIR/outputs/smoke_tests/$(date +%Y%m%d_%H%M%S)_$$"

mkdir -p "$LOG_DIR"

TEMP_DIR="$(mktemp -d)"
TEST_DB="$TEMP_DIR/smoke.db"

PASSED=0
FAILED=0
SKIPPED=0
SERVER_PID=""

# ============================================================
# Terminal colours
# ============================================================

GREEN=""
RED=""
YELLOW=""
BLUE=""
RESET=""

if [[ -t 1 && -z "${NO_COLOR:-}" ]]; then
    GREEN=$'\033[0;32m'
    RED=$'\033[0;31m'
    YELLOW=$'\033[0;33m'
    BLUE=$'\033[0;34m'
    RESET=$'\033[0m'
fi

# ============================================================
# Cleanup
# ============================================================

cleanup() {
    if [[ -n "$SERVER_PID" ]]; then
        kill "$SERVER_PID" 2>/dev/null || true
        wait "$SERVER_PID" 2>/dev/null || true
    fi

    rm -rf -- "$TEMP_DIR"
}

trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

# ============================================================
# Test utilities
# ============================================================

run_test() {
    local id="$1"
    local description="$2"

    shift 2

    local logfile="$LOG_DIR/test_${id}.log"
    local start_time
    local elapsed

    start_time="$(date +%s)"

    printf "[TEST %s] %-48s " "$id" "$description"

    if "$@" >"$logfile" 2>&1; then
        elapsed=$(( $(date +%s) - start_time ))

        printf "%sPASS%s (%ss)\n" \
            "$GREEN" "$RESET" "$elapsed"

        PASSED=$((PASSED + 1))
        return 0
    else
        elapsed=$(( $(date +%s) - start_time ))

        printf "%sFAIL%s (%ss)\n" \
            "$RED" "$RESET" "$elapsed"

        FAILED=$((FAILED + 1))

        echo "  Log: $logfile"

        tail -n 8 "$logfile" || true

        return 1
    fi
}

skip_test() {
    local id="$1"
    local description="$2"

    printf "[TEST %s] %-48s %sSKIP%s\n" \
        "$id" "$description" "$YELLOW" "$RESET"

    SKIPPED=$((SKIPPED + 1))
}

# ============================================================
# Individual tests
# ============================================================

test_python() {
    "$PYTHON_BIN" - <<'PY'
import sys

print("Python:", sys.version)

assert sys.version_info[:2] == (3, 11), \
    "Python 3.11 required"
PY
}

test_dependencies() {
    "$PYTHON_BIN" -m pip check || return 1

    "$PYTHON_BIN" - <<'PY'
import numpy
import pandas
import pyarrow

print("NumPy:", numpy.__version__)
print("Pandas:", pandas.__version__)
print("PyArrow:", pyarrow.__version__)
PY
}

test_compilation() {
    "$PYTHON_BIN" -m compileall -q \
        xyz2db \
        main.py \
        sqlisto_agent.py \
        xyz2db_assistant.py
}

test_regression() {
    "$PYTHON_BIN" -m unittest discover -s tests -v
}

test_model_checksum() {
    [[ -f "$MODEL_FILE" ]] || return 1

    (
        cd "$PROJECT_DIR/modelos_IA" || exit 1
        sha256sum -c SHA256SUMS
    )
}

test_database_integrity() {
    [[ -f "$DB_FILE" ]] || return 1

    (
        cd "$PROJECT_DIR/DBs" || exit 1
        sha256sum -c SHA256SUMS
    ) || return 1

    "$PYTHON_BIN" - "$DB_FILE" "$TEST_DB" <<'PY'
import sqlite3
import sys

from pathlib import Path
from contextlib import closing

source = Path(sys.argv[1]).resolve()
target = Path(sys.argv[2])

with closing(sqlite3.connect(
    source.as_uri() + "?mode=ro", uri=True
)) as conn:

    result = conn.execute(
        "PRAGMA quick_check"
    ).fetchall()

    assert result == [("ok",)], result

    # All subsequent scientific tests use a temporary copy.
    with closing(sqlite3.connect(target)) as dst:
        conn.backup(dst)

print("SHA-256 verification: OK")
print("SQLite integrity: OK")
print("Independent test database created.")
PY
}

test_database_content() {
    "$PYTHON_BIN" - "$TEST_DB" <<'PY'
import sqlite3
import sys

from pathlib import Path
from contextlib import closing

database = Path(sys.argv[1]).resolve()

with closing(sqlite3.connect(
    database.as_uri() + "?mode=ro", uri=True
)) as conn:

    expected = {
        "trajectories": 638,
        "fragment_analysis": 638,
        "fragments": 1137,
        "kinetics_global": 4,
        "kinetics_events": 1276,
    }

    for table, expected_count in expected.items():
        count = conn.execute(
            f"SELECT COUNT(*) FROM {table}"
        ).fetchone()[0]

        print(f"{table}: {count}")

        assert count == expected_count, (
            table, count, expected_count
        )

    frames = conn.execute("""
        SELECT SUM(nframes)
        FROM trajectories
    """).fetchone()[0]

    assert frames == 3560058, frames

    molecules = dict(conn.execute("""
        SELECT molecule, COUNT(*)
        FROM trajectories
        GROUP BY molecule
    """).fetchall())

    assert molecules == {
        "Azaconazole": 313,
        "Difenoconazole": 325,
    }, molecules

    print("Total frames:", frames)
    print("Molecules:", molecules)
PY
}

test_scientific_engine() {
    local result

    result="$(
        "$PYTHON_BIN" main.py summary "$TEST_DB"
    )" || return 1

    printf '%s\n' "$result"

    grep -Eq \
        'Trajectories[[:space:]]*:[[:space:]]*638([[:space:]]|$)' \
        <<< "$result" || return 1

    grep -Eq \
        'Azaconazole[[:space:]]+313([[:space:]]|$)' \
        <<< "$result" || return 1

    grep -Eq \
        'Difenoconazole[[:space:]]+325([[:space:]]|$)' \
        <<< "$result"
}

test_llama_binaries() {
    [[ -x "$LLAMA_SERVER" ]] || return 1
    [[ -x "$LLAMA_CLI" ]] || return 1

    "$LLAMA_SERVER" --version || return 1
    "$LLAMA_CLI" --version
}

test_server() {

    # Do not interfere with an existing inference server.
    "$PYTHON_BIN" - "$HOST" "$PORT" <<'PY' || return 1
import socket
import sys

with socket.socket() as sock:
    sock.bind((sys.argv[1], int(sys.argv[2])))
PY

    "$LLAMA_SERVER" \
        -m "$MODEL_FILE" \
        --host "$HOST" \
        --port "$PORT" \
        -c 8192 \
        --parallel 1 \
        --threads "$THREADS" \
        --threads-batch "$THREADS" \
        >"$LOG_DIR/llama_server.log" 2>&1 &

    SERVER_PID=$!

    for attempt in $(seq 1 120); do

        if ! kill -0 "$SERVER_PID" 2>/dev/null; then
            tail -n 20 "$LOG_DIR/llama_server.log"
            return 1
        fi

        if curl -fsS --max-time 2 \
            "$SERVER_URL/health" >/dev/null 2>&1; then

            echo "Local inference server is ready."
            return 0
        fi

        sleep 1
    done

    echo "Server startup timeout."
    tail -n 20 "$LOG_DIR/llama_server.log"

    return 1
}

test_model_inference() {
    curl -fsS --max-time 300 \
        "$SERVER_URL/v1/chat/completions" \
        -H "Content-Type: application/json" \
        -d '{
            "messages": [
                {
                    "role": "user",
                    "content": "Write an SQL query to count all rows in the trajectories table."
                }
            ],
            "temperature": 0,
            "max_tokens": 128
        }' >"$TEMP_DIR/inference.json" || return 1

    "$PYTHON_BIN" - "$TEMP_DIR/inference.json" <<'PY'
import json
import sys

with open(sys.argv[1], encoding="utf-8") as f:
    response = json.load(f)

content = response["choices"][0]["message"]["content"]

assert content.strip(), "Empty model response"

print(content)

assert "select" in content.casefold()
assert "count" in content.casefold()
assert "trajectories" in content.casefold()
PY
}

run_agent() {
    "$PYTHON_BIN" sqlisto_agent.py \
        "$TEST_DB" "$1" \
        --model "$MODEL_FILE" \
        --llama-bin "$LLAMA_CLI" \
        --llama-url "$SERVER_URL" \
        --output-dir "$LOG_DIR" \
        --show-plan \
        --show-backend \
        --show-sql \
        --no-llama-fallback \
        "${@:2}"
}

test_agent_sql() {
    local result

    result="$(run_agent \
        "How many trajectories are stored for each molecule?"
    )" || return 1

    printf '%s\n' "$result"

    grep -Eiq 'GROUP BY' <<< "$result" || return 1

    grep -Eq \
        'Azaconazole[[:space:]]+313([[:space:]]|$)' \
        <<< "$result" || return 1

    grep -Eq \
        'Difenoconazole[[:space:]]+325([[:space:]]|$)' \
        <<< "$result"
}

test_agent_router() {
    local result

    result="$(run_agent \
        "Show the most frequent fragmentation reactions for Azaconazole." \
        --force-router
    )" || return 1

    printf '%s\n' "$result"

    grep -Eq \
        '"routing"[[:space:]]*:[[:space:]]*"llm_router"' \
        <<< "$result" || return 1

    grep -Eq \
        '"action"[[:space:]]*:[[:space:]]*"reaction_summary"' \
        <<< "$result" || return 1

    grep -q 'rxn_336015104b49' <<< "$result"
}

test_agent_kinetics() {
    local result

    result="$(run_agent \
        "Show the stored global kinetic constants for Azaconazole using uB3LYP."
    )" || return 1

    printf '%s\n' "$result"

    grep -Eq \
        'Azaconazole.*uB3LYP.*5\.43377[0-9]*' \
        <<< "$result" || return 1

    grep -q 'MLE' <<< "$result"
}

# ============================================================
# Run smoke tests
# ============================================================

START_TIME="$(date +%s)"

echo
echo "============================================================"
echo "                SQListo - Smoke Test"
echo "============================================================"
echo
echo "Project:  $PROJECT_DIR"
echo "Python:   $PYTHON_BIN"
echo "Database: $DB_FILE"
echo "Model:    $MODEL_FILE"
echo "Logs:     $LOG_DIR"
echo "Server:   $SERVER_URL"
echo
echo "------------------------------------------------------------"

run_test 01 "Python environment" \
    test_python || true

run_test 02 "Python dependencies" \
    test_dependencies || true

run_test 03 "Python source compilation" \
    test_compilation || true

run_test 04 "Regression tests" \
    test_regression || true

MODEL_OK=false
DB_OK=false
LLAMA_OK=false
SERVER_OK=false

if run_test 05 "GGUF model SHA-256" \
    test_model_checksum; then

    MODEL_OK=true
fi

if run_test 06 "SQLite checksum and integrity" \
    test_database_integrity; then

    DB_OK=true
fi

if [[ "$DB_OK" == true ]]; then

    run_test 07 "Scientific dataset content" \
        test_database_content || true

    run_test 08 "XYZ2DB scientific engine" \
        test_scientific_engine || true

else

    skip_test 07 "Scientific dataset content"
    skip_test 08 "XYZ2DB scientific engine"

fi

if run_test 09 "llama.cpp executables" \
    test_llama_binaries; then

    LLAMA_OK=true
fi

if [[ "$MODEL_OK" == true && "$LLAMA_OK" == true ]]; then

    if run_test 10 "Local inference server" \
        test_server; then

        SERVER_OK=true
    fi

else

    skip_test 10 "Local inference server"

fi

if [[ "$SERVER_OK" == true ]]; then

    run_test 11 "Direct Qwen model inference" \
        test_model_inference || true

else

    skip_test 11 "Direct Qwen model inference"

fi

if [[ "$SERVER_OK" == true && "$DB_OK" == true ]]; then

    run_test 12 "SQListo SQL queries" \
        test_agent_sql || true

    run_test 13 "SQListo LLM tool routing" \
        test_agent_router || true

    run_test 14 "SQListo stored kinetic constants" \
        test_agent_kinetics || true

else

    skip_test 12 "SQListo SQL queries"
    skip_test 13 "SQListo LLM tool routing"
    skip_test 14 "SQListo stored kinetic constants"

fi

# ============================================================
# Final report
# ============================================================

TOTAL=$((PASSED + FAILED + SKIPPED))
ELAPSED=$(( $(date +%s) - START_TIME ))

{
    echo
    echo "============================================================"
    echo "                 SQListo - Final Report"
    echo "============================================================"
    echo
    echo "Total tests:   $TOTAL"
    echo "Passed:        $PASSED"
    echo "Failed:        $FAILED"
    echo "Skipped:       $SKIPPED"
    echo "Elapsed time:  ${ELAPSED}s"
    echo
    echo "Logs: $LOG_DIR"
    echo

    if [[ "$FAILED" -eq 0 && "$SKIPPED" -eq 0 ]]; then
        echo "RESULT: ALL TESTS PASSED"
    else
        echo "RESULT: VALIDATION INCOMPLETE"
    fi

    echo "============================================================"

} | tee "$LOG_DIR/summary.txt"

if [[ "$FAILED" -ne 0 || "$SKIPPED" -ne 0 ]]; then
    exit 1
fi

exit 0

