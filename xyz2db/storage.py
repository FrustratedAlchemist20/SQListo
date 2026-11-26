# xyz2db/storage.py

# Storage management for xyz2db
# This module provides the main function to store XYZ trajectory files into the SQLite database,
# along with their associated metadata and input files. It handles parsing the XYZ files,
# compressing the trajectory data into blocks, and inserting everything into the database.

import json
import math
import os

import numpy as np

from .chemistry import SYMBOL_TO_Z
from .compression import serialize_block
from .config import DEFAULT_BLOCK_SIZE, DEFAULT_COMPRESSION
from .db import init_db
from .ids import build_db_basename, build_traj_code, make_traj_uid
from .metadata import store_md_input
from .parsing import parse_xyz_multiframe
from .utils import sha256_file


def store_xyz_in_db(
    xyz_path: str,
    db_path: str,
    input_path: str = None,
    block_size: int = DEFAULT_BLOCK_SIZE,
    overwrite: bool = False,
    molecule: str = None,
    isomer: str = None,
    method: str = None,
    energy_label: str = None,
    run_id: int = None,
    original_run_dir: str = None,
):
    if db_path in (None, "", "auto"):
        db_path = build_db_basename(
            molecule=molecule,
            isomer=isomer,
            method=method,
            energy=energy_label,
            lowercase=True,
        )

    xyz_path = os.path.abspath(xyz_path)
    db_path = os.path.abspath(db_path)
    sha256_hex = sha256_file(xyz_path)
    traj_uid = make_traj_uid(xyz_path, sha256_hex)
    traj_code = build_traj_code(
        molecule=molecule,
        isomer=isomer,
        method=method,
        energy=energy_label,
        run_id=run_id,
    )

    natoms, symbols, frames_coords, comments, energies = parse_xyz_multiframe(xyz_path)
    nframes = frames_coords.shape[0]
    atomic_numbers = np.array([SYMBOL_TO_Z[s] for s in symbols], dtype=np.uint8)

    conn = init_db(db_path)
    cur = conn.cursor()

    input_id = None
    if input_path is not None:
        input_id = store_md_input(
            conn,
            input_path,
            natoms=natoms,
            energy_label=energy_label,
        )

    cur.execute("SELECT traj_uid FROM trajectories WHERE sha256 = ?", (sha256_hex,))
    row = cur.fetchone()
    if row is not None and not overwrite:
        conn.close()
        print(f"Ya existe en la base: {row[0]}")
        return row[0]

    if overwrite:
        cur.execute("DELETE FROM trajectories WHERE sha256 = ?", (sha256_hex,))

    extra = {
        "format": "xyz_multiframe",
        "dtype_coords": "float32",
        "block_size": block_size,
    }

    cur.execute(
        """
        INSERT INTO trajectories (
            traj_uid, traj_code, input_id, molecule, isomer, method_label, energy_label, run_id,
            original_run_dir, source_filename, source_abspath, sha256,
            natoms, nframes, atomic_numbers, symbols_json, extra_json
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            traj_uid,
            traj_code,
            input_id,
            molecule,
            isomer,
            method,
            energy_label,
            run_id,
            original_run_dir,
            os.path.basename(xyz_path),
            xyz_path,
            sha256_hex,
            natoms,
            nframes,
            atomic_numbers.tobytes(),
            json.dumps(symbols),
            json.dumps(extra),
        ),
    )

    nblocks = math.ceil(nframes / block_size)
    for block_index in range(nblocks):
        start = block_index * block_size
        end = min((block_index + 1) * block_size, nframes)

        coords_block = frames_coords[start:end]
        comments_block = comments[start:end]
        energies_block = energies[start:end]

        payload = serialize_block(coords_block, comments_block, energies_block)

        cur.execute(
            """
            INSERT INTO frame_blocks (
                traj_uid, block_index, start_frame, end_frame, nframes, compression, payload
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                traj_uid,
                block_index,
                start,
                end - 1,
                end - start,
                DEFAULT_COMPRESSION,
                payload,
            ),
        )

    conn.commit()
    conn.execute("VACUUM")
    conn.close()

    original_size = os.path.getsize(xyz_path)
    db_size = os.path.getsize(db_path)

    print("Stored successfully.")
    print(f"traj_uid       : {traj_uid}")
    print(f"traj_code      : {traj_code}")
    print(f"input_file     : {input_path}")
    print(f"frames         : {nframes}")
    print(f"natoms         : {natoms}")
    print(f"source file    : {xyz_path}")
    print(f"sha256         : {sha256_hex}")
    print(f"xyz size       : {original_size / 1024:.2f} KB")
    print(f"db size        : {db_size / 1024:.2f} KB")
    return traj_uid