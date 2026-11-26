# xyz2db/compression.py

# Compression utilities for trajectory data
# This module provides functions to serialize and compress blocks of trajectory data 
# (coordinates, comments, energies,...)

import lzma
from io import BytesIO

import numpy as np

from .config import DEFAULT_LZMA_PRESET


def serialize_block(coords_block: np.ndarray, comments_block, energies_block):
    bio = BytesIO()
    np.savez(
        bio,
        coords=coords_block.astype(np.float32),
        comments=np.array(comments_block, dtype=object),
        energies=np.array(
            [np.nan if e is None else e for e in energies_block],
            dtype=np.float64,
        ),
    )
    raw = bio.getvalue()
    return lzma.compress(raw, preset=DEFAULT_LZMA_PRESET)


def deserialize_block(blob: bytes):
    raw = lzma.decompress(blob)
    bio = BytesIO(raw)
    data = np.load(bio, allow_pickle=True)
    coords = data["coords"]
    comments = data["comments"].tolist()
    energies = data["energies"]
    energies = [None if np.isnan(x) else float(x) for x in energies]
    return coords, comments, energies