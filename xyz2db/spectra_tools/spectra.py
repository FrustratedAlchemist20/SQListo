# xyz2db/spectra_tools/spectra.py

from collections import Counter


def make_peak_key(formula, mz, mz_decimals=5):
    return (formula, round(float(mz), mz_decimals))


def build_spectrum_rows(
    fragment_rows,
    charged_only=False,
    neutral_only=False,
    mz_min=None,
    mz_max=None,
    scale=1000.0,
    sort_by="intensity",
    mz_decimals=5,
):
    """
    fragment_rows: list of dicts with keys:
      formula, exact_mass, charge_guess

    Returns list of dicts:
      intensity, mz, formula, count
    """

    if charged_only and neutral_only:
        raise ValueError("charged_only and neutral_only cannot both be True.")

    # 1) Filter FIRST
    filtered = []
    for row in fragment_rows:
        mz = float(row["exact_mass"])
        charge_guess = row["charge_guess"] if row["charge_guess"] is not None else 0

        if charged_only and charge_guess == 0:
            continue
        if neutral_only and charge_guess != 0:
            continue
        if mz_min is not None and mz < mz_min:
            continue
        if mz_max is not None and mz > mz_max:
            continue

        filtered.append(row)

    if not filtered:
        return []

    # 2) Count ONLY the filtered rows
    counter = Counter()
    representative = {}

    for row in filtered:
        key = make_peak_key(row["formula"], row["exact_mass"], mz_decimals=mz_decimals)
        counter[key] += 1
        if key not in representative:
            representative[key] = {
                "formula": row["formula"],
                "mz": round(float(row["exact_mass"]), mz_decimals),
            }

    # 3) Recalculate the base peak AFTER filtering
    max_count = max(counter.values())
    if max_count <= 0:
        return []

    # 4) Build peaks with renormalized intensities
    peaks = []
    for key, count in counter.items():
        rep = representative[key]
        intensity = scale * count / max_count
        peaks.append(
            {
                "formula": rep["formula"],
                "mz": rep["mz"],
                "count": count,
                "intensity": intensity,
            }
        )

    if sort_by == "mz":
        peaks.sort(key=lambda x: x["mz"])
    else:
        peaks.sort(key=lambda x: (-x["intensity"], x["mz"], x["formula"]))

    return peaks