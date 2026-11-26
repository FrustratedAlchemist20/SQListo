
#!/usr/bin/env python3

"""
Recover missing TeraChem energy metadata from stored MD inputs.

Existing values are preserved. No molecular dynamics trajectories
are recalculated or modified.
"""

import argparse
import math
import sqlite3
import sys

from pathlib import Path
from contextlib import closing

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from xyz2db.energy_utils import compute_terachem_energy_fields


def get_temperature(tinit, t0, thermostat):
    for value in (tinit, t0, thermostat):
        try:
            temperature = float(value)
            if math.isfinite(temperature) and temperature > 0:
                return temperature
        except (TypeError, ValueError):
            continue

    return None


def backfill(database, apply=False):

    path = Path(database).expanduser()

    if path.is_symlink():
        raise ValueError("Use an independent database copy.")

    db = path.resolve()

    if not db.is_file():
        raise FileNotFoundError(db)

    mode = "rw" if apply else "ro"

    with closing(sqlite3.connect(
        db.as_uri() + f"?mode={mode}",
        uri=True
    )) as conn:

        if apply:
            conn.execute("BEGIN IMMEDIATE")

        rows = conn.execute("""
            SELECT DISTINCT
                mi.input_id,
                mi.method,
                mi.tinit,
                mi.t0,
                mi.thermostat,
                t.molecule,
                t.natoms,
                t.energy_label
            FROM md_inputs AS mi
            JOIN trajectories AS t
              ON t.input_id = mi.input_id
        """).fetchall()

        grouped = {}

        for row in rows:
            grouped.setdefault(row[0], []).append(row)

        updated = 0

        try:
            for input_id, records in grouped.items():

                # Avoid ambiguous input definitions.
                definitions = {
                    (r[1], r[2], r[3], r[4], r[6], r[7])
                    for r in records
                }

                if len(definitions) != 1:
                    print(f"[SKIP] Ambiguous input: {input_id}")
                    continue

                (
                    input_id,
                    method,
                    tinit,
                    t0,
                    thermostat,
                    molecule,
                    natoms,
                    energy_label
                ) = records[0]

                if str(method).casefold() not in {
                    "ub3lyp", "b3lyp"
                }:
                    print(f"[SKIP] Unsupported method: {method}")
                    continue

                temperature = get_temperature(
                    tinit, t0, thermostat
                )

                if temperature is None or not natoms or natoms < 3:
                    print(f"[SKIP] Incomplete metadata: {input_id}")
                    continue

                values = compute_terachem_energy_fields(
                    thermostat_K=temperature,
                    natoms=natoms,
                    energy_label=energy_label,
                )

                print(f"\nMolecule: {molecule}")
                print(f"Input: {input_id}")

                for field, value in values.items():
                    print(f"  {field}: {value}")

                if apply:
                    cursor = conn.execute("""
                        UPDATE md_inputs
                        SET
                            energy_label_factor =
                                COALESCE(energy_label_factor, ?),
                            energy_temperature_K =
                                COALESCE(energy_temperature_K, ?),
                            energy_kcal_mol =
                                COALESCE(energy_kcal_mol, ?),
                            zpe_kcal_mol =
                                COALESCE(zpe_kcal_mol, ?),
                            dof = COALESCE(dof, ?)
                        WHERE input_id = ?
                          AND (
                              energy_label_factor IS NULL
                              OR energy_temperature_K IS NULL
                              OR energy_kcal_mol IS NULL
                              OR zpe_kcal_mol IS NULL
                              OR dof IS NULL
                          )
                    """, (
                        values["energy_label_factor"],
                        values["energy_temperature_K"],
                        values["energy_kcal_mol"],
                        values["zpe_kcal_mol"],
                        values["dof"],
                        input_id,
                    ))

                    updated += cursor.rowcount

            if apply:
                integrity = conn.execute(
                    "PRAGMA quick_check"
                ).fetchall()

                if integrity != [("ok",)]:
                    raise RuntimeError(integrity)

                conn.commit()

        except Exception:
            conn.rollback()
            raise

        if apply:
            print(f"\nUpdated inputs: {updated}")
            print("Integrity check: OK")
        else:
            print("\nPreview only. No database changes made.")


if __name__ == "__main__":

    parser = argparse.ArgumentParser(
        description="Recover missing TeraChem energy metadata."
    )

    parser.add_argument("database")

    parser.add_argument(
        "--apply",
        action="store_true",
        help="Apply changes to the database."
    )

    args = parser.parse_args()

    backfill(args.database, args.apply)

