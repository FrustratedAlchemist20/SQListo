import os
import re
from pathlib import Path

from .storage import store_xyz_in_db


def find_run_xyz_files(root_dir: str, xyz_name: str = "coors.xyz"):
    """
    Scan a root directory looking for:
        run_XXX/**/coors.xyz

    Returns a list of tuples:
        (run_dir_name, run_id, xyz_path)
    """
    root = Path(root_dir)
    results = []

    run_pattern = re.compile(r"^run_(\d+)$", re.IGNORECASE)

    for entry in sorted(root.iterdir()):
        if not entry.is_dir():
            continue

        m = run_pattern.match(entry.name)
        if not m:
            continue

        run_id = int(m.group(1))
        run_dir_name = entry.name

        matches = list(entry.rglob(xyz_name))
        if not matches:
            continue

        # If multiple coors.xyz exist inside the same run directory,
        # keep the first one in sorted order.
        xyz_path = sorted(matches)[0]
        results.append((run_dir_name, run_id, str(xyz_path)))

    return results


def store_all_from_runs(
    root_dir: str,
    db_path: str,
    input_path: str = None,
    molecule: str = None,
    isomer: str = None,
    method: str = None,
    energy_label: str = None,
    block_size: int = 500,
    overwrite: bool = False,
    xyz_name: str = "coors.xyz",
):
    """
    Store all run_XXX trajectories found under root_dir.
    Empty or invalid XYZ files are skipped.
    """
    root_dir = os.path.abspath(root_dir)

    if input_path is None:
        candidate = os.path.join(root_dir, "md.in")
        if os.path.isfile(candidate):
            input_path = candidate

    found = find_run_xyz_files(root_dir=root_dir, xyz_name=xyz_name)

    if not found:
        print(f"No '{xyz_name}' files found under run_XXX folders in: {root_dir}")
        return []

    stored = []
    skipped_empty = []
    skipped_error = []

    print(f"Found {len(found)} trajectory file(s).")

    for run_dir_name, run_id, xyz_path in found:
        try:
            if not os.path.isfile(xyz_path):
                print(f"Skipping {xyz_path}: file does not exist.")
                skipped_error.append((run_dir_name, xyz_path, "file does not exist"))
                continue

            if os.path.getsize(xyz_path) == 0:
                print(f"Skipping {xyz_path}: empty XYZ file.")
                skipped_empty.append((run_dir_name, xyz_path))
                continue

            print(f"Storing {xyz_path} (run_id={run_id}, original_run_dir={run_dir_name})")

            traj_uid = store_xyz_in_db(
                xyz_path=xyz_path,
                db_path=db_path,
                input_path=input_path,
                block_size=block_size,
                overwrite=overwrite,
                molecule=molecule,
                isomer=isomer,
                method=method,
                energy_label=energy_label,
                run_id=run_id,
                original_run_dir=run_dir_name,
            )
            stored.append((run_dir_name, run_id, xyz_path, traj_uid))

        except Exception as e:
            print(f"Skipping {xyz_path}: {e}")
            skipped_error.append((run_dir_name, xyz_path, str(e)))
            continue

    print()
    print(f"Done. Stored {len(stored)} trajectory file(s).")
    print(f"Skipped empty files : {len(skipped_empty)}")
    print(f"Skipped error files : {len(skipped_error)}")

    return stored