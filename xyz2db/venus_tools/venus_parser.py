# xyz2db/venus_tools/venus_parser.py

import re
import numpy as np


TRAJ_HEADER_RE = re.compile(r"TRAJECTORY NUMBER\s+(\d+)")
CYCLE_TIME_RE = re.compile(
    r"THE CYCLE COUNT IS:\s*(\d+)\s+TIME:\s*([0-9.+\-Ee]+)"
)
TOTAL_ENERGY_RE = re.compile(r"TOTAL ENERGY:\s*([0-9.+\-Ee]+)")


def build_venus_comment(energy_kcal, cycle_count, time_raw, time_ps, traj_number):
    return (
        f"E={energy_kcal:.9f} kcal/mol "
        f"frame {cycle_count} "
        f"time_raw {time_raw:.3f} "
        f"time_ps {time_ps:.6f} "
        f"traj {traj_number} "
        f"source VENUS"
    )


def parse_venus_output(out_path: str, atom_symbols, timestep_venus: float, ns: int):
    """
    Parse one VENUS .out file and return a dictionary:
    {
      traj_number: [
        {
          "cycle_count": ...,
          "time_raw": ...,
          "time_ps": ...,
          "energy": ...,
          "coords": np.ndarray shape (natoms, 3),
          "comment": ...
        },
        ...
      ],
      ...
    }

    Time convention used:
        time_ps = cycle_count * timestep_venus / 100.0
    """
    natoms = len(atom_symbols)

    with open(out_path, "r", encoding="utf-8", errors="replace") as f:
        lines = f.readlines()

    trajectories = {}
    seen = set()
    i = 0
    n = len(lines)

    while i < n:
        line = lines[i]

        m_traj = TRAJ_HEADER_RE.search(line)
        if not m_traj:
            i += 1
            continue

        traj_number = int(m_traj.group(1))

        if i + 1 >= n:
            break

        m_cycle = CYCLE_TIME_RE.search(lines[i + 1])
        if not m_cycle:
            i += 1
            continue

        cycle_count = int(m_cycle.group(1))
        time_raw = float(m_cycle.group(2))

        energy = None
        q_header_idx = None

        j = i + 2
        while j < n:
            line_j = lines[j]

            m_energy = TOTAL_ENERGY_RE.search(line_j)
            if m_energy:
                energy = float(m_energy.group(1))

            if "Q" in line_j and "P" in line_j:
                q_header_idx = j
                break

            if TRAJ_HEADER_RE.search(line_j):
                break

            j += 1

        if energy is None or q_header_idx is None:
            i += 1
            continue

        coord_lines_start = q_header_idx + 1
        coord_lines_end = coord_lines_start + natoms

        if coord_lines_end > n:
            break

        coords = []
        ok = True

        for k in range(coord_lines_start, coord_lines_end):
            parts = lines[k].split()
            if len(parts) < 6:
                ok = False
                break
            try:
                x = float(parts[0])
                y = float(parts[1])
                z = float(parts[2])
            except ValueError:
                ok = False
                break
            coords.append([x, y, z])

        if not ok or len(coords) != natoms:
            i += 1
            continue

        coords = np.asarray(coords, dtype=np.float32)

        # Fixed VENUS convention:
        # final trajectory always scales to ns * timestep_venus / 100 ps
        time_ps = cycle_count * float(timestep_venus) / 100.0

        comment = build_venus_comment(
            energy_kcal=energy,
            cycle_count=cycle_count,
            time_raw=time_raw,
            time_ps=time_ps,
            traj_number=traj_number,
        )

        # Avoid duplicate frame insertion if the same block appears twice
        unique_key = (traj_number, cycle_count)
        if unique_key not in seen:
            frame = {
                "cycle_count": cycle_count,
                "time_raw": time_raw,
                "time_ps": time_ps,
                "energy": energy,
                "coords": coords,
                "comment": comment,
            }
            trajectories.setdefault(traj_number, []).append(frame)
            seen.add(unique_key)

        i = coord_lines_end

    # Ensure every trajectory is sorted by cycle_count
    for traj_number in trajectories:
        trajectories[traj_number].sort(key=lambda x: x["cycle_count"])

    return trajectories