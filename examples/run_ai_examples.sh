
#!/usr/bin/env bash

# SQListo - Practical scientific AI demonstration

set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

cd "$PROJECT_DIR"

PYTHON_BIN="${PYTHON_BIN:-$PROJECT_DIR/.venv/bin/python}"

if [[ ! -x "$PYTHON_BIN" ]]; then
    PYTHON_BIN="$(command -v python3.11 || command -v python)"
fi

DB="$PROJECT_DIR/DBs/azc_dfcz_ub3_z3.db"

OUTPUT_DIR="$PROJECT_DIR/outputs/tutorial/$(date +%Y%m%d_%H%M%S)"

mkdir -p "$OUTPUT_DIR"

if [[ ! -f "$DB" ]]; then
    echo "ERROR: Demonstration database not found."
    echo "Run: bash scripts/download_database.sh"
    exit 1
fi

if ! curl -fsS --max-time 5 \
    http://127.0.0.1:8080/health >/dev/null; then

    echo "ERROR: Local AI server is not available."
    echo "Run: bash start_sqlisto_llama_server.sh"
    exit 1

fi

PASSED=0
FAILED=0

run_example() {

    local number="$1"
    local title="$2"
    local question="$3"

    shift 3

    echo
    echo "================================================"
    echo "EXAMPLE $number - $title"
    echo "================================================"
    echo
    echo "Question: $question"
    echo

    if "$PYTHON_BIN" sqlisto_agent.py \
        "$DB" \
        "$question" \
        --show-plan \
        --show-sql \
        --show-backend \
        --no-llama-fallback \
        --output-dir "$OUTPUT_DIR" \
        "$@" 2>&1 |
        tee "$OUTPUT_DIR/example_${number}.log"
    then
        PASSED=$((PASSED + 1))
    else
        FAILED=$((FAILED + 1))
        echo "Example execution failed."
    fi

}

run_example 01 \
    "Total trajectories" \
    "How many trajectories are stored in the database?"

run_example 02 \
    "Trajectories by molecule" \
    "How many trajectories are stored for each molecule?"

run_example 03 \
    "Trajectories by computational method" \
    "How many trajectories are stored for each method?"

run_example 04 \
    "Average trajectory length" \
    "What is the average number of frames for each molecule?"

run_example 05 \
    "Azaconazole fragmentation reactions" \
    "Show the most frequent fragmentation reactions for Azaconazole."

run_example 06 \
    "Difenoconazole fragmentation reactions" \
    "Show the most frequent fragmentation reactions for Difenoconazole."

run_example 07 \
    "Azaconazole mass spectrum" \
    "Show the theoretical mass spectrum of Azaconazole."

run_example 08 \
    "Azaconazole stored kinetics" \
    "Show the stored global kinetic constants for Azaconazole using uB3LYP."

run_example 09 \
    "Difenoconazole stored kinetics" \
    "Show the stored global kinetic constants for Difenoconazole using uB3LYP."

run_example 10 \
    "Spanish language interaction" \
    "¿Cuántas trayectorias hay para cada molécula?" \
    --lang es

echo
echo "================================================"
echo "SQListo - Scientific Demonstration Report"
echo "================================================"
echo
echo "Completed: $PASSED"
echo "Failed:    $FAILED"
echo
echo "Results:   $OUTPUT_DIR"
echo

if [[ "$FAILED" -ne 0 ]]; then
    exit 1
fi

