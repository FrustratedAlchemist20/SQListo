# xyz2db/kinetics_tools/kinetics_db.py

import json
import re
import sqlite3

from ..compression import deserialize_block
from ..db import init_db
from ..parsing import extract_frame_number
from ..fragment_tools.fragments import connected_fragments
from .kinetics import (
    compute_global_kinetics_from_events,
    detect_disappearance_time,
    export_event_rows_csv,
    export_summary_csv,
    export_survival_csv,
)


_TIME_PS_RE = re.compile(r"\btime_ps\s+([0-9.+\-Ee]+)")


def extract_time_ps(comment: str, fallback_timestep=None, frame_idx=None):
    if comment:
        m = _TIME_PS_RE.search(str(comment))
        if m:
            try:
                return float(m.group(1))
            except ValueError:
                pass

    if fallback_timestep is not None and frame_idx is not None:
        return float(fallback_timestep) * (int(frame_idx) + 1) / 1000.0

    return None


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
            t.nframes,
            t.symbols_json,
            m.timestep
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
            nframes,
            symbols_json,
            timestep,
        ) = row
        out.append({
            "traj_uid": traj_uid,
            "traj_code": traj_code,
            "molecule": mol,
            "isomer": iso,
            "method_label": meth,
            "energy_label": en,
            "nframes": nframes,
            "symbols": json.loads(symbols_json),
            "timestep": timestep,
        })
    return out


def iter_frames_for_traj(conn, traj_uid, symbols, fallback_timestep=None):
    cur = conn.cursor()
    cur.execute(
        """
        SELECT block_index, start_frame, payload
        FROM frame_blocks
        WHERE traj_uid = ?
        ORDER BY block_index
        """,
        (traj_uid,),
    )
    rows = cur.fetchall()

    for block_index, start_frame, payload in rows:
        coords_block, comments_block, energies_block = deserialize_block(payload)

        for local_idx, (coords, comment) in enumerate(zip(coords_block, comments_block)):
            frame_idx = start_frame + local_idx
            time_ps = extract_time_ps(
                comment=comment,
                fallback_timestep=fallback_timestep,
                frame_idx=frame_idx,
            )

            atoms = []
            for sym, (x, y, z) in zip(symbols, coords):
                atoms.append((sym, float(x), float(y), float(z)))

            yield {
                "frame_idx": frame_idx,
                "frame_number": extract_frame_number(comment),
                "time_ps": time_ps,
                "comment": comment,
                "atoms": atoms,
            }


def build_frame_fragment_records(conn, traj_uid, symbols, fallback_timestep=None):
    for rec in iter_frames_for_traj(conn, traj_uid, symbols, fallback_timestep=fallback_timestep):
        fragments_idx = connected_fragments(rec["atoms"])
        fragment_count = len(fragments_idx)
        intact = (fragment_count == 1)

        yield {
            "frame_idx": rec["frame_idx"],
            "frame_number": rec["frame_number"],
            "time_ps": rec["time_ps"],
            "fragment_count": fragment_count,
            "intact": intact,
        }


def get_disappearance_event_for_traj(
    conn,
    traj_info,
    persist_frames=5,
):
    traj_uid = traj_info["traj_uid"]
    symbols = traj_info["symbols"]
    fallback_timestep = traj_info.get("timestep")

    frame_records = build_frame_fragment_records(
        conn=conn,
        traj_uid=traj_uid,
        symbols=symbols,
        fallback_timestep=fallback_timestep,
    )

    ev = detect_disappearance_time(
        frame_records=frame_records,
        persist_frames=persist_frames,
    )

    return {
        "traj_uid": traj_uid,
        "traj_code": traj_info.get("traj_code"),
        "molecule": traj_info.get("molecule"),
        "isomer": traj_info.get("isomer"),
        "method_label": traj_info.get("method_label"),
        "energy_label": traj_info.get("energy_label"),
        **ev,
    }


def ensure_kinetics_tables(conn):
    cur = conn.cursor()

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS kinetics_global (
            kinetics_uid TEXT PRIMARY KEY,
            molecule TEXT,
            isomer TEXT,
            method_label TEXT,
            energy_label TEXT,
            persist_frames INTEGER,
            window_mode TEXT,
            min_points INTEGER,
            n_trajectories_total INTEGER,
            n_events INTEGER,
            n_censored INTEGER,
            event_fraction REAL,
            mean_followup_ps REAL,
            median_followup_ps REAL,
            min_followup_ps REAL,
            max_followup_ps REAL,
            mean_event_time_ps REAL,
            median_event_time_ps REAL,
            min_event_time_ps REAL,
            max_event_time_ps REAL,
            common_window_ps REAL,
            k_regression_ps_minus1 REAL,
            k_regression_stderr REAL,
            k_regression_ci95_low REAL,
            k_regression_ci95_high REAL,
            half_life_regression_ps REAL,
            r2 REAL,
            n_fit_points INTEGER,
            k_mle_ps_minus1 REAL,
            k_mle_stderr REAL,
            k_mle_ci95_low REAL,
            k_mle_ci95_high REAL,
            half_life_mle_ps REAL,
            warnings_json TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """
    )

    # Backward-compatible migration for databases created before
    # min_points was part of the kinetic identity.
    existing_columns = {
        row[1]
        for row in cur.execute("PRAGMA table_info(kinetics_global)").fetchall()
    }
    if "min_points" not in existing_columns:
        cur.execute(
            "ALTER TABLE kinetics_global ADD COLUMN min_points INTEGER"
        )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS kinetics_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            kinetics_uid TEXT NOT NULL,
            traj_uid TEXT NOT NULL,
            traj_code TEXT,
            molecule TEXT,
            isomer TEXT,
            method_label TEXT,
            energy_label TEXT,
            event_occurred INTEGER,
            event_time_ps REAL,
            event_frame_idx INTEGER,
            followup_time_ps REAL,
            n_frames_scanned INTEGER,
            max_fragment_count INTEGER,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(kinetics_uid, traj_uid)
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS kinetics_survival_points (
            kinetics_uid TEXT NOT NULL,
            point_index INTEGER NOT NULL,
            point_json TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (kinetics_uid, point_index)
        )
        """
    )

    cur.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_kinetics_survival_uid
        ON kinetics_survival_points(kinetics_uid)
        """
    )

    conn.commit()


def make_kinetics_uid(summary):
    import hashlib

    seed = "|".join([
        str(summary.get("molecule")),
        str(summary.get("isomer")),
        str(summary.get("method_label")),
        str(summary.get("energy_label")),
        str(summary.get("persist_frames")),
        str(summary.get("window_mode")),
        str(summary.get("min_points")),
    ])
    short = hashlib.sha256(seed.encode("utf-8")).hexdigest()[:24]
    return f"kin_{short}"


def store_global_kinetics(
    conn,
    summary,
    event_rows,
    survival_rows,
):
    ensure_kinetics_tables(conn)

    kinetics_uid = make_kinetics_uid(summary)
    cur = conn.cursor()

    cur.execute(
        "DELETE FROM kinetics_survival_points WHERE kinetics_uid = ?",
        (kinetics_uid,),
    )
    cur.execute(
        "DELETE FROM kinetics_events WHERE kinetics_uid = ?",
        (kinetics_uid,),
    )
    cur.execute(
        "DELETE FROM kinetics_global WHERE kinetics_uid = ?",
        (kinetics_uid,),
    )

    cur.execute(
        """
        INSERT INTO kinetics_global (
            kinetics_uid,
            molecule,
            isomer,
            method_label,
            energy_label,
            persist_frames,
            window_mode,
            min_points,
            n_trajectories_total,
            n_events,
            n_censored,
            event_fraction,
            mean_followup_ps,
            median_followup_ps,
            min_followup_ps,
            max_followup_ps,
            mean_event_time_ps,
            median_event_time_ps,
            min_event_time_ps,
            max_event_time_ps,
            common_window_ps,
            k_regression_ps_minus1,
            k_regression_stderr,
            k_regression_ci95_low,
            k_regression_ci95_high,
            half_life_regression_ps,
            r2,
            n_fit_points,
            k_mle_ps_minus1,
            k_mle_stderr,
            k_mle_ci95_low,
            k_mle_ci95_high,
            half_life_mle_ps,
            warnings_json
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            kinetics_uid,
            summary.get("molecule"),
            summary.get("isomer"),
            summary.get("method_label"),
            summary.get("energy_label"),
            summary.get("persist_frames"),
            summary.get("window_mode"),
            summary.get("min_points"),
            summary.get("n_trajectories_total"),
            summary.get("n_events"),
            summary.get("n_censored"),
            summary.get("event_fraction"),
            summary.get("mean_followup_ps"),
            summary.get("median_followup_ps"),
            summary.get("min_followup_ps"),
            summary.get("max_followup_ps"),
            summary.get("mean_event_time_ps"),
            summary.get("median_event_time_ps"),
            summary.get("min_event_time_ps"),
            summary.get("max_event_time_ps"),
            summary.get("common_window_ps"),
            summary.get("k_regression_ps^-1"),
            summary.get("k_regression_stderr"),
            summary.get("k_regression_ci95_low"),
            summary.get("k_regression_ci95_high"),
            summary.get("half_life_regression_ps"),
            summary.get("r2"),
            summary.get("n_fit_points"),
            summary.get("k_mle_ps^-1"),
            summary.get("k_mle_stderr"),
            summary.get("k_mle_ci95_low"),
            summary.get("k_mle_ci95_high"),
            summary.get("half_life_mle_ps"),
            json.dumps(summary.get("warnings", [])),
        ),
    )

    for row in event_rows:
        cur.execute(
            """
            INSERT INTO kinetics_events (
                kinetics_uid,
                traj_uid,
                traj_code,
                molecule,
                isomer,
                method_label,
                energy_label,
                event_occurred,
                event_time_ps,
                event_frame_idx,
                followup_time_ps,
                n_frames_scanned,
                max_fragment_count
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                kinetics_uid,
                row.get("traj_uid"),
                row.get("traj_code"),
                row.get("molecule"),
                row.get("isomer"),
                row.get("method_label"),
                row.get("energy_label"),
                1 if row.get("event_occurred") else 0,
                row.get("event_time_ps"),
                row.get("event_frame_idx"),
                row.get("followup_time_ps"),
                row.get("n_frames_scanned"),
                row.get("max_fragment_count"),
            ),
        )

    for point_index, row in enumerate(survival_rows):
        cur.execute(
            """
            INSERT INTO kinetics_survival_points (
                kinetics_uid,
                point_index,
                point_json
            )
            VALUES (?, ?, ?)
            """,
            (
                kinetics_uid,
                point_index,
                json.dumps(row, ensure_ascii=False),
            ),
        )

    conn.commit()
    return kinetics_uid


def print_global_kinetics_summary(summary):
    print("Global disappearance kinetics")
    print("-----------------------------")
    print(f"molecule              : {summary.get('molecule')}")
    print(f"isomer                : {summary.get('isomer')}")
    print(f"method                : {summary.get('method_label')}")
    print(f"energy_label          : {summary.get('energy_label')}")
    print(f"persist_frames        : {summary.get('persist_frames')}")
    print(f"window_mode           : {summary.get('window_mode')}")
    print()
    print(f"n_trajectories_total  : {summary.get('n_trajectories_total')}")
    print(f"n_events              : {summary.get('n_events')}")
    print(f"n_censored            : {summary.get('n_censored')}")
    print(f"event_fraction        : {summary.get('event_fraction')}")
    print()
    print(f"mean_followup_ps      : {summary.get('mean_followup_ps')}")
    print(f"median_followup_ps    : {summary.get('median_followup_ps')}")
    print(f"min_followup_ps       : {summary.get('min_followup_ps')}")
    print(f"max_followup_ps       : {summary.get('max_followup_ps')}")
    print()
    print(f"mean_event_time_ps    : {summary.get('mean_event_time_ps')}")
    print(f"median_event_time_ps  : {summary.get('median_event_time_ps')}")
    print(f"min_event_time_ps     : {summary.get('min_event_time_ps')}")
    print(f"max_event_time_ps     : {summary.get('max_event_time_ps')}")
    print()
    print(f"common_window_ps      : {summary.get('common_window_ps')}")
    print()

    if summary.get("ok"):
        print("Regression estimate")
        print("-------------------")
        print(f"k_regression_ps^-1   : {summary.get('k_regression_ps^-1')}")
        print(f"half_life_regression : {summary.get('half_life_regression_ps')}")
        print(f"r2                   : {summary.get('r2')}")
        print(f"k_reg_ci95           : [{summary.get('k_regression_ci95_low')}, {summary.get('k_regression_ci95_high')}]")
        print()

    if summary.get("k_mle_ps^-1") is not None:
        print("MLE estimate")
        print("------------")
        print(f"k_mle_ps^-1          : {summary.get('k_mle_ps^-1')}")
        print(f"half_life_mle_ps     : {summary.get('half_life_mle_ps')}")
        print(f"k_mle_ci95           : [{summary.get('k_mle_ci95_low')}, {summary.get('k_mle_ci95_high')}]")
        print()

    print(f"warnings             : {summary.get('warnings')}")


def compute_and_store_global_kinetics(
    db_path,
    molecule=None,
    isomer=None,
    method=None,
    energy_label=None,
    persist_frames=5,
    window_mode="censor",
    min_points=5,
    output_summary_csv=None,
    output_events_csv=None,
    output_survival_csv=None,
):
    conn = init_db(db_path)

    trajs = fetch_selected_trajectories(
        conn,
        molecule=molecule,
        isomer=isomer,
        method=method,
        energy_label=energy_label,
    )

    if not trajs:
        conn.close()
        raise ValueError("No trajectories found for the selected filters.")

    event_rows = []
    for traj in trajs:
        ev = get_disappearance_event_for_traj(
            conn=conn,
            traj_info=traj,
            persist_frames=persist_frames,
        )
        event_rows.append(ev)

    summary, survival_rows = compute_global_kinetics_from_events(
        event_rows=event_rows,
        molecule=molecule,
        isomer=isomer,
        method=method,
        energy_label=energy_label,
        persist_frames=persist_frames,
        window_mode=window_mode,
        min_points=min_points,
    )

    summary["min_points"] = int(min_points)

    kinetics_uid = store_global_kinetics(
        conn,
        summary,
        event_rows,
        survival_rows,
    )
    conn.close()

    if output_summary_csv:
        export_summary_csv(summary, output_summary_csv)

    if output_events_csv:
        export_event_rows_csv(event_rows, output_events_csv)

    if output_survival_csv:
        export_survival_csv(survival_rows, output_survival_csv)

    print_global_kinetics_summary(summary)
    print(f"kinetics_uid          : {kinetics_uid}")

    if output_summary_csv:
        print(f"summary_csv           : {output_summary_csv}")
    if output_events_csv:
        print(f"events_csv            : {output_events_csv}")
    if output_survival_csv:
        print(f"survival_csv          : {output_survival_csv}")

    return summary, event_rows, survival_rows
