# xyz2db/exports.py

import os
import re
import sqlite3

from .compression import deserialize_block
from .config import CSV_FLOAT_FORMAT
from .parsing import extract_frame_number


_TIME_PS_RE = re.compile(r"\btime_ps\s+([0-9.+\-Ee]+)")


def extract_time_ps(comment: str):
    if not comment:
        return None
    m = _TIME_PS_RE.search(str(comment))
    if not m:
        return None
    try:
        return float(m.group(1))
    except ValueError:
        return None


def export_frame_data_csv(db_path: str, traj_uid: str, output_csv: str):
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    cur.execute(
        """
        SELECT m.timestep
        FROM trajectories t
        LEFT JOIN md_inputs m ON t.input_id = m.input_id
        WHERE t.traj_uid = ?
        """,
        (traj_uid,),
    )
    row = cur.fetchone()
    timestep_fs = row[0] if row and row[0] is not None else None

    cur.execute(
        """
        SELECT block_index, payload
        FROM frame_blocks
        WHERE traj_uid = ?
        ORDER BY block_index
        """,
        (traj_uid,),
    )
    blocks = cur.fetchall()
    conn.close()

    if not blocks:
        raise ValueError(f"No frame blocks found for traj_uid='{traj_uid}'")

    out_dir = os.path.dirname(output_csv)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)

    frame_idx_global = 0
    with open(output_csv, "w", encoding="utf-8") as f:
        f.write("frame_idx,frame_number,energy,time_ps\n")

        for block_index, payload in blocks:
            coords_block, comments_block, energies_block = deserialize_block(payload)

            for comment, energy in zip(comments_block, energies_block):
                frame_number = extract_frame_number(comment)

                # Prefer the exact time stored in the frame comment (needed for VENUS).
                time_ps = extract_time_ps(comment)

                # Fallback for older trajectories/comments that do not include time_ps.
                if time_ps is None and timestep_fs is not None:
                    time_ps = (frame_idx_global + 1) * float(timestep_fs) / 1000.0

                energy_str = "" if energy is None else format(float(energy), CSV_FLOAT_FORMAT)
                time_str = "" if time_ps is None else format(float(time_ps), CSV_FLOAT_FORMAT)
                frame_number_str = "" if frame_number is None else str(frame_number)

                f.write(f"{frame_idx_global},{frame_number_str},{energy_str},{time_str}\n")
                frame_idx_global += 1