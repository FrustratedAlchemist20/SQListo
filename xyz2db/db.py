import sqlite3

from .schema import SCHEMA_SQL


def init_db(db_path: str):
    conn = sqlite3.connect(db_path)
    conn.executescript(SCHEMA_SQL)
    return conn


def _build_trajectory_filters(molecule=None, isomer=None, method=None, energy_label=None):
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

    where_sql = ""
    if conditions:
        where_sql = " WHERE " + " AND ".join(conditions)

    return where_sql, params


def list_trajectories(
    db_path: str,
    molecule: str = None,
    isomer: str = None,
    method: str = None,
    energy_label: str = None,
):
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    where_sql, params = _build_trajectory_filters(
        molecule=molecule,
        isomer=isomer,
        method=method,
        energy_label=energy_label,
    )

    query = f"""
        SELECT
            t.traj_uid,
            t.traj_code,
            t.molecule,
            t.isomer,
            t.method_label,
            t.energy_label,
            t.run_id,
            t.natoms,
            t.nframes,
            t.created_at,
            t.source_filename,
            m.input_filename,
            fa.fragment_count
        FROM trajectories t
        LEFT JOIN md_inputs m ON t.input_id = m.input_id
        LEFT JOIN fragment_analysis fa ON t.traj_uid = fa.traj_uid
        {where_sql}
        ORDER BY t.created_at DESC
    """

    cur.execute(query, tuple(params))
    rows = cur.fetchall()
    conn.close()

    if not rows:
        print("No trajectories found for the selected filters.")
        return

    print("Trajectory list")
    print("---------------")
    print(f"Filters -> molecule={molecule}, isomer={isomer}, method={method}, energy_label={energy_label}")
    print()
    print(
        f"{'traj_uid':26s} {'traj_code':22s} {'frames':>8s} {'frags':>7s} "
        f"{'molecule':14s} {'method':10s} {'energy':8s} {'input':12s} file"
    )
    print("-" * 160)

    for row in rows:
        (
            traj_uid,
            traj_code,
            mol,
            iso,
            method_label,
            en_label,
            run_id,
            natoms,
            nframes,
            created_at,
            source_filename,
            input_filename,
            fragment_count,
        ) = row

        frag_txt = str(fragment_count) if fragment_count is not None else "-"
        mol_txt = str(mol) if mol is not None else "-"
        method_txt = str(method_label) if method_label is not None else "-"
        energy_txt = str(en_label) if en_label is not None else "-"
        input_txt = str(input_filename) if input_filename is not None else "-"

        print(
            f"{traj_uid:26s} {str(traj_code):22s} {nframes:8d} {frag_txt:>7s} "
            f"{mol_txt:14.14s} {method_txt:10.10s} {energy_txt:8.8s} {input_txt:12.12s} {source_filename}"
        )


def summary_db(
    db_path: str,
    molecule: str = None,
    isomer: str = None,
    method: str = None,
    energy_label: str = None,
):
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    where_sql, params = _build_trajectory_filters(
        molecule=molecule,
        isomer=isomer,
        method=method,
        energy_label=energy_label,
    )

    # Main filtered summary
    cur.execute(f"SELECT COUNT(*) FROM trajectories t{where_sql}", tuple(params))
    n_traj = cur.fetchone()[0]

    cur.execute(f"SELECT COALESCE(SUM(t.nframes), 0) FROM trajectories t{where_sql}", tuple(params))
    total_frames = cur.fetchone()[0]

    cur.execute(f"SELECT COALESCE(AVG(t.nframes), 0) FROM trajectories t{where_sql}", tuple(params))
    avg_frames = cur.fetchone()[0]

    cur.execute(f"SELECT COALESCE(MIN(t.nframes), 0) FROM trajectories t{where_sql}", tuple(params))
    min_frames = cur.fetchone()[0]

    cur.execute(f"SELECT COALESCE(MAX(t.nframes), 0) FROM trajectories t{where_sql}", tuple(params))
    max_frames = cur.fetchone()[0]

    cur.execute(f"SELECT COUNT(DISTINCT t.molecule) FROM trajectories t{where_sql}", tuple(params))
    n_molecules = cur.fetchone()[0]

    cur.execute(f"SELECT COUNT(DISTINCT t.method_label) FROM trajectories t{where_sql}", tuple(params))
    n_methods = cur.fetchone()[0]

    cur.execute(f"SELECT COUNT(DISTINCT t.energy_label) FROM trajectories t{where_sql}", tuple(params))
    n_energies = cur.fetchone()[0]

    cur.execute(
        f"""
        SELECT COUNT(*)
        FROM fragment_analysis fa
        JOIN trajectories t ON fa.traj_uid = t.traj_uid
        {where_sql}
        """,
        tuple(params),
    )
    n_fragment_analyses = cur.fetchone()[0]

    cur.execute(
        f"""
        SELECT COALESCE(SUM(fa.fragment_count), 0)
        FROM fragment_analysis fa
        JOIN trajectories t ON fa.traj_uid = t.traj_uid
        {where_sql}
        """,
        tuple(params),
    )
    total_fragments = cur.fetchone()[0]

    # Breakdown by molecule
    cur.execute(
        f"""
        SELECT t.molecule, COUNT(*)
        FROM trajectories t
        {where_sql}
        GROUP BY t.molecule
        ORDER BY COUNT(*) DESC, t.molecule
        """,
        tuple(params),
    )
    molecule_rows = cur.fetchall()

    # Breakdown by method
    cur.execute(
        f"""
        SELECT t.method_label, COUNT(*)
        FROM trajectories t
        {where_sql}
        GROUP BY t.method_label
        ORDER BY COUNT(*) DESC, t.method_label
        """,
        tuple(params),
    )
    method_rows = cur.fetchall()

    # Breakdown by energy
    cur.execute(
        f"""
        SELECT t.energy_label, COUNT(*)
        FROM trajectories t
        {where_sql}
        GROUP BY t.energy_label
        ORDER BY COUNT(*) DESC, t.energy_label
        """,
        tuple(params),
    )
    energy_rows = cur.fetchall()

    conn.close()

    print("Database summary")
    print("----------------")
    print(f"Filters")
    print(f"  molecule         : {molecule}")
    print(f"  isomer           : {isomer}")
    print(f"  method           : {method}")
    print(f"  energy_label     : {energy_label}")
    print()
    print(f"Trajectories       : {n_traj}")
    print(f"Total frames       : {int(total_frames)}")
    print(f"Average frames     : {avg_frames:.2f}" if n_traj else "Average frames     : 0.00")
    print(f"Min frames         : {int(min_frames)}")
    print(f"Max frames         : {int(max_frames)}")
    print(f"Molecules          : {n_molecules}")
    print(f"Method labels      : {n_methods}")
    print(f"Energy labels      : {n_energies}")
    print(f"Fragment analyses  : {n_fragment_analyses}")
    print(f"Stored fragments   : {int(total_fragments)}")

    if molecule_rows:
        print()
        print("Breakdown by molecule")
        print("---------------------")
        for mol, count in molecule_rows:
            print(f"{str(mol):20s} {count}")

    if method_rows:
        print()
        print("Breakdown by method_label")
        print("-------------------------")
        for meth, count in method_rows:
            print(f"{str(meth):20s} {count}")

    if energy_rows:
        print()
        print("Breakdown by energy_label")
        print("-------------------------")
        for en, count in energy_rows:
            print(f"{str(en):20s} {count}")


def show_trajectory(db_path: str, traj_uid: str):
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    cur.execute(
        """
        SELECT
            t.traj_uid,
            t.traj_code,
            t.input_id,
            t.molecule,
            t.isomer,
            t.method_label,
            t.energy_label,
            t.run_id,
            t.original_run_dir,
            t.source_filename,
            t.source_abspath,
            t.sha256,
            t.natoms,
            t.nframes,
            t.created_at,
            m.input_filename,
            m.basis,
            m.charge,
            m.spinmult,
            m.method,
            m.dispersion,
            m.run_type,
            m.nstep,
            m.timestep,
            m.thermostat,
            m.rescalefreq,
            m.tinit,
            m.t0,
            m.gpus,
            fa.fragment_count,
            fa.analyzed_frame_number,
            fa.analysis_method
        FROM trajectories t
        LEFT JOIN md_inputs m ON t.input_id = m.input_id
        LEFT JOIN fragment_analysis fa ON t.traj_uid = fa.traj_uid
        WHERE t.traj_uid = ?
        """,
        (traj_uid,),
    )
    row = cur.fetchone()

    if row is None:
        conn.close()
        print(f"No trajectory found for traj_uid='{traj_uid}'")
        return

    cur.execute(
        """
        SELECT COUNT(*), MIN(start_frame), MAX(end_frame), MIN(compression), MAX(compression)
        FROM frame_blocks
        WHERE traj_uid = ?
        """,
        (traj_uid,),
    )
    block_info = cur.fetchone()

    cur.execute(
        """
        SELECT fragment_index, formula, exact_mass, charge_guess, n_atoms
        FROM fragments
        WHERE traj_uid = ?
        ORDER BY fragment_index
        """,
        (traj_uid,),
    )
    fragment_rows = cur.fetchall()

    conn.close()

    (
        traj_uid,
        traj_code,
        input_id,
        molecule,
        isomer,
        method_label,
        energy_label,
        run_id,
        original_run_dir,
        source_filename,
        source_abspath,
        sha256,
        natoms,
        nframes,
        created_at,
        input_filename,
        basis,
        charge,
        spinmult,
        method,
        dispersion,
        run_type,
        nstep,
        timestep,
        thermostat,
        rescalefreq,
        tinit,
        t0,
        gpus,
        fragment_count,
        analyzed_frame_number,
        analysis_method,
    ) = row

    n_blocks, min_start, max_end, min_comp, max_comp = block_info

    print("Trajectory")
    print("----------")
    print(f"traj_uid             : {traj_uid}")
    print(f"traj_code            : {traj_code}")
    print(f"input_id             : {input_id}")
    print(f"molecule             : {molecule}")
    print(f"isomer               : {isomer}")
    print(f"method_label         : {method_label}")
    print(f"energy_label         : {energy_label}")
    print(f"run_id               : {run_id}")
    print(f"original_run_dir     : {original_run_dir}")
    print(f"source_filename      : {source_filename}")
    print(f"source_abspath       : {source_abspath}")
    print(f"sha256               : {sha256}")
    print(f"natoms               : {natoms}")
    print(f"nframes              : {nframes}")
    print(f"created_at           : {created_at}")
    print()
    print("Input")
    print("-----")
    print(f"input_filename       : {input_filename}")
    print(f"basis                : {basis}")
    print(f"charge               : {charge}")
    print(f"spinmult             : {spinmult}")
    print(f"method               : {method}")
    print(f"dispersion           : {dispersion}")
    print(f"run_type             : {run_type}")
    print(f"nstep                : {nstep}")
    print(f"timestep             : {timestep}")
    print(f"thermostat           : {thermostat}")
    print(f"rescalefreq          : {rescalefreq}")
    print(f"tinit                : {tinit}")
    print(f"t0                   : {t0}")
    print(f"gpus                 : {gpus}")
    print()
    print("Blocks")
    print("------")
    print(f"n_blocks             : {n_blocks}")
    print(f"frame range          : {min_start} -> {max_end}")
    if min_comp == max_comp:
        print(f"compression          : {min_comp}")
    else:
        print(f"compression          : {min_comp} / {max_comp}")
    print()
    print("Fragments")
    print("---------")
    print(f"fragment_count       : {fragment_count}")
    print(f"analyzed_frame_number: {analyzed_frame_number}")
    print(f"analysis_method      : {analysis_method}")

    if fragment_rows:
        for fragment_index, formula, exact_mass, charge_guess, n_atoms in fragment_rows:
            print(
                f"  Fragment {fragment_index}: "
                f"formula={formula}, mass={exact_mass:.6f}, "
                f"charge_guess={charge_guess}, n_atoms={n_atoms}"
            )


def show_input_for_trajectory(db_path: str, traj_uid: str):
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    cur.execute(
        """
        SELECT
            m.input_id,
            m.input_filename,
            m.input_sha256,
            m.basis,
            m.has_basis,
            m.coordinates_file,
            m.charge,
            m.spinmult,
            m.method,
            m.dispersion,
            m.has_dispersion,
            m.run_type,
            m.nstep,
            m.timestep,
            m.thermostat,
            m.rescalefreq,
            m.tinit,
            m.t0,
            m.gpus,
            m.created_at
        FROM trajectories t
        LEFT JOIN md_inputs m ON t.input_id = m.input_id
        WHERE t.traj_uid = ?
        """,
        (traj_uid,),
    )
    row = cur.fetchone()
    conn.close()

    if row is None:
        print(f"No trajectory found for traj_uid='{traj_uid}'")
        return

    if row[0] is None:
        print(f"Trajectory '{traj_uid}' has no associated md.in entry.")
        return

    (
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
        created_at,
    ) = row

    print("MD input")
    print("--------")
    print(f"input_id             : {input_id}")
    print(f"input_filename       : {input_filename}")
    print(f"input_sha256         : {input_sha256}")
    print(f"basis                : {basis}")
    print(f"has_basis            : {has_basis}")
    print(f"coordinates_file     : {coordinates_file}")
    print(f"charge               : {charge}")
    print(f"spinmult             : {spinmult}")
    print(f"method               : {method}")
    print(f"dispersion           : {dispersion}")
    print(f"has_dispersion       : {has_dispersion}")
    print(f"run_type             : {run_type}")
    print(f"nstep                : {nstep}")
    print(f"timestep             : {timestep}")
    print(f"thermostat           : {thermostat}")
    print(f"rescalefreq          : {rescalefreq}")
    print(f"tinit                : {tinit}")
    print(f"t0                   : {t0}")
    print(f"gpus                 : {gpus}")
    print(f"created_at           : {created_at}")