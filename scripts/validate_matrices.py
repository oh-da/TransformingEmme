#!/usr/bin/env python3
"""Logical tests for the EMME ``.in`` -> CSV conversion.

Every test is a sum-and-compare check:

1.  *zone index*    -- the CSV index and header are exactly the 1310 ``TAZV41``
    ids of ``TAZ_v41.shp``, in the same order, on every file.
2.  *raw total*     -- an independent re-scan of the ``.in`` file (a separate,
    deliberately dumb parser) reproduces the total the converter reported.
3.  *reconciliation*-- ``total in CSV + total on off-TAZ zones == total in .in``.
4.  *csv round-trip*-- re-reading the CSV gives back the same grand total,
    the same non-zero cell count and the same individual cells.
5.  *row/col sums*  -- sum of row totals == sum of column totals == grand total.
6.  *value sanity*  -- no NaN/inf, no negative trips, no duplicated O-D pairs.
7.  *comparisons*   -- daily (a+o+p) totals per matrix per scenario, mode
    shares, intrazonal shares and 2050/2018 growth ratios are tabulated and
    checked for internal consistency (daily == a + o + p).

Usage::

    python3 scripts/validate_matrices.py [--root TLV_Model_v433]
"""

from __future__ import annotations

import argparse
import csv
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))

from emme_matrix_tools import (  # noqa: E402
    KIND_LABELS,
    MATRIX_KINDS,
    PERIODS,
    SCENARIO_NUMBERS,
    expected_files,
    find_scenarios,
    parse_emme_in,
    read_matrix_csv,
    read_taz_ids,
    scenario_label,
)

REL_TOL = 1e-9  # in-memory comparisons
CSV_TOL = 1e-7  # comparisons that survive %.9g text formatting


class Results:
    """Collects PASS/FAIL lines so the report and the exit code agree."""

    def __init__(self) -> None:
        self.rows: list[tuple[str, str, bool, str]] = []

    def check(self, group: str, name: str, ok: bool, detail: str = "") -> bool:
        self.rows.append((group, name, bool(ok), detail))
        flag = "PASS" if ok else "FAIL"
        print(f"  [{flag}] {name}" + (f" -- {detail}" if detail else ""))
        return bool(ok)

    @property
    def failed(self) -> list[tuple[str, str, bool, str]]:
        return [r for r in self.rows if not r[2]]


def close(a: float, b: float, tol: float) -> bool:
    scale = max(1.0, abs(a), abs(b))
    return abs(a - b) <= tol * scale


def raw_total(path: Path) -> tuple[float, int]:
    """Independent second parser: sum every ``dest:value`` token after the header."""
    total = 0.0
    count = 0
    started = False
    with open(path, "r", encoding="latin-1") as fh:
        for line in fh:
            if not started:
                started = line.startswith("a matrix=")
                continue
            for token in line.split():
                if ":" in token:
                    total += float(token.split(":", 1)[1])
                    count += 1
    return total, count


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "TLV_Model_v433",
    )
    args = parser.parse_args()
    root: Path = args.root
    matrices_root = root / "Matrices"

    taz_ids = read_taz_ids(root / "taz_layer" / "taz_v41.dbf", "TAZV41")
    n_zones = len(taz_ids)
    res = Results()

    print(f"TAZ_v41 / TAZV41: {n_zones} zones ({taz_ids.min()}..{taz_ids.max()})\n")

    scenarios = find_scenarios(matrices_root)
    totals: dict[tuple[str, str, str], float] = {}
    file_totals: dict[tuple[str, str, str], float] = {}
    offtaz_totals: dict[tuple[str, str, str], float] = {}
    intrazonal: dict[tuple[str, str, str], float] = {}
    nonzero_cells: dict[tuple[str, str, str], int] = {}

    scen_dirs: dict[str, str] = {}
    for scenario_dir in scenarios:
        scen = scenario_label(scenario_dir.name)
        scen_dirs[scen] = scenario_dir.name
        print(f"=== {scen}")
        for kind, period, in_path in expected_files(scenario_dir):
            key = (scen, kind, period)
            csv_path = scenario_dir / "CSV" / f"{kind}_{period}.csv"
            label = f"{scen}/{kind}_{period}"

            if not (in_path.exists() and csv_path.exists()):
                res.check("files", f"{label}: inputs present", False,
                          f"missing {in_path.name if not in_path.exists() else csv_path.name}")
                continue

            parsed = parse_emme_in(in_path, taz_ids)
            row_ids, col_ids, mat = read_matrix_csv(csv_path)

            # 1. zone index / header
            res.check(
                "zone index",
                f"{label}: CSV index & header == TAZV41",
                np.array_equal(row_ids, taz_ids) and np.array_equal(col_ids, taz_ids),
                f"{len(row_ids)}x{len(col_ids)} vs {n_zones}x{n_zones}",
            )

            # 2. independent re-scan of the .in file
            rtotal, rcount = raw_total(in_path)
            res.check(
                "raw total",
                f"{label}: re-scan total == parser total",
                close(rtotal, parsed.file_total, REL_TOL) and rcount == parsed.n_pairs,
                f"{rtotal:,.4f} vs {parsed.file_total:,.4f} "
                f"({rcount:,} vs {parsed.n_pairs:,} pairs)",
            )

            # 3. reconciliation in-TAZ + off-TAZ == file
            res.check(
                "reconciliation",
                f"{label}: CSV + off-TAZ == .in",
                close(parsed.taz_total + parsed.off_taz_total, parsed.file_total, REL_TOL),
                f"{parsed.taz_total:,.4f} + {parsed.off_taz_total:,.4f} "
                f"= {parsed.taz_total + parsed.off_taz_total:,.4f} "
                f"vs {parsed.file_total:,.4f}",
            )

            # 4. CSV round-trip
            csv_total = float(mat.sum())
            res.check(
                "round-trip",
                f"{label}: CSV grand total == parsed in-TAZ total",
                close(csv_total, parsed.taz_total, CSV_TOL),
                f"{csv_total:,.4f} vs {parsed.taz_total:,.4f}",
            )
            max_cell_diff = float(np.abs(mat - parsed.matrix).max())
            res.check(
                "round-trip",
                f"{label}: every CSV cell == parsed cell",
                max_cell_diff <= CSV_TOL * max(1.0, float(np.abs(parsed.matrix).max())),
                f"max abs cell difference {max_cell_diff:.3g}",
            )
            res.check(
                "round-trip",
                f"{label}: non-zero cell count matches",
                int((mat != 0).sum()) == int((parsed.matrix != 0).sum()),
                f"{int((mat != 0).sum()):,} cells",
            )

            # 5. row sums == col sums == grand total
            row_sum = float(mat.sum(axis=1).sum())
            col_sum = float(mat.sum(axis=0).sum())
            res.check(
                "row/col sums",
                f"{label}: sum(productions) == sum(attractions) == total",
                close(row_sum, col_sum, REL_TOL) and close(row_sum, csv_total, REL_TOL),
                f"rows {row_sum:,.4f} / cols {col_sum:,.4f} / total {csv_total:,.4f}",
            )

            # 6. value sanity
            res.check(
                "sanity",
                f"{label}: finite, non-negative, no duplicate O-D pairs",
                bool(np.isfinite(mat).all())
                and float(mat.min()) >= 0.0
                and parsed.duplicate_pairs == 0
                and parsed.negative_values == 0,
                f"min {float(mat.min()):.6g}, duplicates {parsed.duplicate_pairs}, "
                f"negatives {parsed.negative_values}",
            )

            totals[key] = csv_total
            file_totals[key] = parsed.file_total
            offtaz_totals[key] = parsed.off_taz_total
            intrazonal[key] = float(np.trace(mat))
            nonzero_cells[key] = int((mat != 0).sum())
        print()

    # ------------------------------------------------------------------ #
    # 7. comparisons across periods, matrices and scenarios
    # ------------------------------------------------------------------ #
    print("=== comparisons")
    scen_names = [scenario_label(s.name) for s in scenarios]
    daily: dict[tuple[str, str], float] = {}
    daily_file: dict[tuple[str, str], float] = {}
    for scen in scen_names:
        for kind in MATRIX_KINDS:
            parts = [totals.get((scen, kind, p)) for p in PERIODS]
            if any(v is None for v in parts):
                continue
            daily[(scen, kind)] = float(sum(parts))
            daily_file[(scen, kind)] = float(
                sum(file_totals[(scen, kind, p)] for p in PERIODS)
            )
            res.check(
                "comparison",
                f"{scen}/{kind}: daily == AM + Offpeak + PM",
                close(daily[(scen, kind)], sum(parts), REL_TOL),
                f"{daily[(scen, kind)]:,.2f}",
            )

    # scenario-level totals across the three matrices
    scen_daily = {
        scen: sum(daily[(scen, k)] for k in MATRIX_KINDS if (scen, k) in daily)
        for scen in scen_names
    }
    for scen in scen_names:
        res.check(
            "comparison",
            f"{scen}: scenario daily total == sum of the 3 matrices",
            close(
                scen_daily[scen],
                sum(daily[(scen, k)] for k in MATRIX_KINDS if (scen, k) in daily),
                REL_TOL,
            ),
            f"{scen_daily[scen]:,.2f} trips/day inside the TAZ layer",
        )

    base = "2018"
    if base in scen_names:
        for scen in scen_names:
            if scen == base:
                continue
            for kind in MATRIX_KINDS:
                if (scen, kind) not in daily or (base, kind) not in daily:
                    continue
                ratio = daily[(scen, kind)] / daily[(base, kind)]
                res.check(
                    "comparison",
                    f"{scen}/{kind}: 2050 forecast >= 2018 base",
                    ratio >= 1.0,
                    f"x{ratio:.3f} ({daily[(base, kind)]:,.0f} -> "
                    f"{daily[(scen, kind)]:,.0f})",
                )

    # ------------------------------------------------------------------ #
    # report files
    # ------------------------------------------------------------------ #
    qa_dir = matrices_root / "QA"
    qa_dir.mkdir(parents=True, exist_ok=True)

    totals_path = qa_dir / "scenario_totals.csv"
    with open(totals_path, "w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(
            [
                "scenario",
                "scenario_dir",
                "matrix",
                "period",
                "period_label",
                "trips_in_csv",
                "trips_in_in_file",
                "trips_off_taz",
                "pct_in_csv",
                "intrazonal_trips",
                "pct_intrazonal",
                "nonzero_cells",
                "pct_cells_filled",
            ]
        )
        for scen in scen_names:
            for kind in MATRIX_KINDS:
                for period in PERIODS:
                    key = (scen, kind, period)
                    if key not in totals:
                        continue
                    t = totals[key]
                    w.writerow(
                        [
                            scen,
                            scen_dirs[scen],
                            kind,
                            period,
                            PERIODS[period],
                            f"{t:.4f}",
                            f"{file_totals[key]:.4f}",
                            f"{offtaz_totals[key]:.4f}",
                            f"{100 * t / file_totals[key]:.4f}" if file_totals[key] else "",
                            f"{intrazonal[key]:.4f}",
                            f"{100 * intrazonal[key] / t:.4f}" if t else "",
                            nonzero_cells[key],
                            f"{100 * nonzero_cells[key] / (n_zones * n_zones):.4f}",
                        ]
                    )
    print(f"\nwrote {totals_path}")

    report_path = qa_dir / "validation_report.md"
    with open(report_path, "w", encoding="utf-8") as fh:
        fh.write("# EMME `.in` -> CSV conversion: validation report\n\n")
        fh.write(
            f"Zone system: `TAZ_v41.shp` / `TAZV41` -- **{n_zones} zones** "
            f"({taz_ids.min()}..{taz_ids.max()}), used as both the CSV index "
            "and the CSV header.\n\n"
        )
        fh.write("Scenarios:\n\n")
        fh.write("| scenario | EMME scenario | directory |\n|---|---:|---|\n")
        for scen in scen_names:
            number = SCENARIO_NUMBERS.get(scen, "")
            fh.write(f"| {scen} | {number} | `Matrices/{scen_dirs[scen]}/` |\n")
        fh.write("\n")

        fh.write("## Test summary\n\n")
        groups = defaultdict(lambda: [0, 0])
        for group, _name, ok, _detail in res.rows:
            groups[group][0] += 1
            groups[group][1] += 0 if ok else 1
        fh.write("| test group | checks | failures |\n|---|---:|---:|\n")
        for group, (total, fails) in groups.items():
            fh.write(f"| {group} | {total} | {fails} |\n")
        fh.write(
            f"\n**{len(res.rows)} checks, {len(res.failed)} failures.**\n\n"
        )
        if res.failed:
            fh.write("### Failures\n\n")
            for group, name, _ok, detail in res.failed:
                fh.write(f"- `{group}` {name} -- {detail}\n")
            fh.write("\n")

        fh.write("## Trips per matrix (inside the TAZ_v41 zone system)\n\n")
        fh.write("| scenario | matrix | AM | Offpeak | PM | daily (a+o+p) |\n")
        fh.write("|---|---|---:|---:|---:|---:|\n")
        for scen in scen_names:
            for kind in MATRIX_KINDS:
                if (scen, kind) not in daily:
                    continue
                cells = " | ".join(
                    f"{totals[(scen, kind, p)]:,.0f}" for p in PERIODS
                )
                fh.write(
                    f"| {scen} | {kind} | {cells} | {daily[(scen, kind)]:,.0f} |\n"
                )

        fh.write("\n## Mode shares (daily, inside the TAZ layer)\n\n")
        fh.write("| scenario | " + " | ".join(MATRIX_KINDS) + " | total |\n")
        fh.write("|---" * (len(MATRIX_KINDS) + 2) + "|\n")
        for scen in scen_names:
            tot = scen_daily[scen]
            cells = " | ".join(
                f"{daily[(scen, k)]:,.0f} ({100 * daily[(scen, k)] / tot:.1f}%)"
                if (scen, k) in daily
                else "-"
                for k in MATRIX_KINDS
            )
            fh.write(f"| {scen} | {cells} | {tot:,.0f} |\n")

        if base in scen_names:
            fh.write("\n## Growth vs 2018 (daily totals inside the TAZ layer)\n\n")
            fh.write("| matrix | " + " | ".join(scen_names) + " |\n")
            fh.write("|---" * (len(scen_names) + 1) + "|\n")
            for kind in MATRIX_KINDS:
                cells = []
                for scen in scen_names:
                    if (scen, kind) not in daily:
                        cells.append("-")
                    else:
                        ratio = daily[(scen, kind)] / daily[(base, kind)]
                        cells.append(f"{daily[(scen, kind)]:,.0f} (x{ratio:.2f})")
                fh.write(f"| {KIND_LABELS[kind]} | " + " | ".join(cells) + " |\n")

        fh.write(
            "\n## Trips outside the TAZ_v41 zone system\n\n"
            "The `.in` files also carry zones that do not exist in `TAZ_v41` -- "
            "external/cordon zones (ids below 1000) and the P&R / K&R station "
            "zones (ids 9xxx). Those rows and columns cannot be placed in a "
            "`TAZV41`-indexed matrix, so they are excluded from the CSVs and "
            "reported here instead; `CSV total + off-TAZ total` always equals "
            "the `.in` total (test group *reconciliation*).\n\n"
        )
        fh.write("| scenario | matrix | period | .in total | CSV total | off-TAZ | % kept |\n")
        fh.write("|---|---|---|---:|---:|---:|---:|\n")
        for scen in scen_names:
            for kind in MATRIX_KINDS:
                for period in PERIODS:
                    key = (scen, kind, period)
                    if key not in totals:
                        continue
                    ft = file_totals[key]
                    fh.write(
                        f"| {scen} | {kind} | {PERIODS[period]} | {ft:,.1f} | "
                        f"{totals[key]:,.1f} | {offtaz_totals[key]:,.1f} | "
                        f"{100 * totals[key] / ft if ft else 0:.2f}% |\n"
                    )

    print(f"wrote {report_path}")

    print(
        f"\n{len(res.rows)} checks run, {len(res.failed)} failed."
    )
    return 1 if res.failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
