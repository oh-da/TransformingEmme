# TLV Model v4.33 — EMME matrices as TAZ CSVs

Each scenario folder holds the EMME exports and their CSV equivalents:

```
Matrices/
  2018/            EMME/*.in   CSV/*.csv     Scenario 1971 — base year 2018
  2050_BU/         EMME/*.in   CSV/*.csv     Scenario 5971 — 2050 Business As Usual
  2050_HS/         EMME/*.in   CSV/*.csv     Scenario 5972 — 2050 Strategic Plan
  QA/                                        conversion + validation output
```

> The 2050 strategic-plan scenario is stored as `2050_HS` (it is the "SP" /
> Strategic Plan scenario 5972 in `ExportedMatrices_TLVModel_V433.txt`).

## The nine matrices per scenario

| file | contents | period |
|---|---|---|
| `AUTOTOT_a` / `_o` / `_p` | total auto trips | AM / Offpeak / PM |
| `PRKRTotDemand_a` / `_o` / `_p` | Park & Ride + Kiss & Ride total demand | AM / Offpeak / PM |
| `TransitTotDemand_a` / `_o` / `_p` | total transit trips | AM / Offpeak / PM |

## CSV layout

Zone system: the `TAZV41` column of `taz_layer/TAZ_v41.shp` — **1310 zones,
1101…8451**, sorted ascending.

* row 1 is the header: `TAZV41` followed by the 1310 destination zone ids;
* column 1 is the origin zone id;
* cell *(i, j)* is the number of trips from origin *i* to destination *j*;
* every O-D pair is written, zeros included, so all files are 1311 × 1311.

## Regenerating and checking

```bash
python3 scripts/convert_emme_to_csv.py     # .in -> CSV  (~45 s)
python3 scripts/validate_matrices.py       # 234 logical tests (~50 s)
```

Only `numpy` is required; the shapefile attribute table is read directly, so
no GIS stack is needed.

## QA output

| file | contents |
|---|---|
| `QA/validation_report.md` | test results plus the totals, mode-share and growth tables |
| `QA/conversion_summary.csv` | per-file pair counts and totals from the conversion run |
| `QA/scenario_totals.csv` | trips, intrazonal share and cell fill per scenario/matrix/period |
| `QA/offtaz_zone_totals.csv` | trips on zones that have no `TAZV41` row/column |

## Zones outside `TAZV41`

The `.in` files also carry zones that do not exist in `TAZ_v41`: external /
cordon zones (ids below 1000) and the P&R / K&R station zones (ids 9xxx).
They have no row or column in a `TAZV41`-indexed matrix, so those trips are
excluded from the CSVs — 10–27 % of the trips depending on the matrix — and
listed instead in `QA/offtaz_zone_totals.csv`. The identity

```
CSV total + off-TAZ total == .in total
```

is asserted for all 27 matrices by the *reconciliation* test group.
