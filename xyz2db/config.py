# xyz2db/config.py

# Central configuration values for the xyz2db project.
# This file should only contain simple constants and default values.

"""
Central configuration values for the xyz2db project.

This file should only contain simple constants and default values.
Do not put SQL schema definitions or core business logic here.
"""

# -------------------------
# Default file and folder names
# -------------------------
DEFAULT_XYZ_NAME = "coors.xyz"
DEFAULT_INPUT_NAME = "md.in"
DEFAULT_FRAME_CSV_NAME = "frame_data.csv"

# Prefix and formatting for restored trajectory folders
DEFAULT_RUN_DIR_PREFIX = "run_"
DEFAULT_RUN_DIR_DIGITS = 3

# -------------------------
# Storage defaults
# -------------------------
DEFAULT_BLOCK_SIZE = 500
DEFAULT_COMPRESSION = "lzma+npz"
DEFAULT_LZMA_PRESET = 6

# -------------------------
# Default metadata values
# -------------------------
DEFAULT_CHARGE = 0
DEFAULT_SPINMULT = 1

# -------------------------
# Text / formatting defaults
# -------------------------
XYZ_OUTPUT_FLOAT_FORMAT = " .8f"
CSV_FLOAT_FORMAT = ".10f"

# -------------------------
# Parser defaults
# -------------------------
MD_INPUT_COMMENT_PREFIX = "#"

# -------------------------
# CLI examples (optional reference)
# -------------------------
EXAMPLE_DB_NAME = "central.db"
EXAMPLE_RESTORE_DIR = "restored_runs"