"""Generate the synthetic dataset. Every athlete here is invented.

45 days of daily wellness + HRV, ~every-other-day CMJ (RSI-mod), plus daily
load (sRPE) and GPS for a 9-athlete synthetic squad, engineered so the final
morning tells a realistic multi-domain story:

  D. Silva (RHP)  REVIEW  — neuromuscular AND wellness both down (convergence)
                            during his heaviest training week (load = context)
  A. Rivera (OF)  MONITOR — autonomic: 7-day rolling HRV trending down
  R. Bennett (C)  MONITOR — neuromuscular: three declining CMJ sessions
  six others      CLEARED

Story metrics use the target-z trick: on story days the raw value is derived
from the athlete's own trailing 28-day stats — the same window the engine
uses — so the engine reproduces the story from raw readings alone. HRV is a
7-day rolling mean in the engine, so Rivera's story is a sustained week-long
decline, not a single day. Emits long-form Reading rows. No real athlete,
team, or dataset is involved.

Usage: python3 scripts/generate_data.py [--out data/synthetic.csv]
"""

from __future__ import annotations

import argparse
import csv
import random
import statistics
from datetime import date, timedelta
from pathlib import Path

BRIEF_DAY = date(2026, 7, 7)
DAYS = 45
SEED = 20260707
BASELINE_DAYS = 28
ACUTE_DAYS = 7

# id, name, pos, wellness base, hrv base, rsi base
SQUAD = [
    ("A01", "D. Silva",    "RHP", 20.0, 4.20, 0.520),
    ("A02", "A. Rivera",   "OF",  21.0, 4.35, 0.560),
    ("A03", "R. Bennett",  "C",   20.5, 4.10, 0.510),
    ("A04", "T. Nakamura", "MIF", 21.5, 4.40, 0.500),
    ("A05", "J. Okafor",   "1B",  22.0, 4.30, 0.590),
    ("A06", "M. Alvarez",  "LHP", 20.8, 4.25, 0.530),
    ("A07", "C. Boateng",  "OF",  21.2, 4.45, 0.600),
    ("A08", "L. Petrov",   "3B",  20.3, 4.15, 0.490),
    ("A09", "E. Cruz",     "RP",  19.8, 4.05, 0.460),
]

SD = {"wellness_score": 0.7, "hrv_lnrmssd": 0.16, "rsi_mod": 0.020}
SOURCE = {"wellness_score": "form", "hrv_lnrmssd": "wearable",
          "rsi_mod": "forceplate"}

# story: name -> {metric: ("today", z) or ("tail", [z...])}
STORY = {
    "D. Silva": {"rsi_mod": ("today", -1.6), "wellness_score": ("today", -1.6)},
    "A. Rivera": {"hrv_lnrmssd": ("tail", [-0.08, -0.16, -0.24, -0.32, -0.4, -0.4, -0.4])},
    "R. Bennett": {"rsi_mod": ("tail", [-0.6, -1.0, -1.4])},
}
SILVA_TARGET_ACWR = 1.52  # heavy last week, context only

# The recent window is controlled for EVERY athlete/metric so noise never
# creates a spurious flag; only the deep baseline is random. This mirrors the
# v1 generator: story metrics are scripted, everything else settles safely.
SAFE_TAIL_DAYS = 22   # covers the 14-session trend + HRV's 7-day rolling window
SAFE_WIG = 0.6        # x metric SD, alternating (nonzero baseline SD, no decline run)
SAFE_TODAY_Z = 0.35   # non-story athletes land slightly above baseline today


def trailing_stats(values):
    w = values[-BASELINE_DAYS:]
    return statistics.fmean(w), statistics.stdev(w)


def value_for_z(history, z):
    mean, sd = trailing_stats(history)
    return mean + z * sd


def solve_acute_load(prior_21, target):
    return target * sum(prior_21) / (28 - ACUTE_DAYS * target)


def generate(end: date = BRIEF_DAY, days: int = DAYS, seed: int = SEED):
    rng = random.Random(seed)
    rows: list[dict] = []
    start = end - timedelta(days=days - 1)

    for aid, name, pos, w_base, h_base, r_base in SQUAD:
        bases = {"wellness_score": w_base, "hrv_lnrmssd": h_base, "rsi_mod": r_base}
        story = STORY.get(name, {})
        hist = {m: [] for m in bases}
        loads: list[float] = []
        acute = 0.0

        def emit(day, metric, value, source):
            rows.append({"athlete_id": aid, "name": name, "pos": pos,
                         "day": day.isoformat(), "metric": metric,
                         "value": f"{value:.3f}", "source": source})

        def safe(base_val, sd, remaining):
            # deterministic alternating settle: no 2-run decline, mean ~ base
            return base_val + SAFE_WIG * sd * (1 if remaining % 2 == 0 else -1)

        for i in range(days):
            day = start + timedelta(days=i)
            remaining = days - i

            for m, base_val in bases.items():
                plan = story.get(m)
                if plan and plan[0] == "today":
                    if remaining == 1:
                        v = value_for_z(hist[m], plan[1])
                    elif remaining <= SAFE_TAIL_DAYS:
                        v = safe(base_val, SD[m], remaining)
                    else:
                        v = base_val + rng.gauss(0, SD[m])
                elif plan and plan[0] == "tail":
                    tail = plan[1]
                    n_story = len(tail) + 1
                    if remaining == 1:
                        v = value_for_z(hist[m], tail[-1])
                    elif remaining <= n_story:
                        v = value_for_z(hist[m], tail[len(tail) - remaining + 1])
                    elif remaining <= SAFE_TAIL_DAYS:
                        v = safe(base_val, SD[m], remaining)
                    else:
                        v = base_val + rng.gauss(0, SD[m])
                else:  # non-story metric: settle safely, land today above baseline
                    if remaining == 1:
                        v = base_val + SAFE_TODAY_Z * SD[m]
                    elif remaining <= SAFE_TAIL_DAYS:
                        v = safe(base_val, SD[m], remaining)
                    else:
                        v = base_val + rng.gauss(0, SD[m])
                hist[m].append(v)
                emit(day, m, v, SOURCE[m])

            # load (sRPE) — Silva's last week solved to the target ACWR
            if name == "D. Silva" and remaining == ACUTE_DAYS:
                acute = solve_acute_load(loads[-21:], SILVA_TARGET_ACWR)
            if name == "D. Silva" and remaining <= ACUTE_DAYS:
                load = acute
            else:
                load = max(120.0, rng.gauss(420, 55))
            loads.append(load)
            emit(day, "srpe_au", load, "form")
            emit(day, "hsr_m", max(0.0, rng.gauss(600, 120)), "gps")
            emit(day, "total_m", max(0.0, rng.gauss(5200, 700)), "gps")

    rows.sort(key=lambda r: (r["day"], r["athlete_id"], r["metric"]))
    return rows


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(Path(__file__).parent.parent / "data" / "synthetic.csv"))
    args = ap.parse_args()
    rows = generate()
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["athlete_id", "name", "pos", "day",
                                               "metric", "value", "source"])
        writer.writeheader()
        writer.writerows(rows)
    print(f"Wrote {len(rows)} readings ({len(SQUAD)} athletes x {DAYS} days) -> {out}")


if __name__ == "__main__":
    main()
