
#!/usr/bin/env bash

# ============================================================
# SQListo - Demonstration database downloader
# ============================================================

set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

REPOSITORY="FrustratedAlchemist20/SQListo"
RELEASE_TAG="v0.1.0"

DB_DIR="$PROJECT_DIR/DBs"
DB_FILE="azc_dfcz_ub3_z3.db"
CHECKSUM_FILE="SHA256SUMS"

RELEASE_URL="https://github.com/$REPOSITORY/releases/download/$RELEASE_TAG"

# ============================================================
# Utility functions
# ============================================================

fail() {
    echo "ERROR: $1" >&2
    exit 1
}

download_asset() {
    local filename="$1"
    local destination="$2"

    # Try public download first.
    if curl -fsSL --retry 3 \
        "$RELEASE_URL/$filename" \
        -o "$destination"; then
        return 0
    fi

    # Fall back to authenticated GitHub CLI.
    command -v gh >/dev/null 2>&1 \
        || fail "Private repository. Install GitHub CLI (gh)."

    gh auth status --hostname github.com >/dev/null 2>&1 \
        || fail "Run 'gh auth login' first."

    gh release download "$RELEASE_TAG" \
        --repo "$REPOSITORY" \
        --pattern "$filename" \
        --output "$destination" \
        --clobber
}

# ============================================================
# Preliminary checks
# ============================================================

echo "=============================================="
echo "       SQListo Database Downloader"
echo "=============================================="
echo
echo "Repository: $REPOSITORY"
echo "Release:    $RELEASE_TAG"
echo "Database:   $DB_FILE"
echo

for tool in curl python sha256sum; do
    command -v "$tool" >/dev/null 2>&1 \
        || fail "Required command not found: $tool"
done

mkdir -p "$DB_DIR"

TARGET="$DB_DIR/$DB_FILE"

# Never overwrite symbolic links.
if [[ -L "$TARGET" ]]; then
    fail "The destination is a symbolic link. Remove the link or use a clean installation."
fi

# Temporary download directory.
TEMP_DIR="$(mktemp -d "$DB_DIR/.download.XXXXXX")"

trap 'rm -rf -- "$TEMP_DIR"' EXIT

# ============================================================
# Download checksum
# ============================================================

echo "Downloading SHA-256 checksum..."

download_asset "$CHECKSUM_FILE" \
    "$TEMP_DIR/$CHECKSUM_FILE"

EXPECTED_HASH="$(
    awk -v file="$DB_FILE" \
        '$2 == file {print $1}' \
        "$TEMP_DIR/$CHECKSUM_FILE"
)"

[[ "$EXPECTED_HASH" =~ ^[a-fA-F0-9]{64}$ ]] \
    || fail "Invalid SHA-256 checksum."

# ============================================================
# Check existing database
# ============================================================

if [[ -f "$TARGET" ]]; then

    echo "Database already exists."
    echo "Verifying existing database..."

    CURRENT_HASH="$(sha256sum "$TARGET" | awk '{print $1}')"

    if [[ "$CURRENT_HASH" == "$EXPECTED_HASH" ]]; then
        echo "Existing database is correct."
        echo "No download required."
        exit 0
    fi

    fail "Existing database differs from the release. Move it manually before downloading."
fi

# ============================================================
# Download database
# ============================================================

echo
echo "Downloading demonstration database..."

download_asset "$DB_FILE" \
    "$TEMP_DIR/$DB_FILE"

# ============================================================
# Verify SHA-256
# ============================================================

echo
echo "Verifying SHA-256 checksum..."

DOWNLOADED_HASH="$(
    sha256sum "$TEMP_DIR/$DB_FILE" | awk '{print $1}'
)"

[[ "$DOWNLOADED_HASH" == "$EXPECTED_HASH" ]] \
    || fail "SHA-256 checksum mismatch."

echo "SHA-256 verification: OK"

# ============================================================
# Verify SQLite integrity
# ============================================================

echo
echo "Checking SQLite database integrity..."

python - "$TEMP_DIR/$DB_FILE" <<'PY'
import sqlite3
import sys

from pathlib import Path
from contextlib import closing

database = Path(sys.argv[1]).resolve()

with closing(
    sqlite3.connect(
        database.as_uri() + "?mode=ro",
        uri=True
    )
) as conn:

    integrity = conn.execute(
        "PRAGMA quick_check"
    ).fetchall()

    if integrity != [("ok",)]:
        raise RuntimeError(
            f"Database integrity check failed: {integrity}"
        )

    trajectories = conn.execute(
        "SELECT COUNT(*) FROM trajectories"
    ).fetchone()[0]

    if trajectories != 638:
        raise RuntimeError(
            f"Unexpected trajectory count: {trajectories}"
        )

    print("SQLite integrity: OK")
    print(f"Stored trajectories: {trajectories}")
PY

# ============================================================
# Install verified database without overwriting
# ============================================================

mv -n "$TEMP_DIR/$DB_FILE" "$TARGET"

[[ ! -e "$TEMP_DIR/$DB_FILE" ]] \
    || fail "Destination appeared during download."

cp "$TEMP_DIR/$CHECKSUM_FILE" \
    "$DB_DIR/$CHECKSUM_FILE"

echo
echo "=============================================="
echo "Database successfully installed."
echo "=============================================="
echo
echo "Location: $TARGET"
echo "Release:  $RELEASE_TAG"
echo "SHA-256:  $EXPECTED_HASH"
echo

du -h "$TARGET"

