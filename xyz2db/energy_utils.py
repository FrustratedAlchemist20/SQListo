import re

KB_KCAL_MOL_K = 0.00198720425864083


def extract_energy_label_factor(label):
    if not label:
        return None
    text = str(label).strip()

    m = re.search(r"ZPEx([0-9]+(?:\.[0-9]+)?)", text, re.IGNORECASE)
    if not m:
        m = re.search(r"ZPE\s*x\s*([0-9]+(?:\.[0-9]+)?)", text, re.IGNORECASE)
    if not m:
        return None

    try:
        value = float(m.group(1))
    except ValueError:
        return None

    return int(value) if value.is_integer() else value


def compute_terachem_energy_fields(thermostat_K, natoms, energy_label):
    f = extract_energy_label_factor(energy_label)
    s = 3 * natoms - 6 if natoms is not None and natoms >= 2 else None

    energy_kcal_mol = None
    zpe_kcal_mol = None

    if thermostat_K is not None and s is not None:
        energy_kcal_mol = float(thermostat_K) * s * KB_KCAL_MOL_K / 2.0

    if energy_kcal_mol is not None and f not in (None, 0):
        zpe_kcal_mol = energy_kcal_mol / float(f)

    return {
        "energy_label_factor": f,
        "energy_temperature_K": thermostat_K,
        "energy_kcal_mol": energy_kcal_mol,
        "zpe_kcal_mol": zpe_kcal_mol,
        "dof": s,
    }


def compute_venus_energy_fields(enmta_kcal, natoms, energy_label):
    f = extract_energy_label_factor(energy_label)
    s = 3 * natoms - 6 if natoms is not None and natoms >= 2 else None

    energy_kcal_mol = enmta_kcal
    zpe_kcal_mol = None
    energy_temperature_K = None

    if energy_kcal_mol is not None and f not in (None, 0):
        zpe_kcal_mol = float(energy_kcal_mol) / float(f)

    if energy_kcal_mol is not None and s not in (None, 0):
        energy_temperature_K = float(energy_kcal_mol) / (s * KB_KCAL_MOL_K)

    return {
        "energy_label_factor": f,
        "energy_temperature_K": energy_temperature_K,
        "energy_kcal_mol": energy_kcal_mol,
        "zpe_kcal_mol": zpe_kcal_mol,
        "dof": s,
    }