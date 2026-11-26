# xyz2db/restore.py

# Restoration utilities for xyz2db
# This module provides functions
# to restore XYZ trajectory files and their associated metadata from the SQLite database.

import json
import os
import sqlite3

import numpy as np

from .compression import deserialize_block
from .config import (
    DEFAULT_FRAME_CSV_NAME,
    DEFAULT_RUN_DIR_DIGITS,
    DEFAULT_RUN_DIR_PREFIX,
    DEFAULT_XYZ_NAME,
)
from .export import export_frame_data_csv


def restore_single_input_file_from_db(db_path: str, output_dir: str):
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    cur.execute(
        """
        SELECT input_filename, raw_input_text
        FROM md_inputs
        ORDER BY created_at, input_id
        LIMIT 1
        """
    )
    row = cur.fetchone()
    conn.close()

    if row is None:
        return None

    input_filename, raw_input_text = row

    if not input_filename or raw_input_text is None:
        return None

    os.makedirs(output_dir, exist_ok=True)
    output_input = os.path.join(output_dir, input_filename)

    with open(output_input, "w", encoding="utf-8") as f:
        f.write(raw_input_text)

    return output_input


def show_input_from_db(db_path: str, traj_uid: str):
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    cur.execute(
        """
        SELECT
            t.traj_uid,
            t.traj_code,
            t.molecule,
            t.isomer,
            t.method_label,
            t.energy_label,
            m.input_filename,
            m.raw_input_text,
            m.energy_label_factor,
            m.energy_temperature_K,
            m.energy_kcal_mol,
            m.zpe_kcal_mol,
            m.dof
        FROM trajectories t
        LEFT JOIN md_inputs m ON t.input_id = m.input_id
        WHERE t.traj_uid = ?
        """,
        (traj_uid,),
    )

    row = cur.fetchone()
    conn.close()

    if row is None:
        raise ValueError(f"No trajectory found for traj_uid='{traj_uid}'")

    (
        traj_uid_val,
        traj_code,
        molecule,
        isomer,
        method_label,
        energy_label,
        input_filename,
        raw_input_text,
        energy_label_factor,
        energy_temperature_K,
        energy_kcal_mol,
        zpe_kcal_mol,
        dof,
    ) = row

    if raw_input_text is None:
        raise ValueError(f"No stored input found for traj_uid='{traj_uid}'")

    print(f"traj_uid          : {traj_uid_val}")
    print(f"traj_code         : {traj_code}")
    print(f"molecule          : {molecule}")
    print(f"isomer            : {isomer}")
    print(f"method            : {method_label}")
    print(f"energy_label      : {energy_label}")
    print(f"input_filename    : {input_filename}")
    print()

    print("Energy summary")
    print("--------------")
    print(f"energy_label_factor : {energy_label_factor}")
    print(f"energy_temperature_K: {energy_temperature_K}")
    print(f"energy_kcal_mol    : {energy_kcal_mol}")
    print(f"zpe_kcal_mol       : {zpe_kcal_mol}")
    print(f"dof                : {dof}")
    print()

    print("Raw input")
    print("---------")
    print(raw_input_text)

def restore_input_for_trajectory(db_path: str, traj_uid: str, output_path: str = None):
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    cur.execute(
        """
        SELECT
            m.input_filename,
            m.raw_input_text
        FROM trajectories t
        LEFT JOIN md_inputs m ON t.input_id = m.input_id
        WHERE t.traj_uid = ?
        """,
        (traj_uid,),
    )
    row = cur.fetchone()
    conn.close()

    if row is None:
        raise ValueError(f"No trajectory found for traj_uid='{traj_uid}'")

    input_filename, raw_input_text = row

    if raw_input_text is None:
        raise ValueError(f"No stored input found for traj_uid='{traj_uid}'")

    if output_path is None:
        output_path = input_filename if input_filename else "restored_input.inp"

    output_dir = os.path.dirname(output_path)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(raw_input_text)

    print(f"Restored input -> {os.path.abspath(output_path)}")
    return output_path

def restore_xyz_from_db(db_path: str, traj_uid: str, output_xyz: str):
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    cur.execute(
        """
        SELECT natoms, atomic_numbers, symbols_json, nframes
        FROM trajectories
        WHERE traj_uid = ?
        """,
        (traj_uid,),
    )
    row = cur.fetchone()
    if row is None:
        conn.close()
        raise ValueError(f"No trajectory found for traj_uid='{traj_uid}'")

    natoms, atomic_numbers_blob, symbols_json, nframes = row
    atomic_numbers = np.frombuffer(atomic_numbers_blob, dtype=np.uint8)
    symbols = json.loads(symbols_json)

    if len(symbols) != natoms or len(atomic_numbers) != natoms:
        conn.close()
        raise ValueError("Inconsistent stored atomic information.")

    cur.execute(
        """
        SELECT block_index, start_frame, end_frame, payload
        FROM frame_blocks
        WHERE traj_uid = ?
        ORDER BY block_index
        """,
        (traj_uid,),
    )
    blocks = cur.fetchall()
    conn.close()

    output_dir = os.path.dirname(output_xyz)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)

    recovered_frames = 0
    with open(output_xyz, "w", encoding="utf-8") as out:
        for block_index, start_frame, end_frame, payload in blocks:
            coords_block, comments_block, energies_block = deserialize_block(payload)

            expected_n = end_frame - start_frame + 1
            if coords_block.shape[0] != expected_n:
                raise ValueError(
                    f"Corrupted block {block_index}: unexpected number of frames."
                )

            for iframe in range(coords_block.shape[0]):
                out.write(f"{natoms}\n")
                comment = comments_block[iframe] if comments_block[iframe] is not None else ""
                out.write(f"{comment}\n")
                coords = coords_block[iframe]
                for sym, (x, y, z) in zip(symbols, coords):
                    out.write(f"{sym:<2s} {x: .8f} {y: .8f} {z: .8f}\n")
                recovered_frames += 1

    print("Restoration completed.")
    print(f"traj_uid     : {traj_uid}")
    print(f"frames       : {recovered_frames}")
    print(f"output xyz   : {os.path.abspath(output_xyz)}")


def restore_single_run_from_db(db_path: str, traj_uid: str):
    """
    Restore one trajectory into its original run folder name stored in the database.

    Example:
        python main.py restore my.db traj_xxxxx

    Output:
        run_350/
          coors.xyz
          frame_data.csv
    """
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    cur.execute(
        """
        SELECT original_run_dir, source_filename
        FROM trajectories
        WHERE traj_uid = ?
        """,
        (traj_uid,),
    )
    row = cur.fetchone()
    conn.close()

    if row is None:
        raise ValueError(f"No trajectory found for traj_uid='{traj_uid}'")

    original_run_dir, source_filename = row

    output_dir = original_run_dir if original_run_dir else traj_uid
    os.makedirs(output_dir, exist_ok=True)

    xyz_name = source_filename if source_filename else DEFAULT_XYZ_NAME
    output_xyz = os.path.join(output_dir, xyz_name)

    restore_xyz_from_db(db_path, traj_uid, output_xyz)

    output_csv = os.path.join(output_dir, DEFAULT_FRAME_CSV_NAME)
    export_frame_data_csv(db_path, traj_uid, output_csv)

    print(f"Restored frame data -> {output_csv}")
    print(f"Done. Restored trajectory '{traj_uid}' into: {os.path.abspath(output_dir)}")


def restore_all_from_db(
    db_path: str,
    output_dir: str,
    molecule: str = None,
    isomer: str = None,
    method: str = None,
    energy_label: str = None,
):
    os.makedirs(output_dir, exist_ok=True)

    output_input = restore_single_input_file_from_db(db_path, output_dir)
    if output_input is not None:
        print(f"Restored shared input -> {output_input}")
    else:
        print("No shared input file found in the database.")

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    query = """
        SELECT
            traj_uid,
            source_filename,
            original_run_dir,
            molecule,
            isomer,
            method_label,
            energy_label
        FROM trajectories
    """

    conditions = []
    params = []

    if molecule is not None:
        conditions.append("molecule = ?")
        params.append(molecule)

    if isomer is not None:
        conditions.append("isomer = ?")
        params.append(isomer)

    if method is not None:
        conditions.append("method_label = ?")
        params.append(method)

    if energy_label is not None:
        conditions.append("energy_label = ?")
        params.append(energy_label)

    if conditions:
        query += " WHERE " + " AND ".join(conditions)

    query += " ORDER BY run_id, created_at, traj_uid"

    cur.execute(query, tuple(params))
    rows = cur.fetchall()
    conn.close()

    if not rows:
        print("No trajectories found in the database for the selected filters.")
        return

    def short_label(value, fallback="UNK"):
        if value is None:
            return fallback
        return str(value).replace(" ", "_")

    for i, (
        traj_uid,
        source_filename,
        original_run_dir,
        mol,
        iso,
        meth,
        enlab,
    ) in enumerate(rows, start=1):
        base_run = original_run_dir if original_run_dir else f"{DEFAULT_RUN_DIR_PREFIX}{i:0{DEFAULT_RUN_DIR_DIGITS}d}"

        mol_txt = short_label(mol, "UNK")
        iso_txt = short_label(iso, "NA") if iso is not None else None
        meth_txt = short_label(meth, "UNK")
        en_txt = short_label(enlab, "UNK")

        parts = [mol_txt]
        if iso_txt is not None:
            parts.append(iso_txt)
        parts.extend([meth_txt, en_txt, base_run])

        run_folder_name = "_".join(parts)
        run_dir = os.path.join(output_dir, run_folder_name)
        os.makedirs(run_dir, exist_ok=True)

        xyz_name = source_filename if source_filename else DEFAULT_XYZ_NAME
        output_xyz = os.path.join(run_dir, xyz_name)

        print(f"Restoring {traj_uid} -> {output_xyz}")
        restore_xyz_from_db(db_path, traj_uid, output_xyz)

        output_csv = os.path.join(run_dir, DEFAULT_FRAME_CSV_NAME)
        export_frame_data_csv(db_path, traj_uid, output_csv)
        print(f"Restored frame data -> {output_csv}")

    print(f"Done. Restored {len(rows)} trajectory file(s) into: {os.path.abspath(output_dir)}")