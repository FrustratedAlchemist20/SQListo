# xyz2db/venus_tools/venus_store.py

import hashlib
import json
import os
from io import BytesIO
import lzma

import numpy as np

from ..db import init_db
from ..config import DEFAULT_BLOCK_SIZE, DEFAULT_XYZ_NAME
from ..venus_tools.venus_input import parse_venus_input
from ..venus_tools.venus_parser import parse_venus_output

# Reuse chemistry data from the main project
from ..chemistry import SYMBOL_TO_Z as ATOMIC_NUMBERS

# Try to reuse the main serializer if available
try:
    from ..compression import serialize_block as _project_serialize_block
except ImportError:
    _project_serialize_block = None

# Optional: try to reuse the same auto-db naming logic as the main workflow
try:
    from ..ids import CODE_MAP
except ImportError:
    CODE_MAP = None


def _make_input_id(raw_input_text: str):
    sha = hashlib.sha256(raw_input_text.encode("utf-8")).hexdigest()
    return f"inp_{sha[:20]}", sha


def _make_traj_uid(payload_seed: str):
    sha = hashlib.sha256(payload_seed.encode("utf-8")).hexdigest()
    return f"traj_{sha[:24]}"


def _serialize_block(coords_block, comments_block, energies_block):
    """
    Prefer the main project serializer if available.
    Otherwise use a local fallback compatible with npz + lzma storage.
    """
    if _project_serialize_block is not None:
        return _project_serialize_block(coords_block, comments_block, energies_block)

    bio = BytesIO()
    np.savez_compressed(
        bio,
        coords=np.asarray(coords_block, dtype=np.float32),
        comments=np.asarray(comments_block, dtype=object),
        energies=np.asarray(energies_block, dtype=np.float64),
    )
    return lzma.compress(bio.getvalue())


def _normalize_energy_label(label):
    if label is None:
        return None
    txt = str(label).strip()
    txt = txt.replace(".0", "")
    return txt


def _abbrev_from_code_map(section, value, default="UNK"):
    if value is None:
        return default
    if CODE_MAP is None:
        return str(value)
    return CODE_MAP.get(section, {}).get(value, str(value))


def _resolve_auto_db_name(db_path, molecule, isomer, method_label, energy_label):
    """
    Build a filename similar in spirit to the existing auto naming:
    molecule[_isomer]_method_energy.db
    """
    if db_path != "auto":
        return db_path

    mol_code = _abbrev_from_code_map("molecule", molecule, "unk").lower()
    iso_code = str(isomer).lower() if isomer else None
    method_code = _abbrev_from_code_map("method", method_label, "unk").lower()
    energy_code = _abbrev_from_code_map("energy", energy_label, "unk").lower()

    parts = [mol_code]
    if iso_code:
        parts.append(iso_code)
    parts.extend([method_code, energy_code])

    return "_".join(parts) + ".db"


def _store_md_input(conn, venus_meta):
    input_id, input_sha256 = _make_input_id(venus_meta["raw_input_text"])
    cur = conn.cursor()

    cur.execute(
        """
        INSERT OR IGNORE INTO md_inputs (
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
            venus_meta["input_filename"],
            input_sha256,
            None,
            0,
            None,
            venus_meta["charge_from_input"],
            1,
            venus_meta["method_from_input"],
            None,
            0,
            "venus_md",
            venus_meta["ns"],
            venus_meta["timestep_venus"],
            None,  # thermostat is not a literal input keyword for VENUS here
            None,
            None,
            None,
            None,
            venus_meta["raw_input_text"],
            venus_meta["energy_label_factor"],
            venus_meta["energy_temperature_K"],
            venus_meta["energy_kcal_mol"],
            venus_meta["zpe_kcal_mol"],
            venus_meta["dof"],
        ),
    )

    return input_id


def _make_traj_code(molecule, isomer, method_label, energy_label, sim_id, traj_number):
    parts = []
    parts.append(molecule if molecule else "UNK")
    if isomer:
        parts.append(isomer)
    parts.append(method_label if method_label else "UNK")
    parts.append(energy_label if energy_label else "UNK")
    parts.append(f"SIM{sim_id:03d}")
    parts.append(f"T{traj_number:03d}")
    return "_".join(parts)


def _get_atomic_numbers(atom_symbols):
    try:
        return np.asarray([ATOMIC_NUMBERS[s] for s in atom_symbols], dtype=np.uint8)
    except KeyError as e:
        raise ValueError(f"Unsupported atomic symbol in VENUS input: {e}")


def _store_one_venus_trajectory(
    conn,
    frames,
    out_path,
    input_id,
    molecule,
    isomer,
    method_label,
    energy_label,
    sim_id,
    traj_number,
    atom_symbols,
    block_size=DEFAULT_BLOCK_SIZE,
):
    cur = conn.cursor()

    if not frames:
        return None, False

    original_run_dir = f"SIM{sim_id:03d}_TRAJ{traj_number:03d}"

    # We want restore/restore-all to reconstruct coors.xyz, not the raw VENUS .out
    source_filename = DEFAULT_XYZ_NAME
    source_abspath = os.path.abspath(out_path)

    traj_code = _make_traj_code(
        molecule=molecule,
        isomer=isomer,
        method_label=method_label,
        energy_label=energy_label,
        sim_id=sim_id,
        traj_number=traj_number,
    )

    natoms = len(atom_symbols)
    nframes = len(frames)
    atomic_numbers = _get_atomic_numbers(atom_symbols)

    seed_parts = [
        source_abspath,
        str(sim_id),
        str(traj_number),
        str(nframes),
        str(frames[0]["cycle_count"]) if frames else "0",
        str(frames[-1]["cycle_count"]) if frames else "0",
    ]
    traj_uid = _make_traj_uid("|".join(seed_parts))

    sha_seed = json.dumps(
        {
            "source": source_abspath,
            "sim_id": sim_id,
            "traj_number": traj_number,
            "cycles": [f["cycle_count"] for f in frames],
            "energies": [float(f["energy"]) for f in frames],
        },
        sort_keys=True,
    )
    sha256 = hashlib.sha256(sha_seed.encode("utf-8")).hexdigest()

    extra_json = json.dumps(
        {
            "source_program": "VENUS",
            "source_out_file": os.path.basename(out_path),
            "source_out_abspath": source_abspath,
            "sim_id": sim_id,
            "traj_number": traj_number,
            "time_units_raw": "venus_internal",
            "time_ps_formula": "cycle_count * timestep_venus / 100.0",
            "energy_units": "kcal/mol",
        }
    )

    cur.execute(
        """
        INSERT OR IGNORE INTO trajectories (
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
            atomic_numbers,
            symbols_json,
            extra_json
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            traj_uid,
            traj_code,
            input_id,
            molecule,
            isomer,
            method_label,
            energy_label,
            sim_id * 1000 + traj_number,
            original_run_dir,
            source_filename,
            source_abspath,
            sha256,
            natoms,
            nframes,
            atomic_numbers.tobytes(),
            json.dumps(atom_symbols),
            extra_json,
        ),
    )

    # If already existed, skip blocks to avoid duplicates
    cur.execute("SELECT COUNT(*) FROM frame_blocks WHERE traj_uid = ?", (traj_uid,))
    if cur.fetchone()[0] > 0:
        return traj_uid, False

    for block_index, start in enumerate(range(0, nframes, block_size)):
        block_frames = frames[start : start + block_size]

        coords_block = np.asarray([f["coords"] for f in block_frames], dtype=np.float32)
        comments_block = [f["comment"] for f in block_frames]
        energies_block = [float(f["energy"]) for f in block_frames]

        payload = _serialize_block(coords_block, comments_block, energies_block)

        cur.execute(
            """
            INSERT INTO frame_blocks (
                traj_uid,
                block_index,
                start_frame,
                end_frame,
                nframes,
                compression,
                payload
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                traj_uid,
                block_index,
                start,
                start + len(block_frames) - 1,
                len(block_frames),
                "lzma+npz",
                payload,
            ),
        )

    return traj_uid, True


def store_one_venus_output(
    out_path,
    db_path,
    input_path,
    molecule=None,
    isomer=None,
    method=None,
    energy_label=None,
    block_size=DEFAULT_BLOCK_SIZE,
):
    sim_dir = os.path.dirname(os.path.abspath(out_path))
    sim_name = os.path.basename(sim_dir)

    try:
        sim_id = int("".join(ch for ch in sim_name if ch.isdigit()))
    except ValueError:
        raise ValueError(f"Could not parse SIM numeric identifier from folder name: {sim_name}")

    venus_meta = parse_venus_input(input_path)

    method_label = method if method is not None else venus_meta["method_from_input"]
    energy_label_final = energy_label if energy_label is not None else venus_meta["energy_label_from_input"]
    energy_label_final = _normalize_energy_label(energy_label_final)

    atom_symbols = venus_meta["atom_symbols"]
    if not atom_symbols:
        raise ValueError("Could not parse QM atom labels from the VENUS input file.")

    if venus_meta["timestep_venus"] is None or venus_meta["ns"] is None:
        raise ValueError(
            "Could not parse timestep_venus or ns from the VENUS input file."
        )

    db_path = _resolve_auto_db_name(
        db_path=db_path,
        molecule=molecule,
        isomer=isomer,
        method_label=method_label,
        energy_label=energy_label_final,
    )

    conn = init_db(db_path)
    input_id = _store_md_input(conn, venus_meta)

    trajectories = parse_venus_output(
        out_path=out_path,
        atom_symbols=atom_symbols,
        timestep_venus=venus_meta["timestep_venus"],
        ns=venus_meta["ns"],
    )

    if not trajectories:
        conn.close()
        print(f"Skipping empty or unreadable VENUS output -> {out_path}")
        return

    stored = 0
    skipped = 0

    for traj_number, frames in sorted(trajectories.items()):
        if not frames:
            skipped += 1
            print(f"Skipped empty VENUS trajectory ({sim_name}, traj {traj_number})")
            continue

        traj_uid, inserted = _store_one_venus_trajectory(
            conn=conn,
            frames=frames,
            out_path=out_path,
            input_id=input_id,
            molecule=molecule,
            isomer=isomer,
            method_label=method_label,
            energy_label=energy_label_final,
            sim_id=sim_id,
            traj_number=traj_number,
            atom_symbols=atom_symbols,
            block_size=block_size,
        )

        if inserted:
            stored += 1
            print(f"Stored VENUS trajectory -> {traj_uid} ({sim_name}, traj {traj_number})")
        else:
            skipped += 1
            print(f"Skipped duplicate VENUS trajectory -> {traj_uid} ({sim_name}, traj {traj_number})")

    conn.commit()
    conn.close()

    print(f"Output database: {os.path.abspath(db_path)}")
    print(f"Done. Stored {stored} VENUS trajectory(ies) from one output.")
    print(f"Skipped duplicates/empty: {skipped}")


def store_all_venus_from_sims(
    root_dir,
    db_path,
    input_path=None,
    molecule=None,
    isomer=None,
    method=None,
    energy_label=None,
    block_size=DEFAULT_BLOCK_SIZE,
):
    if input_path is None:
        inp_candidates = [
            os.path.join(root_dir, x)
            for x in os.listdir(root_dir)
            if x.lower().endswith(".inp")
        ]
        if len(inp_candidates) != 1:
            raise ValueError("Could not determine unique VENUS input file automatically.")
        input_path = inp_candidates[0]

    venus_meta = parse_venus_input(input_path)

    method_label = method if method is not None else venus_meta["method_from_input"]
    energy_label_final = energy_label if energy_label is not None else venus_meta["energy_label_from_input"]
    energy_label_final = _normalize_energy_label(energy_label_final)

    atom_symbols = venus_meta["atom_symbols"]
    if not atom_symbols:
        raise ValueError("Could not parse QM atom labels from the VENUS input file.")

    if venus_meta["timestep_venus"] is None or venus_meta["ns"] is None:
        raise ValueError(
            "Could not parse timestep_venus or ns from the VENUS input file."
        )

    db_path = _resolve_auto_db_name(
        db_path=db_path,
        molecule=molecule,
        isomer=isomer,
        method_label=method_label,
        energy_label=energy_label_final,
    )

    conn = init_db(db_path)
    input_id = _store_md_input(conn, venus_meta)

    sim_dirs = [
        os.path.join(root_dir, x)
        for x in os.listdir(root_dir)
        if os.path.isdir(os.path.join(root_dir, x)) and x.upper().startswith("SIM")
    ]
    sim_dirs.sort()

    stored = 0
    skipped = 0

    for sim_dir in sim_dirs:
        sim_name = os.path.basename(sim_dir)
        try:
            sim_id = int("".join(ch for ch in sim_name if ch.isdigit()))
        except ValueError:
            continue

        out_files = [
            os.path.join(sim_dir, x)
            for x in os.listdir(sim_dir)
            if x.lower().endswith(".out")
        ]
        out_files.sort()

        if not out_files:
            print(f"Skipping {sim_name}: no .out files found.")
            continue

        for out_path in out_files:
            trajectories = parse_venus_output(
                out_path=out_path,
                atom_symbols=atom_symbols,
                timestep_venus=venus_meta["timestep_venus"],
                ns=venus_meta["ns"],
            )
            if not trajectories:
                skipped += 1
                print(f"Skipping empty or unreadable VENUS output -> {out_path}")
                continue

            for traj_number, frames in sorted(trajectories.items()):
                if not frames:
                    skipped += 1
                    print(f"Skipped empty VENUS trajectory ({sim_name}, traj {traj_number})")
                    continue

                traj_uid, inserted = _store_one_venus_trajectory(
                    conn=conn,
                    frames=frames,
                    out_path=out_path,
                    input_id=input_id,
                    molecule=molecule,
                    isomer=isomer,
                    method_label=method_label,
                    energy_label=energy_label_final,
                    sim_id=sim_id,
                    traj_number=traj_number,
                    atom_symbols=atom_symbols,
                    block_size=block_size,
                )

                if inserted:
                    stored += 1
                    print(f"Stored VENUS trajectory -> {traj_uid} ({sim_name}, traj {traj_number})")
                else:
                    skipped += 1
                    print(f"Skipped duplicate VENUS trajectory -> {traj_uid} ({sim_name}, traj {traj_number})")

    conn.commit()
    conn.close()

    print(f"Output database: {os.path.abspath(db_path)}")
    print(f"Done. Stored {stored} VENUS trajectory(ies).")
    print(f"Skipped duplicates/empty: {skipped}")