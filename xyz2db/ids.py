# xyz2db/ids.py

# Unique ID generation for trajectories and inputs

import hashlib
from pathlib import Path

from .utils import sha256_file

def make_traj_uid(filepath: str, sha256_hex: str) -> str:
    base = f"{Path(filepath).name}|{sha256_hex}"
    uid = hashlib.sha256(base.encode("utf-8")).hexdigest()[:24]
    return f"traj_{uid}"

def make_input_id(input_path: str) -> tuple[str, str]:
    sha256_hex = sha256_file(input_path)
    short = hashlib.sha256(sha256_hex.encode("utf-8")).hexdigest()[:20]
    return f"inp_{short}", sha256_hex

CODE_MAP = {
    "molecule": {
        "Azaconazole": "Azc",
        "Triticonazole": "Ttzl",
        "Tebuconazole": "Tbcz",
        "Diniconazole": "Dncz",
        "Metconazole": "Mtcz",
        "Penconazole": "Pncz",
        "Triadimefon": "Tdf",
        "Triadimenol": "Tdm",
        "Fenbuconazole": "Fbcz",
        "Difenoconazole": "Dfcz",
    },
    "isomer": {
        "E": "E",
        "Z": "Z",
        "cis": "C",
        "trans": "T",
        None: "",
        "": "",
    },
    "method": {
        "PM6": "PM6",
        "uB3LYP": "UB3",
        "B3LYP": "B3",
    },
    "energy": {
        "ZPEx2": "Z2",
        "ZPEx3": "Z3",
        "De": "DE",
        "D0": "D0",
    },
}

def build_db_basename(molecule=None, isomer=None, method=None, energy=None, lowercase=True):
    mol = CODE_MAP["molecule"].get(molecule, molecule or "unknown")
    iso = CODE_MAP["isomer"].get(isomer, isomer or "")
    met = CODE_MAP["method"].get(method, method or "unknown")
    ene = CODE_MAP["energy"].get(energy, energy or "unknown")

    parts = [mol]
    if iso:
        parts.append(iso)
    parts.extend([met, ene])

    name = "_".join(parts)
    if lowercase:
        name = name.lower()

    return f"{name}.db"

def build_traj_code(molecule=None, isomer=None, method=None, energy=None, run_id=None):
    mol = CODE_MAP["molecule"].get(molecule, "UNK") if molecule else "UNK"
    iso = CODE_MAP["isomer"].get(isomer, isomer or "")
    met = CODE_MAP["method"].get(method, method or "UNK")
    ene = CODE_MAP["energy"].get(energy, energy or "UNK")

    parts = [mol]
    if iso:
        parts.append(iso)
    parts.extend([met, ene])

    if run_id is not None:
        parts.append(f"R{int(run_id):03d}")

    return "_".join(parts)
