# xyz2db/venus_tools/venus_input.py

import os
import re

from ..energy_utils import compute_venus_energy_fields


def _extract_method_and_charge(keyword_line: str):
    """
    Example:
    'PM6 CHARGE=1 1SCF GRADIENTS XYZ'
    """
    method = None
    charge = None

    text = keyword_line.strip().strip("'").strip('"')
    parts = text.split()
    if parts:
        method = parts[0].upper()

    m = re.search(r"CHARGE\s*=\s*([+-]?\d+)", text, re.IGNORECASE)
    if m:
        charge = int(m.group(1))

    return method, charge


def _extract_energy_label(line: str):
    """
    Example:
    THERMAL FRAGMENTATION: ENMTA=405.834 kcal/mol (=ZPEx3.0)
    """
    m = re.search(r"\(=([^)]+)\)", line)
    if not m:
        return None
    raw = m.group(1).strip()
    raw = raw.replace(".0", "")
    return raw


def parse_venus_input(inp_path: str):
    with open(inp_path, "r", encoding="utf-8", errors="replace") as f:
        raw = f.read()

    lines = [line.rstrip("\n") for line in raw.splitlines()]

    result = {
        "input_filename": os.path.basename(inp_path),
        "raw_input_text": raw,
        "title_line": None,
        "nt": None,
        "ns": None,
        "nip": None,
        "ncrot": None,
        "timestep_venus": None,
        "total_ps": None,
        "method_from_input": None,
        "charge_from_input": None,
        "energy_label_from_input": None,
        "atom_symbols": None,
        "natoms": None,
        "enmta_kcal": None,
        # Derived energy fields
        "energy_label_factor": None,
        "energy_temperature_K": None,
        "energy_kcal_mol": None,
        "zpe_kcal_mol": None,
        "dof": None,
    }

    if lines:
        result["title_line"] = lines[0].strip()

    # Energy label and ENMTA
    for line in lines:
        if "THERMAL FRAGMENTATION" in line.upper():
            result["energy_label_from_input"] = _extract_energy_label(line)
            m = re.search(r"ENMTA\s*=\s*([0-9.+\-Ee]+)", line)
            if m:
                result["enmta_kcal"] = float(m.group(1))
            break

    # Method and charge from keyword line
    for line in lines:
        if "CHARGE=" in line.upper():
            method, charge = _extract_method_and_charge(line)
            result["method_from_input"] = method
            result["charge_from_input"] = charge
            break

    # Find nt,ns,nip,ncrot
    for line in lines:
        if "nt,ns,nip,ncrot" in line.lower():
            nums = line.split("!")[0].strip().rstrip(",")
            vals = [x.strip() for x in nums.split(",") if x.strip()]
            if len(vals) >= 4:
                result["nt"] = int(vals[0])
                result["ns"] = int(vals[1])
                result["nip"] = int(vals[2])
                result["ncrot"] = int(vals[3])
            break

    # Find timestep
    for line in lines:
        if "time:" in line.lower():
            nums = line.split("!")[0].strip().rstrip(",")
            try:
                result["timestep_venus"] = float(nums)
            except ValueError:
                pass
            break

    # Atom symbols
    for line in lines:
        if "QM ATOMS LABELS" in line.upper():
            symbols_txt = line.split("!")[0].strip().rstrip(",")
            symbols = [x.strip() for x in symbols_txt.split(",") if x.strip()]
            result["atom_symbols"] = symbols
            result["natoms"] = len(symbols)
            break

    # VENUS convention agreed:
    # time_ps = cycle_count * timestep_venus / 100.0
    if result["ns"] is not None and result["timestep_venus"] is not None:
        result["total_ps"] = result["ns"] * result["timestep_venus"] / 100.0

    # Derived energy fields for VENUS:
    # energy_kcal_mol is directly ENMTA
    # T = ZPE * f / (s * kB)
    energy_fields = compute_venus_energy_fields(
        enmta_kcal=result["enmta_kcal"],
        natoms=result["natoms"],
        energy_label=result["energy_label_from_input"],
    )
    result.update(energy_fields)

    return result