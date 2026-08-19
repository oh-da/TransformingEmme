#!/usr/bin/env python3
"""Convert every EMME ``.in`` matrix in the model tree into a TAZ-indexed CSV.

For each scenario under ``TLV_Model_v433/Matrices`` the nine exported matrices
(AUTOTOT / PRKRTotDemand / TransitTotDemand x a/o/p) are written to
``<scenario>/CSV/<name>.csv`` as a dense square matrix whose index and header
are the ``TAZV41`` zone ids taken from ``taz_layer/taz_v41.dbf`` (the attribute
table of ``TAZ_v41.shp``).

A per-file conversion summary is written to ``Matrices/QA/conversion_summary.csv``
so the totals can be reconciled against the raw ``.in`` files.

Usage::

    python3 scripts/convert_emme_to_csv.py [--root TLV_Model_v433] [--gzip]
"""

from __future__ import annotations

import argparse
import csv
import gzip
import shutil
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from emme_matrix_tools import (  # noqa: E402
    PERIODS,
    expected_files,
    find_scenarios,
    matches_scenario,
    parse_emme_in,
    read_taz_ids,
    scenario_label,
    write_matrix_csv,
)

SUMMARY_COLUMNS = [
    "scenario",
    "scenario_dir",
    "matrix",
    "period",
    "period_label",
    "in_file",
    "csv_file",
    "matrix_header",
    "pairs_in_file",
    "pairs_in_taz",
    "duplicate_pairs",
    "negative_values",
    "total_trips_in_file",
    "total_trips_in_csv",
    "total_trips_off_taz",
    "pct_trips_in_csv",
    "off_taz_origin_zones",
    "off_taz_dest_zones",
    "nonzero_cells",
    "zones",
]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "TLV_Model_v433",
        help="model root containing taz_layer/ and Matrices/",
    )
    parser.add_argument(
        "--gzip",
        action="store_true",
        help="also write a .csv.gz beside each CSV and drop the plain file",
    )
    parser.add_argument(
        "--scenario",
        action="append",
        help="limit to the named scenario, by directory or label (repeatable)",
    )
    args = parser.parse_args()

    root: Path = args.root
    dbf = root / "taz_layer" / "taz_v41.dbf"
    matrices_root = root / "Matrices"

    taz_ids = read_taz_ids(dbf, "TAZV41")
    print(f"TAZ_v41 / TAZV41: {len(taz_ids)} zones "
          f"({taz_ids.min()}..{taz_ids.max()})")

    scenarios = find_scenarios(matrices_root)
    if args.scenario:
        scenarios = [
            s
            for s in scenarios
            if any(matches_scenario(s.name, w) for w in args.scenario)
        ]
    if not scenarios:
        print("no scenarios found", file=sys.stderr)
        return 1

    rows = []
    off_taz_rows = []
    for scenario_dir in scenarios:
        scen = scenario_label(scenario_dir.name)
        suffix = "" if scen == scenario_dir.name else f" (directory {scenario_dir.name})"
        print(f"\n=== scenario {scen}{suffix}")
        for kind, period, in_path in expected_files(scenario_dir):
            if not in_path.exists():
                print(f"  MISSING {in_path.name}", file=sys.stderr)
                continue
            t0 = time.time()
            parsed = parse_emme_in(in_path, taz_ids)

            csv_path = scenario_dir / "CSV" / f"{kind}_{period}.csv"
            write_matrix_csv(parsed.matrix, taz_ids, csv_path)
            if args.gzip:
                with open(csv_path, "rb") as src, gzip.open(
                    csv_path.with_suffix(".csv.gz"), "wb", compresslevel=6
                ) as dst:
                    shutil.copyfileobj(src, dst)
                csv_path.unlink()
                csv_path = csv_path.with_suffix(".csv.gz")

            nonzero = int((parsed.matrix != 0).sum())
            pct = (
                100.0 * parsed.taz_total / parsed.file_total
                if parsed.file_total
                else 0.0
            )
            rows.append(
                {
                    "scenario": scen,
                    "scenario_dir": scenario_dir.name,
                    "matrix": kind,
                    "period": period,
                    "period_label": PERIODS[period],
                    "in_file": str(in_path.relative_to(root)),
                    "csv_file": str(csv_path.relative_to(root)),
                    "matrix_header": parsed.matrix_header,
                    "pairs_in_file": parsed.n_pairs,
                    "pairs_in_taz": parsed.n_pairs_in_taz,
                    "duplicate_pairs": parsed.duplicate_pairs,
                    "negative_values": parsed.negative_values,
                    "total_trips_in_file": f"{parsed.file_total:.6f}",
                    "total_trips_in_csv": f"{parsed.taz_total:.6f}",
                    "total_trips_off_taz": f"{parsed.off_taz_total:.6f}",
                    "pct_trips_in_csv": f"{pct:.4f}",
                    "off_taz_origin_zones": len(parsed.off_taz_origins),
                    "off_taz_dest_zones": len(parsed.off_taz_dests),
                    "nonzero_cells": nonzero,
                    "zones": len(taz_ids),
                }
            )
            for zone in sorted(parsed.off_taz_origins | parsed.off_taz_dests):
                off_taz_rows.append(
                    {
                        "scenario": scen,
                        "scenario_dir": scenario_dir.name,
                        "matrix": kind,
                        "period": period,
                        "zone": zone,
                        "trips_from_zone": f"{parsed.off_taz_from.get(zone, 0.0):.6f}",
                        "trips_to_zone": f"{parsed.off_taz_to.get(zone, 0.0):.6f}",
                    }
                )

            print(
                f"  {in_path.name:<24} -> {csv_path.name:<24} "
                f"pairs={parsed.n_pairs:>8,} "
                f"total={parsed.file_total:>14,.2f} "
                f"in-TAZ={parsed.taz_total:>14,.2f} ({pct:5.2f}%) "
                f"[{time.time() - t0:4.1f}s]"
            )

    qa_dir = matrices_root / "QA"
    qa_dir.mkdir(parents=True, exist_ok=True)
    summary_path = qa_dir / "conversion_summary.csv"
    with open(summary_path, "w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=SUMMARY_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)
    print(f"\nwrote {summary_path} ({len(rows)} matrices)")

    # Marginals of the zones that have no TAZV41 row/column (external/cordon
    # zones and P&R station zones), so the trips left out of the CSVs stay
    # traceable. A pair whose origin *and* destination are both off-TAZ shows
    # up in both columns, so do not add the two columns together.
    off_taz_path = qa_dir / "offtaz_zone_totals.csv"
    with open(off_taz_path, "w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(
            fh,
            fieldnames=[
                "scenario",
                "scenario_dir",
                "matrix",
                "period",
                "zone",
                "trips_from_zone",
                "trips_to_zone",
            ],
        )
        writer.writeheader()
        writer.writerows(off_taz_rows)
    print(f"wrote {off_taz_path} ({len(off_taz_rows)} rows)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
