# xyz2db/utils.py

# Utility functions for xyz2db
# This dependency is used for hashing files to ensure data integrity and avoid duplicates in the database.

import hashlib

def sha256_file(filepath: str, chunk_size: int = 1024 * 1024) -> str:
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()