# xyz2db/spectra_tools/spectra_db.py

import csv
import sqlite3

from .spectra import build_spectrum_rows


def fetch_fragment_rows_for_spectrum(
    db_path,
    molecule=None,
    isomer=None,
    method=None,
    energy_label=None,
):
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    query = """
        SELECT
            t.traj_uid,
            t.molecule,
            t.isomer,
            t.method_label,
            t.energy_label,
            f.formula,
            f.exact_mass,
            f.charge_guess
        FROM trajectories t
        JOIN fragment_analysis fa ON t.traj_uid = fa.traj_uid
        JOIN fragments f ON t.traj_uid = f.traj_uid
    """

    conditions = []
    params = []

    if molecule is not None:
        conditions.append("t.molecule = ?")
        params.append(molecule)

    if isomer is not None:
        conditions.append("t.isomer = ?")
        params.append(isomer)

    if method is not None:
        conditions.append("t.method_label = ?")
        params.append(method)

    if energy_label is not None:
        conditions.append("t.energy_label = ?")
        params.append(energy_label)

    if conditions:
        query += " WHERE " + " AND ".join(conditions)

    query += """
        ORDER BY t.method_label, t.run_id, t.created_at, t.traj_uid, f.fragment_index
    """

    cur.execute(query, tuple(params))
    rows = cur.fetchall()
    conn.close()

    return [
        {
            "traj_uid": traj_uid,
            "molecule": molecule,
            "isomer": isomer,
            "method_label": method_label,
            "energy_label": energy_label,
            "formula": formula,
            "exact_mass": exact_mass,
            "charge_guess": charge_guess,
        }
        for (
            traj_uid,
            molecule,
            isomer,
            method_label,
            energy_label,
            formula,
            exact_mass,
            charge_guess,
        ) in rows
    ]


def print_spectrum_table(peaks):
    if not peaks:
        print("No spectra peaks found for the selected filters.")
        return

    print(f"{'intensity':>12s} {'mz':>12s} {'formula':20s}")
    print("-" * 48)

    for peak in peaks:
        print(
            f"{peak['intensity']:12.6f} "
            f"{peak['mz']:12.5f} "
            f"{peak['formula']:20s}"
        )


def export_spectrum_csv(peaks, output_csv):
    with open(output_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["intensity", "mz", "formula", "count"])
        for peak in peaks:
            writer.writerow(
                [
                    f"{peak['intensity']:.6f}",
                    f"{peak['mz']:.5f}",
                    peak["formula"],
                    peak["count"],
                ]
            )


def spectrum_list(
    db_path,
    molecule=None,
    isomer=None,
    method=None,
    energy_label=None,
    charged_only=False,
    neutral_only=False,
    mz_min=None,
    mz_max=None,
    scale=1000.0,
    sort_by="intensity",
    output_csv=None,
):
    fragment_rows = fetch_fragment_rows_for_spectrum(
        db_path=db_path,
        molecule=molecule,
        isomer=isomer,
        method=method,
        energy_label=energy_label,
    )

    if not fragment_rows:
        print("No fragment data found in the database for the selected filters.")
        print("Run analyze-fragments first.")
        return

    peaks = build_spectrum_rows(
        fragment_rows=fragment_rows,
        charged_only=charged_only,
        neutral_only=neutral_only,
        mz_min=mz_min,
        mz_max=mz_max,
        scale=scale,
        sort_by=sort_by,
    )

    print_spectrum_table(peaks)

    if output_csv is not None:
        export_spectrum_csv(peaks, output_csv)
        print(f"CSV written to: {output_csv}")