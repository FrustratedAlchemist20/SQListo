# xyz2db/metadata.py

# Metadata management for xyz2db
# This module provides functions to store
# and retrieve metadata about MD inputs and trajectories in the database.

import os

from .ids import make_input_id
from .parsing import parse_md_input


def store_md_input(conn, input_path: str, natoms=None, energy_label=None):
    input_path = os.path.abspath(input_path)
    parsed = parse_md_input(input_path, natoms=natoms, energy_label=energy_label)
    input_id, input_sha256 = make_input_id(input_path)

    cur = conn.cursor()
    cur.execute("SELECT input_id FROM md_inputs WHERE input_sha256 = ?", (input_sha256,))
    row = cur.fetchone()
    if row is not None:
        return row[0]

    cur.execute(
        """
        INSERT INTO md_inputs (
            input_id,
            input_filename,
            input_sha256,
            basis,
            has_basis,
            coordinates_file,
            charge,
            spinmult,
            method,
            dispersion,
            has_dispersion,
            run_type,
            nstep,
            timestep,
            thermostat,
            rescalefreq,
            tinit,
            t0,
            gpus,
            raw_input_text,
            energy_label_factor,
            energy_temperature_K,
            energy_kcal_mol,
            zpe_kcal_mol,
            dof
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            input_id,
            parsed["input_filename"],
            input_sha256,
            parsed["basis"],
            parsed["has_basis"],
            parsed["coordinates_file"],
            parsed["charge"],
            parsed["spinmult"],
            parsed["method"],
            parsed["dispersion"],
            parsed["has_dispersion"],
            parsed["run_type"],
            parsed["nstep"],
            parsed["timestep"],
            parsed["thermostat"],
            parsed["rescalefreq"],
            parsed["tinit"],
            parsed["t0"],
            parsed["gpus"],
            parsed["raw_input_text"],
            parsed["energy_label_factor"],
            parsed["energy_temperature_K"],
            parsed["energy_kcal_mol"],
            parsed["zpe_kcal_mol"],
            parsed["dof"],
        ),
    )
    conn.commit()
    return input_id