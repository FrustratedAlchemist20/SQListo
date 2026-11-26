# xyz2db/fragment_tools/fragment_db.py

import json
import sqlite3

from ..compression import deserialize_block
from ..db import init_db
from ..parsing import extract_frame_number
from .fragments import analyze_last_frame_atoms


def get_last_frame_from_db(db_path: str, traj_uid: str):
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    cur.execute(
        """
        SELECT t.symbols_json, fb.payload
        FROM trajectories t
        JOIN frame_blocks fb ON t.traj_uid = fb.traj_uid
        WHERE t.traj_uid = ?
        ORDER BY fb.block_index DESC
        LIMIT 1
        """,
        (traj_uid,),
    )
    row = cur.fetchone()

    if row is None:
        conn.close()
        raise ValueError(f"No trajectory found for traj_uid='{traj_uid}'")

    symbols_json, payload = row
    symbols = json.loads(symbols_json)

    coords_block, comments_block, energies_block = deserialize_block(payload)

    coords = coords_block[-1]
    comment = comments_block[-1]
    frame_number = extract_frame_number(comment)

    atoms = []
    for sym, (x, y, z) in zip(symbols, coords):
        atoms.append((sym, float(x), float(y), float(z)))

    conn.close()
    return atoms, comment, frame_number


def store_fragment_analysis(db_path: str, traj_uid: str, fragments, analyzed_frame_idx=-1, analyzed_frame_number=None):
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    cur.execute("DELETE FROM fragments WHERE traj_uid = ?", (traj_uid,))
    cur.execute("DELETE FROM fragment_analysis WHERE traj_uid = ?", (traj_uid,))

    cur.execute(
        """
        INSERT INTO fragment_analysis (
            traj_uid, analyzed_frame_idx, analyzed_frame_number, fragment_count, analysis_method
        )
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            traj_uid,
            analyzed_frame_idx,
            analyzed_frame_number,
            len(fragments),
            "last_frame_connectivity",
        ),
    )

    for frag in fragments:
        cur.execute(
            """
            INSERT INTO fragments (
                traj_uid, fragment_index, formula, exact_mass, charge_guess, n_atoms, atom_indices_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                traj_uid,
                frag["fragment_index"],
                frag["formula"],
                frag["exact_mass"],
                frag["charge_guess"],
                frag["n_atoms"],
                json.dumps(frag["atom_indices"]),
            ),
        )

    conn.commit()
    conn.close()


def analyze_and_store_fragments_for_traj(db_path: str, traj_uid: str):
    # Ensures the general schema exists
    conn = init_db(db_path)
    conn.close()

    atoms, comment, frame_number = get_last_frame_from_db(db_path, traj_uid)
    fragments = analyze_last_frame_atoms(atoms)

    store_fragment_analysis(
        db_path=db_path,
        traj_uid=traj_uid,
        fragments=fragments,
        analyzed_frame_idx=-1,
        analyzed_frame_number=frame_number,
    )
    return fragments


def analyze_and_store_fragments_for_all(db_path: str):
    # Ensures the general schema exists
    conn = init_db(db_path)
    conn.close()

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("SELECT traj_uid FROM trajectories ORDER BY run_id, created_at, traj_uid")
    rows = cur.fetchall()
    conn.close()

    analyzed = 0
    for (traj_uid,) in rows:
        try:
            analyze_and_store_fragments_for_traj(db_path, traj_uid)
            analyzed += 1
            print(f"Analyzed fragments for {traj_uid}")
        except Exception as e:
            print(f"Skipping fragment analysis for {traj_uid}: {e}")

    print(f"Done. Fragment analysis stored for {analyzed} trajectory(ies).")


def fragment_list(db_path: str):
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    cur.execute(
        """
        SELECT
            t.traj_uid,
            t.traj_code,
            t.original_run_dir,
            t.source_filename,
            fa.fragment_count,
            fa.analyzed_frame_number,
            fa.analysis_method
        FROM trajectories t
        LEFT JOIN fragment_analysis fa ON t.traj_uid = fa.traj_uid
        ORDER BY t.run_id, t.created_at, t.traj_uid
        """
    )
    traj_rows = cur.fetchall()

    if not traj_rows:
        conn.close()
        print("No trajectories found in the database.")
        return

    for (
        traj_uid,
        traj_code,
        original_run_dir,
        source_filename,
        fragment_count,
        analyzed_frame_number,
        analysis_method,
    ) in traj_rows:
        print("-" * 80)
        print(f"traj_uid             : {traj_uid}")
        print(f"traj_code            : {traj_code}")
        print(f"original_run_dir     : {original_run_dir}")
        print(f"source_filename      : {source_filename}")
        print(f"fragment_count       : {fragment_count}")
        print(f"analyzed_frame_number: {analyzed_frame_number}")
        print(f"analysis_method      : {analysis_method}")

        cur.execute(
            """
            SELECT fragment_index, formula, exact_mass, charge_guess, n_atoms
            FROM fragments
            WHERE traj_uid = ?
            ORDER BY fragment_index
            """,
            (traj_uid,),
        )
        frag_rows = cur.fetchall()

        if not frag_rows:
            print("  No stored fragment details.")
            continue

        for fragment_index, formula, exact_mass, charge_guess, n_atoms in frag_rows:
            print(
                f"  Fragment {fragment_index}: "
                f"formula={formula}, mass={exact_mass:.6f}, "
                f"charge_guess={charge_guess}, n_atoms={n_atoms}"
            )

    conn.close()