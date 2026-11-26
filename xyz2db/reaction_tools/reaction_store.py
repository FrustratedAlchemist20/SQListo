# xyz2db/reaction_tools/reaction_store.py

import sqlite3

from ..db import init_db
from .reaction_db import build_reaction_summary
from .reactions import merge_two_methods


def _store_single_method_reactions(conn, method_name, data):
    cur = conn.cursor()

    for item in data:
        molecule_txt = ",".join(item.get("molecule_labels", [])) if item.get("molecule_labels") else None
        energy_txt = ",".join(item.get("energy_labels", [])) if item.get("energy_labels") else None

        cur.execute(
            """
            INSERT OR REPLACE INTO reaction_summary (
                reaction_uid,
                method_label,
                molecule_labels,
                energy_labels,
                count,
                frequency_pct,
                fragment_count
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                item["reaction_uid"],
                method_name,
                molecule_txt,
                energy_txt,
                item["count"],
                item["frequency_pct"],
                len(item["fragments"]),
            ),
        )

        cur.execute("DELETE FROM reaction_fragments WHERE reaction_uid = ?", (item["reaction_uid"],))
        cur.execute("DELETE FROM reaction_members WHERE reaction_uid = ?", (item["reaction_uid"],))

        for i, frag in enumerate(item["fragments"], start=1):
            cur.execute(
                """
                INSERT INTO reaction_fragments (
                    reaction_uid,
                    fragment_index,
                    formula,
                    exact_mass
                )
                VALUES (?, ?, ?, ?)
                """,
                (
                    item["reaction_uid"],
                    i,
                    frag["formula"],
                    frag["exact_mass"],
                ),
            )

        for member in item["members"]:
            cur.execute(
                """
                INSERT OR IGNORE INTO reaction_members (
                    reaction_uid,
                    traj_uid
                )
                VALUES (?, ?)
                """,
                (
                    item["reaction_uid"],
                    member["traj_uid"],
                ),
            )


def store_reactions(
    db_path,
    methods=None,
    molecule=None,
    isomer=None,
    energy_label=None,
):
    """
    Store aggregated reactions in the database.

    methods:
      None -> all methods in DB
      [method1] -> one method
      [method1, method2] -> store both method-specific summaries
    """
    conn = init_db(db_path)

    summary = build_reaction_summary(
        db_path=db_path,
        methods=methods,
        molecule=molecule,
        isomer=isomer,
        energy_label=energy_label,
    )

    if not summary:
        conn.close()
        print("No fragment-based reactions found to store.")
        print("Run analyze-fragments first.")
        return

    stored = 0
    for method_name, data in summary.items():
        _store_single_method_reactions(conn, method_name, data)
        stored += len(data)

    conn.commit()
    conn.close()

    print(f"Stored {stored} aggregated reaction(s) in the database.")


def reaction_show(db_path, reaction_uid):
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    cur.execute(
        """
        SELECT
            reaction_uid,
            method_label,
            molecule_labels,
            energy_labels,
            count,
            frequency_pct,
            fragment_count
        FROM reaction_summary
        WHERE reaction_uid = ?
        """,
        (reaction_uid,),
    )
    row = cur.fetchone()

    if row is None:
        conn.close()
        print(f"No stored reaction found for reaction_uid='{reaction_uid}'")
        return

    (
        reaction_uid,
        method_label,
        molecule_labels,
        energy_labels,
        count,
        frequency_pct,
        fragment_count,
    ) = row

    print("Reaction")
    print("--------")
    print(f"reaction_uid   : {reaction_uid}")
    print(f"method_label   : {method_label}")
    print(f"molecule       : {molecule_labels}")
    print(f"energy_label   : {energy_labels}")
    print(f"count          : {count}")
    print(f"frequency_pct  : {frequency_pct:.6f}")
    print(f"fragment_count : {fragment_count}")
    print()

    cur.execute(
        """
        SELECT fragment_index, formula, exact_mass
        FROM reaction_fragments
        WHERE reaction_uid = ?
        ORDER BY fragment_index
        """,
        (reaction_uid,),
    )
    frag_rows = cur.fetchall()

    print("Fragments")
    print("---------")
    for fragment_index, formula, exact_mass in frag_rows:
        print(f"  Fragment {fragment_index}: formula={formula}, mass={exact_mass:.6f}")
    print()

    cur.execute(
        """
        SELECT
            t.traj_uid,
            t.traj_code,
            t.molecule,
            t.energy_label,
            t.original_run_dir
        FROM reaction_members rm
        JOIN trajectories t ON rm.traj_uid = t.traj_uid
        WHERE rm.reaction_uid = ?
        ORDER BY t.run_id, t.created_at, t.traj_uid
        """,
        (reaction_uid,),
    )
    member_rows = cur.fetchall()

    print("Member trajectories")
    print("-------------------")
    for traj_uid, traj_code, molecule, energy_label, original_run_dir in member_rows:
        print(
            f"  traj_uid={traj_uid} | traj_code={traj_code} | "
            f"molecule={molecule} | energy={energy_label} | run_dir={original_run_dir}"
        )

    conn.close()


def fragment_search(db_path, formula=None, mz=None, tol=0.001):
    if formula is None and mz is None:
        raise ValueError("You must provide --formula or --mz")

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    if formula is not None:
        cur.execute(
            """
            SELECT DISTINCT
                rs.reaction_uid,
                rs.method_label,
                rs.molecule_labels,
                rs.energy_labels,
                rs.frequency_pct
            FROM reaction_fragments rf
            JOIN reaction_summary rs ON rf.reaction_uid = rs.reaction_uid
            WHERE rf.formula = ?
            ORDER BY rs.frequency_pct DESC, rs.reaction_uid
            """,
            (formula,),
        )
        reaction_rows = cur.fetchall()

        print(f"Fragment formula: {formula}")
    else:
        cur.execute(
            """
            SELECT DISTINCT
                rs.reaction_uid,
                rs.method_label,
                rs.molecule_labels,
                rs.energy_labels,
                rs.frequency_pct
            FROM reaction_fragments rf
            JOIN reaction_summary rs ON rf.reaction_uid = rs.reaction_uid
            WHERE ABS(rf.exact_mass - ?) <= ?
            ORDER BY rs.frequency_pct DESC, rs.reaction_uid
            """,
            (mz, tol),
        )
        reaction_rows = cur.fetchall()

        print(f"Fragment mass: {mz:.6f} ± {tol:.6f}")

    print()
    print("Reactions containing this fragment")
    print("---------------------------------")
    if not reaction_rows:
        print("No matching reactions found.")
        conn.close()
        return

    for reaction_uid, method_label, molecule_labels, energy_labels, frequency_pct in reaction_rows:
        print(
            f"  reaction_uid={reaction_uid} | method={method_label} | "
            f"molecule={molecule_labels} | energy={energy_labels} | freq={frequency_pct:.6f}"
        )

    print()
    print("Member trajectories")
    print("-------------------")

    reaction_uids = [row[0] for row in reaction_rows]
    placeholders = ",".join("?" for _ in reaction_uids)

    cur.execute(
        f"""
        SELECT DISTINCT
            rm.reaction_uid,
            t.traj_uid,
            t.traj_code,
            t.molecule,
            t.energy_label,
            t.original_run_dir
        FROM reaction_members rm
        JOIN trajectories t ON rm.traj_uid = t.traj_uid
        WHERE rm.reaction_uid IN ({placeholders})
        ORDER BY rm.reaction_uid, t.run_id, t.created_at, t.traj_uid
        """,
        tuple(reaction_uids),
    )
    member_rows = cur.fetchall()

    for reaction_uid, traj_uid, traj_code, molecule, energy_label, original_run_dir in member_rows:
        print(
            f"  reaction_uid={reaction_uid} | traj_uid={traj_uid} | traj_code={traj_code} | "
            f"molecule={molecule} | energy={energy_label} | run_dir={original_run_dir}"
        )

    conn.close()