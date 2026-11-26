
#!/usr/bin/env bash

# ============================================================
# SQListo - Automated Linux installer
# ============================================================

set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_DIR"

PYTHON_BIN="${PYTHON_BIN:-python3.11}"
VENV_DIR="$PROJECT_DIR/.venv"

LLAMA_DIR="$PROJECT_DIR/.local/llama.cpp"
LLAMA_REPO="https://github.com/ggml-org/llama.cpp.git"
LLAMA_COMMIT="9724f664e803e70eb8d046a3fac411122ad42ff7"

BUILD_JOBS="${BUILD_JOBS:-2}"

# ============================================================
# Utilities
# ============================================================

fail() {
    echo "ERROR: $1" >&2
    exit 1
}

section() {
    echo
    echo "================================================"
    echo "$1"
    echo "================================================"
}

# ============================================================
# Welcome
# ============================================================

section "SQListo - Scientific Software Installer"

echo "Installation directory: $PROJECT_DIR"
echo "Python executable: $PYTHON_BIN"
echo "Inference backend: CPU"
echo

[[ "$(uname -s)" == "Linux" ]] \
    || fail "This installer currently supports Linux."

# ============================================================
# 1. System requirements
# ============================================================

section "[1/7] Checking system requirements"

MISSING=()

for tool in git curl cmake make gcc g++ sha256sum "$PYTHON_BIN"; do
    if ! command -v "$tool" >/dev/null 2>&1; then
        MISSING+=("$tool")
    fi
done

if [[ "${#MISSING[@]}" -gt 0 ]]; then

    echo "Missing commands: ${MISSING[*]}"
    echo
    echo "Install the required system packages first."
    echo
    echo "Rocky Linux / Fedora:"
    echo "sudo dnf install git curl cmake make gcc gcc-c++ python3.11"
    echo
    echo "Ubuntu / Debian:"
    echo "sudo apt install git curl cmake build-essential python3-venv"
    echo "Python 3.11 must also be available."

    exit 1

fi

"$PYTHON_BIN" -c '
import sys
assert sys.version_info[:2] == (3, 11), "Python 3.11 required"
'

echo "System requirements: OK"

# ============================================================
# 2. Python environment
# ============================================================

section "[2/7] Preparing Python environment"

if [[ ! -d "$VENV_DIR" ]]; then
    "$PYTHON_BIN" -m venv "$VENV_DIR"
fi

source "$VENV_DIR/bin/activate"

python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m pip check

echo "Python environment: OK"

# ============================================================
# 3. llama.cpp
# ============================================================

section "[3/7] Installing llama.cpp"

mkdir -p "$PROJECT_DIR/.local"

if [[ ! -d "$LLAMA_DIR" ]]; then

    git clone --no-checkout "$LLAMA_REPO" "$LLAMA_DIR"
    git -C "$LLAMA_DIR" checkout --detach "$LLAMA_COMMIT"

else

    CURRENT_COMMIT="$(git -C "$LLAMA_DIR" rev-parse HEAD)"

    [[ "$CURRENT_COMMIT" == "$LLAMA_COMMIT" ]] \
        || fail "Existing llama.cpp installation has a different commit."

fi

if [[ ! -x "$LLAMA_DIR/build/bin/llama-server" ]] \
    || [[ ! -x "$LLAMA_DIR/build/bin/llama-cli" ]]; then

    cmake \
        -S "$LLAMA_DIR" \
        -B "$LLAMA_DIR/build" \
        -DCMAKE_BUILD_TYPE=Release \
        -DLLAMA_CURL=OFF \
        -DLLAMA_BUILD_SERVER=ON

    cmake --build "$LLAMA_DIR/build" \
        --config Release \
        --parallel "$BUILD_JOBS" \
        --target llama-server llama-cli

else

    echo "llama.cpp is already installed."

fi

[[ -x "$LLAMA_DIR/build/bin/llama-server" ]] \
    || fail "llama-server was not built."

[[ -x "$LLAMA_DIR/build/bin/llama-cli" ]] \
    || fail "llama-cli was not built."

"$LLAMA_DIR/build/bin/llama-server" --version

# ============================================================
# 4. Language model
# ============================================================

section "[4/7] Downloading language model"

bash scripts/download_model.sh

# ============================================================
# 5. Demonstration database
# ============================================================

section "[5/7] Downloading demonstration database"

bash scripts/download_database.sh

# ============================================================
# 6. Software validation
# ============================================================

section "[6/7] Running software validation"

python -m compileall -q \
    xyz2db \
    main.py \
    sqlisto_agent.py \
    xyz2db_assistant.py

python -m unittest discover -s tests -v

python main.py summary DBs/azc_dfcz_ub3_z3.db

# ============================================================
# 7. Installation completed
# ============================================================

section "[7/7] Installation completed"

echo "SQListo successfully installed."
echo
echo "To activate the Python environment:"
echo
echo "  source .venv/bin/activate"
echo
echo "To start the local AI server:"
echo
echo "  bash start_sqlisto_llama_server.sh"
echo
echo "To display available commands:"
echo
echo "  python main.py --help"
echo
echo "To query the demonstration database:"
echo
echo '  python sqlisto_agent.py DBs/azc_dfcz_ub3_z3.db "How many trajectories are stored for each molecule?"'
echo

