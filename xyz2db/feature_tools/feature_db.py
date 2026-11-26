# xyz2db/feature_tools/feature_db.py

import csv
import json
import os
import re
import sqlite3
from collections import defaultdict

from ..compression import deserialize_block
from ..db import init_db
from .features import compute_fragment_feature_dict, aggregate_condition_feature_rows


_TIME_PS_RE = re.compile(r"\btime_ps\s+([0-9.+\-Ee]+)")


def _maybe_import_pandas():
    try:
        import pandas as pd
        return pd
    except Exception:
        return None


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


def get_existing_tables(conn):
    cur = conn.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
    return {row[0] for row in cur.fetchall()}


def sql_equals_or_null(column_name, value, params):
    if value is None:
        return f"{column_name} IS NULL"
    params.append(value)
    return f"{column_name} = ?"


def fetch_selected_trajectories(
    conn,
    molecule=None,
    isomer=None,
    method=None,
    energy_label=None,
):
    cur = conn.cursor()

    query = """
        SELECT
            t.traj_uid,
            t.traj_code,
            t.molecule,
            t.isomer,
            t.method_label,
            t.energy_label,
            t.run_id,
            t.nframes,
            t.natoms,
            t.symbols_json,
            m.timestep,
            m.nstep,
            m.charge,
            m.spinmult,
            m.method,
            m.run_type,
            m.energy_label_factor,
            m.energy_temperature_K,
            m.energy_kcal_mol,
            m.zpe_kcal_mol,
            m.dof
        FROM trajectories t
        LEFT JOIN md_inputs m ON t.input_id = m.input_id
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

    query += " ORDER BY t.run_id, t.created_at, t.traj_uid"

    cur.execute(query, tuple(params))
    rows = cur.fetchall()

    out = []
    for row in rows:
        (
            traj_uid,
            traj_code,
            mol,
            iso,
            meth,
            en,
            run_id,
            nframes,
            natoms,
            symbols_json,
            timestep,
            nstep,
            charge,
            spinmult,
            method_from_input,
            run_type,
            energy_label_factor,
            energy_temperature_K,
            energy_kcal_mol,
            zpe_kcal_mol,
            dof,
        ) = row

        out.append(
            {
                "traj_meta": {
                    "traj_uid": traj_uid,
                    "traj_code": traj_code,
                    "molecule": mol,
                    "isomer": iso,
                    "method_label": meth,
                    "energy_label": en,
                    "run_id": run_id,
                    "nframes": nframes,
                    "natoms": natoms,
                },
                "input_meta": {
                    "timestep": timestep,
                    "nstep": nstep,
                    "charge": charge,
                    "spinmult": spinmult,
                    "method": method_from_input,
                    "run_type": run_type,
                    "energy_label_factor": energy_label_factor,
                    "energy_temperature_K": energy_temperature_K,
                    "energy_kcal_mol": energy_kcal_mol,
                    "zpe_kcal_mol": zpe_kcal_mol,
                    "dof": dof,
                },
                "symbols": json.loads(symbols_json),
            }
        )

    return out


def fetch_final_time_ps(conn, traj_uid, fallback_timestep=None, fallback_nframes=None):
    cur = conn.cursor()
    cur.execute(
        """
        SELECT payload
        FROM frame_blocks
        WHERE traj_uid = ?
        ORDER BY block_index DESC
        LIMIT 1
        """,
        (traj_uid,),
    )
    row = cur.fetchone()

    if row is not None:
        payload = row[0]
        coords_block, comments_block, energies_block = deserialize_block(payload)
        if comments_block:
            last_comment = comments_block[-1]
            last_time_ps = extract_time_ps(last_comment)
            if last_time_ps is not None:
                return last_time_ps

    if fallback_timestep is not None and fallback_nframes is not None:
        return float(fallback_timestep) * int(fallback_nframes) / 1000.0

    return None


def fetch_fragment_rows(conn, traj_uid):
    cur = conn.cursor()
    cur.execute(
        """
        SELECT formula, exact_mass, charge_guess, n_atoms
        FROM fragments
        WHERE traj_uid = ?
        ORDER BY fragment_index
        """,
        (traj_uid,),
    )
    rows = cur.fetchall()

    return [
        {
            "formula": formula,
            "exact_mass": exact_mass,
            "charge_guess": charge_guess,
            "n_atoms": n_atoms,
        }
        for formula, exact_mass, charge_guess, n_atoms in rows
    ]


def fetch_reaction_info_for_traj(conn, traj_uid, existing_tables=None):
    if existing_tables is None:
        existing_tables = get_existing_tables(conn)

    if "reaction_members" not in existing_tables or "reaction_summary" not in existing_tables:
        return {}

    cur = conn.cursor()
    cur.execute(
        """
        SELECT
            rm.reaction_uid,
            rs.count,
            rs.frequency_pct,
            rs.fragment_count
        FROM reaction_members rm
        LEFT JOIN reaction_summary rs ON rm.reaction_uid = rs.reaction_uid
        WHERE rm.traj_uid = ?
        ORDER BY rs.frequency_pct DESC, rs.count DESC, rm.reaction_uid
        LIMIT 1
        """,
        (traj_uid,),
    )
    row = cur.fetchone()

    if row is None:
        return {}

    reaction_uid, reaction_count, reaction_frequency_pct, reaction_fragment_count = row
    return {
        "reaction_uid": reaction_uid,
        "reaction_count": reaction_count,
        "reaction_frequency_pct": reaction_frequency_pct,
        "reaction_fragment_count": reaction_fragment_count,
        "has_reaction_assignment": 1,
    }


def fetch_latest_kinetics_global_for_condition(
    conn,
    molecule,
    isomer,
    method_label,
    energy_label,
    existing_tables=None,
):
    if existing_tables is None:
        existing_tables = get_existing_tables(conn)

    if "kinetics_global" not in existing_tables:
        return {}

    cur = conn.cursor()
    params = []
    conditions = [
        sql_equals_or_null("molecule", molecule, params),
        sql_equals_or_null("isomer", isomer, params),
        sql_equals_or_null("method_label", method_label, params),
        sql_equals_or_null("energy_label", energy_label, params),
    ]

    cur.execute(
        f"""
        SELECT
            kinetics_uid,
            persist_frames,
            window_mode,
            n_trajectories_total,
            n_events,
            n_censored,
            event_fraction,
            common_window_ps,
            k_regression_ps_minus1,
            half_life_regression_ps,
            r2,
            n_fit_points,
            k_mle_ps_minus1,
            half_life_mle_ps,
            k_mle_ci95_low,
            k_mle_ci95_high
        FROM kinetics_global
        WHERE {" AND ".join(conditions)}
        ORDER BY created_at DESC, kinetics_uid DESC
        LIMIT 1
        """,
        tuple(params),
    )
    row = cur.fetchone()

    if row is None:
        return {}

    (
        kinetics_uid,
        persist_frames,
        window_mode,
        n_trajectories_total,
        n_events,
        n_censored,
        event_fraction,
        common_window_ps,
        k_regression_ps_minus1,
        half_life_regression_ps,
        r2,
        n_fit_points,
        k_mle_ps_minus1,
        half_life_mle_ps,
        k_mle_ci95_low,
        k_mle_ci95_high,
    ) = row

    return {
        "kinetics_uid": kinetics_uid,
        "persist_frames": persist_frames,
        "window_mode": window_mode,
        "n_trajectories_total": n_trajectories_total,
        "n_events": n_events,
        "n_censored": n_censored,
        "event_fraction": event_fraction,
        "common_window_ps": common_window_ps,
        "k_regression_ps^-1": k_regression_ps_minus1,
        "half_life_regression_ps": half_life_regression_ps,
        "r2": r2,
        "n_fit_points": n_fit_points,
        "k_mle_ps^-1": k_mle_ps_minus1,
        "half_life_mle_ps": half_life_mle_ps,
        "k_mle_ci95_low": k_mle_ci95_low,
        "k_mle_ci95_high": k_mle_ci95_high,
    }


def fetch_kinetics_event_for_traj(conn, kinetics_uid, traj_uid, existing_tables=None):
    if existing_tables is None:
        existing_tables = get_existing_tables(conn)

    if "kinetics_events" not in existing_tables or not kinetics_uid:
        return {}

    cur = conn.cursor()
    cur.execute(
        """
        SELECT
            event_occurred,
            event_time_ps,
            event_frame_idx,
            followup_time_ps,
            n_frames_scanned,
            max_fragment_count
        FROM kinetics_events
        WHERE kinetics_uid = ? AND traj_uid = ?
        LIMIT 1
        """,
        (kinetics_uid, traj_uid),
    )
    row = cur.fetchone()

    if row is None:
        return {}

    (
        event_occurred,
        event_time_ps,
        event_frame_idx,
        followup_time_ps,
        n_frames_scanned,
        max_fragment_count,
    ) = row

    return {
        "event_occurred": event_occurred,
        "event_time_ps": event_time_ps,
        "event_frame_idx": event_frame_idx,
        "followup_time_ps": followup_time_ps,
        "n_frames_scanned": n_frames_scanned,
        "max_fragment_count": max_fragment_count,
    }


def compute_feature_row_for_traj(
    conn,
    traj_bundle,
    include_reactions=True,
    include_kinetics=True,
    existing_tables=None,
    kinetics_cache=None,
):
    if existing_tables is None:
        existing_tables = get_existing_tables(conn)
    if kinetics_cache is None:
        kinetics_cache = {}

    traj_meta = traj_bundle["traj_meta"]
    input_meta = dict(traj_bundle["input_meta"])
    symbols = traj_bundle["symbols"]
    traj_uid = traj_meta["traj_uid"]

    fragment_rows = fetch_fragment_rows(conn, traj_uid)
    if not fragment_rows:
        raise ValueError(
            f"No fragment data found for traj_uid='{traj_uid}'. Run analyze-fragments first."
        )

    input_meta["final_time_ps"] = fetch_final_time_ps(
        conn,
        traj_uid,
        fallback_timestep=input_meta.get("timestep"),
        fallback_nframes=traj_meta.get("nframes"),
    )

    feat = compute_fragment_feature_dict(
        traj_meta=traj_meta,
        input_meta=input_meta,
        fragment_rows=fragment_rows,
        symbols=symbols,
    )

    if include_reactions:
        feat.update(fetch_reaction_info_for_traj(conn, traj_uid, existing_tables=existing_tables))

    if include_kinetics:
        cond_key = (
            traj_meta.get("molecule"),
            traj_meta.get("isomer"),
            traj_meta.get("method_label"),
            traj_meta.get("energy_label"),
        )
        if cond_key not in kinetics_cache:
            kinetics_cache[cond_key] = fetch_latest_kinetics_global_for_condition(
                conn,
                molecule=traj_meta.get("molecule"),
                isomer=traj_meta.get("isomer"),
                method_label=traj_meta.get("method_label"),
                energy_label=traj_meta.get("energy_label"),
                existing_tables=existing_tables,
            )

        kg = kinetics_cache[cond_key]
        feat.update(kg)

        if kg.get("kinetics_uid"):
            feat.update(
                fetch_kinetics_event_for_traj(
                    conn,
                    kinetics_uid=kg["kinetics_uid"],
                    traj_uid=traj_uid,
                    existing_tables=existing_tables,
                )
            )

    return feat


def extract_features_one(
    db_path,
    traj_uid,
    include_reactions=True,
    include_kinetics=True,
):
    conn = init_db(db_path)
    existing_tables = get_existing_tables(conn)

    trajs = fetch_selected_trajectories(conn)
    target = None
    for t in trajs:
        if t["traj_meta"]["traj_uid"] == traj_uid:
            target = t
            break

    if target is None:
        conn.close()
        raise ValueError(f"No trajectory found for traj_uid='{traj_uid}'")

    row = compute_feature_row_for_traj(
        conn,
        target,
        include_reactions=include_reactions,
        include_kinetics=include_kinetics,
        existing_tables=existing_tables,
        kinetics_cache={},
    )
    conn.close()

    print(f"Computed features in memory for {traj_uid}")
    return row


def extract_features_all(
    db_path,
    molecule=None,
    isomer=None,
    method=None,
    energy_label=None,
    include_reactions=True,
    include_kinetics=True,
):
    conn = init_db(db_path)
    existing_tables = get_existing_tables(conn)

    trajs = fetch_selected_trajectories(
        conn,
        molecule=molecule,
        isomer=isomer,
        method=method,
        energy_label=energy_label,
    )

    rows = []
    skipped = 0
    kinetics_cache = {}

    for t in trajs:
        try:
            row = compute_feature_row_for_traj(
                conn,
                t,
                include_reactions=include_reactions,
                include_kinetics=include_kinetics,
                existing_tables=existing_tables,
                kinetics_cache=kinetics_cache,
            )
            rows.append(row)
        except Exception as e:
            print(f"Skipping feature extraction for {t['traj_meta']['traj_uid']}: {e}")
            skipped += 1

    conn.close()

    print(f"Done. Computed features for {len(rows)} trajectory(ies).")
    print(f"Skipped: {skipped}")
    return rows


def build_condition_feature_rows(trajectory_rows):
    groups = defaultdict(list)
    for row in trajectory_rows:
        key = (
            row.get("molecule"),
            row.get("isomer"),
            row.get("method_label"),
            row.get("energy_label"),
        )
        groups[key].append(row)

    out = []
    for key, rows in groups.items():
        cond_row = aggregate_condition_feature_rows(rows)
        if cond_row is not None:
            out.append(cond_row)

    out.sort(
        key=lambda r: (
            str(r.get("molecule")),
            str(r.get("isomer")),
            str(r.get("method_label")),
            str(r.get("energy_label")),
        )
    )
    return out


def _write_csv_dicts(rows, output_csv):
    if not rows:
        raise ValueError("No rows available to export.")

    os.makedirs(os.path.dirname(output_csv), exist_ok=True) if os.path.dirname(output_csv) else None

    all_keys = []
    seen = set()
    for row in rows:
        for k in row.keys():
            if k not in seen:
                seen.add(k)
                all_keys.append(k)

    with open(output_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=all_keys)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def _write_parquet_dicts(rows, output_parquet):
    pd = _maybe_import_pandas()
    if pd is None:
        print("Warning: pandas is not available. Skipping Parquet export.")
        return False

    os.makedirs(os.path.dirname(output_parquet), exist_ok=True) if os.path.dirname(output_parquet) else None

    try:
        df = pd.DataFrame(rows)
        df.to_parquet(output_parquet, index=False)
        return True
    except Exception as e:
        print(f"Warning: could not write Parquet ({e}).")
        return False


def _default_parquet_path_from_csv(output_csv):
    base, _ext = os.path.splitext(output_csv)
    return base + ".parquet"


def feature_list(
    db_path,
    molecule=None,
    isomer=None,
    method=None,
    energy_label=None,
    include_reactions=True,
    include_kinetics=True,
):
    rows = extract_features_all(
        db_path=db_path,
        molecule=molecule,
        isomer=isomer,
        method=method,
        energy_label=energy_label,
        include_reactions=include_reactions,
        include_kinetics=include_kinetics,
    )

    if not rows:
        print("No computed features found for the selected filters.")
        return

    print(
        f"{'traj_uid':26s} {'traj_code':22s} {'frags':>5s} "
        f"{'largest_fragment':20s} {'mass':>12s} {'time_ps':>12s} {'chg/neut':>10s}"
    )
    print("-" * 140)

    for row in rows:
        mass_txt = "-" if row.get("largest_fragment_mass") is None else f"{row['largest_fragment_mass']:.6f}"
        time_txt = "-" if row.get("final_time_ps") is None else f"{row['final_time_ps']:.6f}"
        chg_txt = f"{row.get('charged_fragment_count', '-')}/{row.get('neutral_fragment_count', '-')}"
        print(
            f"{str(row.get('traj_uid')):26s} {str(row.get('traj_code')):22s} "
            f"{str(row.get('fragment_count')):>5s} "
            f"{str(row.get('largest_fragment_formula')):20s} {mass_txt:>12s} {time_txt:>12s} {chg_txt:>10s}"
        )


def feature_export(
    db_path,
    output_csv,
    molecule=None,
    isomer=None,
    method=None,
    energy_label=None,
    dataset_type="trajectory",
    include_reactions=True,
    include_kinetics=True,
    output_parquet=None,
):
    """
    Export feature datasets directly from the analytical tables already stored in the DB.

    dataset_type:
        - "trajectory" : one row per trajectory
        - "condition"  : one row per (molecule, isomer, method_label, energy_label)

    If output_parquet is None, it is derived automatically from output_csv.
    """
    if dataset_type not in {"trajectory", "condition"}:
        raise ValueError("dataset_type must be 'trajectory' or 'condition'")

    traj_rows = extract_features_all(
        db_path=db_path,
        molecule=molecule,
        isomer=isomer,
        method=method,
        energy_label=energy_label,
        include_reactions=include_reactions,
        include_kinetics=include_kinetics,
    )

    if not traj_rows:
        print("No computed features found for the selected filters.")
        return []

    if dataset_type == "trajectory":
        rows = traj_rows
    else:
        rows = build_condition_feature_rows(traj_rows)

    _write_csv_dicts(rows, output_csv)
    print(f"Feature CSV written to: {output_csv}")

    if output_parquet is None and output_csv:
        output_parquet = _default_parquet_path_from_csv(output_csv)

    if output_parquet:
        ok = _write_parquet_dicts(rows, output_parquet)
        if ok:
            print(f"Feature Parquet written to: {output_parquet}")

    return rows

def feature_export_all(
    db_path,
    output_dir,
    molecule=None,
    isomer=None,
    method=None,
    energy_label=None,
    include_reactions=True,
    include_kinetics=True,
):
    """
    Export both main feature datasets directly:
      - trajectory_features.{csv,parquet}
      - condition_features.{csv,parquet}

    Returns a dict with the generated paths.
    """
    if not output_dir:
        raise ValueError("output_dir must be provided")

    os.makedirs(output_dir, exist_ok=True)

    trajectory_csv = os.path.join(output_dir, "trajectory_features.csv")
    trajectory_parquet = os.path.join(output_dir, "trajectory_features.parquet")

    condition_csv = os.path.join(output_dir, "condition_features.csv")
    condition_parquet = os.path.join(output_dir, "condition_features.parquet")

    feature_export(
        db_path=db_path,
        output_csv=trajectory_csv,
        molecule=molecule,
        isomer=isomer,
        method=method,
        energy_label=energy_label,
        dataset_type="trajectory",
        include_reactions=include_reactions,
        include_kinetics=include_kinetics,
        output_parquet=trajectory_parquet,
    )

    feature_export(
        db_path=db_path,
        output_csv=condition_csv,
        molecule=molecule,
        isomer=isomer,
        method=method,
        energy_label=energy_label,
        dataset_type="condition",
        include_reactions=include_reactions,
        include_kinetics=include_kinetics,
        output_parquet=condition_parquet,
    )

    print("Done. Exported all feature datasets.")
    print(f"trajectory_csv      : {trajectory_csv}")
    print(f"trajectory_parquet  : {trajectory_parquet}")
    print(f"condition_csv       : {condition_csv}")
    print(f"condition_parquet   : {condition_parquet}")

    return {
        "trajectory_csv": trajectory_csv,
        "trajectory_parquet": trajectory_parquet,
        "condition_csv": condition_csv,
        "condition_parquet": condition_parquet,
    }