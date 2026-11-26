# xyz2db/kinetics_tools/kinetics.py

import csv
import math
from collections import Counter


def safe_mean(values):
    if not values:
        return None
    return sum(values) / len(values)


def safe_median(values):
    if not values:
        return None
    vals = sorted(values)
    n = len(vals)
    mid = n // 2
    if n % 2 == 1:
        return vals[mid]
    return 0.5 * (vals[mid - 1] + vals[mid])


def safe_min(values):
    return min(values) if values else None


def safe_max(values):
    return max(values) if values else None


def linear_regression(x, y):
    """
    Simple OLS linear regression:
        y = a + b x

    Returns dict with:
        slope, intercept, r2, slope_stderr
    """
    n = len(x)
    if n < 2:
        raise ValueError("Need at least 2 points for linear regression.")

    x_mean = sum(x) / n
    y_mean = sum(y) / n

    sxx = sum((xi - x_mean) ** 2 for xi in x)
    sxy = sum((xi - x_mean) * (yi - y_mean) for xi, yi in zip(x, y))
    syy = sum((yi - y_mean) ** 2 for yi in y)

    if sxx == 0:
        raise ValueError("Regression failed: zero variance in x.")

    slope = sxy / sxx
    intercept = y_mean - slope * x_mean

    y_hat = [intercept + slope * xi for xi in x]
    ss_res = sum((yi - yhi) ** 2 for yi, yhi in zip(y, y_hat))
    ss_tot = syy
    r2 = 1.0 if ss_tot == 0 else (1.0 - ss_res / ss_tot)

    slope_stderr = None
    if n > 2:
        mse = ss_res / (n - 2)
        slope_stderr = math.sqrt(mse / sxx)

    return {
        "slope": slope,
        "intercept": intercept,
        "r2": r2,
        "slope_stderr": slope_stderr,
    }


def normal_95_ci(value, stderr):
    if value is None or stderr is None:
        return None, None
    delta = 1.96 * stderr
    return value - delta, value + delta


def detect_disappearance_time(frame_records, persist_frames=5):
    """
    frame_records: iterable of dicts with keys:
        frame_idx, time_ps, intact, fragment_count

    disappearance criterion:
        fragment_count > 1 for at least persist_frames consecutive frames

    Returns dict with:
        event_occurred
        event_time_ps
        event_frame_idx
        followup_time_ps
        n_frames_scanned
        max_fragment_count
    """
    broken_streak = 0
    first_break_time = None
    first_break_idx = None

    last_time_ps = None
    n_scanned = 0
    max_fragment_count = 1

    for rec in frame_records:
        frame_idx = rec["frame_idx"]
        time_ps = rec["time_ps"]
        intact = rec["intact"]
        fragment_count = rec["fragment_count"]

        n_scanned += 1
        last_time_ps = time_ps
        if fragment_count is not None:
            max_fragment_count = max(max_fragment_count, fragment_count)

        if intact:
            broken_streak = 0
            first_break_time = None
            first_break_idx = None
        else:
            if broken_streak == 0:
                first_break_time = time_ps
                first_break_idx = frame_idx
            broken_streak += 1

            if broken_streak >= persist_frames:
                return {
                    "event_occurred": True,
                    "event_time_ps": first_break_time,
                    "event_frame_idx": first_break_idx,
                    "followup_time_ps": last_time_ps,
                    "n_frames_scanned": n_scanned,
                    "max_fragment_count": max_fragment_count,
                }

    return {
        "event_occurred": False,
        "event_time_ps": None,
        "event_frame_idx": None,
        "followup_time_ps": last_time_ps,
        "n_frames_scanned": n_scanned,
        "max_fragment_count": max_fragment_count,
    }


def build_survival_curve(event_rows, window_mode="censor"):
    """
    event_rows: list of dicts with:
        traj_uid, event_occurred, event_time_ps, followup_time_ps

    window_mode:
        - "censor": use all follow-up times directly
        - "common": truncate to the minimum followup among all trajectories

    Returns:
        {
          "rows": [...],
          "common_window_ps": ...,
          "n0": ...
        }

    Each survival row contains:
        time_ps, n_at_risk, n_surviving, survival, ln_survival,
        n_events_at_t, n_censored_before_t
    """
    if not event_rows:
        raise ValueError("No event rows available to build survival curve.")

    followups = [r["followup_time_ps"] for r in event_rows if r["followup_time_ps"] is not None]
    if not followups:
        raise ValueError("No valid follow-up times available.")

    common_window_ps = min(followups)

    processed = []
    for r in event_rows:
        event = bool(r["event_occurred"])
        t_event = r["event_time_ps"]
        t_follow = r["followup_time_ps"]

        if t_follow is None:
            continue

        if window_mode == "common":
            t_follow_eff = min(t_follow, common_window_ps)
            if event and t_event is not None and t_event <= common_window_ps:
                processed.append({
                    "traj_uid": r["traj_uid"],
                    "event": 1,
                    "time_ps": t_event,
                    "followup_time_ps": t_follow_eff,
                })
            else:
                processed.append({
                    "traj_uid": r["traj_uid"],
                    "event": 0,
                    "time_ps": t_follow_eff,
                    "followup_time_ps": t_follow_eff,
                })
        elif window_mode == "censor":
            processed.append({
                "traj_uid": r["traj_uid"],
                "event": 1 if event else 0,
                "time_ps": t_event if event else t_follow,
                "followup_time_ps": t_follow,
            })
        else:
            raise ValueError("window_mode must be 'censor' or 'common'")

    if not processed:
        raise ValueError("No processed rows for survival curve.")

    # Unique event times only for survival rows
    unique_times = sorted({
        r["time_ps"]
        for r in processed
        if r["time_ps"] is not None and r["event"] == 1
    })

    n0 = len(processed)
    out_rows = []

    for t in unique_times:
        n_at_risk = sum(1 for r in processed if r["followup_time_ps"] >= t)
        n_events_at_t = sum(1 for r in processed if r["event"] == 1 and r["time_ps"] == t)
        n_censored_before_t = sum(1 for r in processed if r["event"] == 0 and r["time_ps"] < t)

        n_surviving = sum(
            1 for r in processed
            if (r["event"] == 0 and r["followup_time_ps"] >= t)
            or (r["event"] == 1 and r["time_ps"] > t)
        )

        survival = n_surviving / n0 if n0 else None
        ln_survival = math.log(survival) if survival is not None and survival > 0 else None

        out_rows.append({
            "time_ps": t,
            "n_at_risk": n_at_risk,
            "n_events_at_t": n_events_at_t,
            "n_censored_before_t": n_censored_before_t,
            "n_surviving": n_surviving,
            "n0": n0,
            "survival": survival,
            "ln_survival": ln_survival,
        })

    return {
        "rows": out_rows,
        "common_window_ps": common_window_ps,
        "n0": n0,
        "processed_rows": processed,
    }


def fit_k_regression_from_survival(survival_rows, min_points=5, min_survivors=2):
    """
    Fit:
        ln(S(t)) = a - k t

    Uses rows with:
        ln_survival not None
        n_surviving >= min_survivors
    """
    fit_rows = [
        r for r in survival_rows
        if r["ln_survival"] is not None and r["n_surviving"] >= min_survivors
    ]

    if len(fit_rows) < min_points:
        return {
            "ok": False,
            "reason": f"Not enough fit points: {len(fit_rows)} < {min_points}",
        }

    x = [r["time_ps"] for r in fit_rows]
    y = [r["ln_survival"] for r in fit_rows]

    reg = linear_regression(x, y)
    slope = reg["slope"]
    k = -slope

    if k <= 0:
        return {
            "ok": False,
            "reason": "Estimated k from regression is non-positive.",
            "raw_regression": reg,
        }

    stderr_k = reg["slope_stderr"]
    ci_low, ci_high = normal_95_ci(k, stderr_k)
    half_life_ps = math.log(2.0) / k if k > 0 else None

    return {
        "ok": True,
        "k_regression_ps^-1": k,
        "k_regression_stderr": stderr_k,
        "k_regression_ci95_low": ci_low,
        "k_regression_ci95_high": ci_high,
        "half_life_regression_ps": half_life_ps,
        "intercept": reg["intercept"],
        "r2": reg["r2"],
        "n_fit_points": len(fit_rows),
        "fit_start_ps": min(x),
        "fit_end_ps": max(x),
    }


def fit_k_mle_exponential(event_rows):
    """
    Exponential MLE with right censoring:
        k_MLE = d / sum(t_i)

    where:
        d = number of events
        t_i = follow-up time if censored, event time if event observed
    """
    usable = []
    for r in event_rows:
        if r["event_occurred"]:
            t = r["event_time_ps"]
        else:
            t = r["followup_time_ps"]
        if t is not None:
            usable.append((1 if r["event_occurred"] else 0, t))

    if not usable:
        return {
            "ok": False,
            "reason": "No usable rows for MLE.",
        }

    d = sum(event for event, t in usable)
    total_time = sum(t for event, t in usable)

    if d <= 0 or total_time <= 0:
        return {
            "ok": False,
            "reason": "MLE requires at least one event and positive total follow-up time.",
        }

    k = d / total_time
    stderr = k / math.sqrt(d)
    ci_low, ci_high = normal_95_ci(k, stderr)
    half_life_ps = math.log(2.0) / k if k > 0 else None

    return {
        "ok": True,
        "k_mle_ps^-1": k,
        "k_mle_stderr": stderr,
        "k_mle_ci95_low": ci_low,
        "k_mle_ci95_high": ci_high,
        "half_life_mle_ps": half_life_ps,
        "n_events_mle": d,
        "total_followup_ps": total_time,
    }


def summarize_event_rows(event_rows):
    followups = [r["followup_time_ps"] for r in event_rows if r["followup_time_ps"] is not None]
    event_times = [r["event_time_ps"] for r in event_rows if r["event_occurred"] and r["event_time_ps"] is not None]

    n_total = len(event_rows)
    n_events = sum(1 for r in event_rows if r["event_occurred"])
    n_censored = n_total - n_events
    event_fraction = (n_events / n_total) if n_total else None

    return {
        "n_trajectories_total": n_total,
        "n_events": n_events,
        "n_censored": n_censored,
        "event_fraction": event_fraction,
        "mean_followup_ps": safe_mean(followups),
        "median_followup_ps": safe_median(followups),
        "min_followup_ps": safe_min(followups),
        "max_followup_ps": safe_max(followups),
        "mean_event_time_ps": safe_mean(event_times),
        "median_event_time_ps": safe_median(event_times),
        "min_event_time_ps": safe_min(event_times),
        "max_event_time_ps": safe_max(event_times),
    }


def build_warnings(summary_stats, reg_stats, mle_stats):
    warnings = []

    if summary_stats["n_events"] < 10:
        warnings.append("few_events")

    if summary_stats["event_fraction"] is not None and summary_stats["event_fraction"] < 0.2:
        warnings.append("high_censoring")

    if reg_stats.get("ok") and reg_stats.get("r2") is not None and reg_stats["r2"] < 0.95:
        warnings.append("low_r2")

    if reg_stats.get("ok") and mle_stats.get("ok"):
        k_reg = reg_stats["k_regression_ps^-1"]
        k_mle = mle_stats["k_mle_ps^-1"]
        if k_reg > 0 and k_mle > 0:
            rel_diff = abs(k_reg - k_mle) / max(k_reg, k_mle)
            if rel_diff > 0.15:
                warnings.append("regression_mle_discrepancy")

    if summary_stats["max_followup_ps"] is not None and summary_stats["max_followup_ps"] < 1.0:
        warnings.append("short_time_window")

    return warnings


def compute_global_kinetics_from_events(
    event_rows,
    molecule=None,
    isomer=None,
    method=None,
    energy_label=None,
    persist_frames=5,
    window_mode="censor",
    min_points=5,
):
    summary_stats = summarize_event_rows(event_rows)

    survival = build_survival_curve(event_rows, window_mode=window_mode)
    survival_rows = survival["rows"]

    reg_stats = fit_k_regression_from_survival(
        survival_rows,
        min_points=min_points,
        min_survivors=2,
    )

    mle_stats = fit_k_mle_exponential(event_rows)
    warnings = build_warnings(summary_stats, reg_stats, mle_stats)

    result = {
        "molecule": molecule,
        "isomer": isomer,
        "method_label": method,
        "energy_label": energy_label,
        "persist_frames": persist_frames,
        "window_mode": window_mode,
        "common_window_ps": survival["common_window_ps"],
        **summary_stats,
        "warnings": warnings,
        "fit_ok": bool(reg_stats.get("ok")) or bool(mle_stats.get("ok")),
    }

    result.update(reg_stats)
    result.update(mle_stats)

    return result, survival_rows


def export_event_rows_csv(event_rows, output_csv):
    header = [
        "traj_uid",
        "traj_code",
        "molecule",
        "isomer",
        "method_label",
        "energy_label",
        "event_occurred",
        "event_time_ps",
        "event_frame_idx",
        "followup_time_ps",
        "n_frames_scanned",
        "max_fragment_count",
    ]
    with open(output_csv, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=header)
        w.writeheader()
        for row in event_rows:
            w.writerow({k: row.get(k) for k in header})


def export_survival_csv(survival_rows, output_csv):
    header = [
        "time_ps",
        "n_at_risk",
        "n_events_at_t",
        "n_censored_before_t",
        "n_surviving",
        "n0",
        "survival",
        "ln_survival",
    ]
    with open(output_csv, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=header)
        w.writeheader()
        for row in survival_rows:
            w.writerow({k: row.get(k) for k in header})


def export_summary_csv(summary_row, output_csv):
    keys = sorted(summary_row.keys())
    with open(output_csv, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=keys)
        w.writeheader()
        w.writerow(summary_row)