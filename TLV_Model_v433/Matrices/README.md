# TLV Model v4.33 — EMME matrices as TAZ CSVs

Each scenario folder holds the EMME exports and their CSV equivalents:

```
Matrices/
  2018/            EMME/*.in   CSV/*.csv     2018     — EMME scenario 1971, base year
  2050_BU/         EMME/*.in   CSV/*.csv     2050_BU  — EMME scenario 5971, Business As Usual
  2050_HS/         EMME/*.in   CSV/*.csv     2050_SP  — EMME scenario 5972, Strategic Plan
  QA/                                        conversion + validation output
```

> **`2050_HS` is the `2050_SP` scenario.** The directory keeps the name the
> EMME export used; everything the scripts report — QA tables, the validation
> report, the `scenario` column of every QA CSV — calls it `2050_SP`, with the
> directory name alongside it in `scenario_dir`. Either name works for
> `--scenario` on the command line.

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

## How to run it

The CSV files in this repository are already built — you only need this
section if the EMME exports change and you want to rebuild them, or if you
want to satisfy yourself that the numbers are right.

There are two programs and they are meant to be run **in this order**: the
first one builds the CSV files, the second one checks them. Neither one ever
modifies the EMME `.in` files, so you cannot damage the source data by
running them.

### Before the first run (once only)

You need Python 3 and one add-on library called `numpy`, which does the
number-crunching. To install it, open a terminal (Command Prompt on Windows,
Terminal on Mac) and type:

```bash
pip install numpy
```

That is the only thing to install. The zone numbers are read straight out of
the shapefile's attribute table, so you do **not** need ArcGIS, QGIS or any
other GIS software installed for this to work.

Then move to the folder that contains this project — everything below assumes
you are in the folder that holds the `scripts` and `TLV_Model_v433` folders:

```bash
cd path/to/TransformingEmme
```

### Step 1 — build the CSV files

```bash
python3 scripts/convert_emme_to_csv.py
```

This takes about 45 seconds. While it runs it does the following, in order:

1. **Reads the zone list.** It opens the attribute table of
   `taz_layer/TAZ_v41.shp` and takes the `TAZV41` column — the 1310 zone
   numbers from 1101 to 8451. These become the row and column labels of every
   CSV. If the same zone number appeared twice the program stops immediately
   rather than produce a confusing matrix.
2. **Finds the scenarios.** Any folder inside `Matrices` that contains an
   `EMME` sub-folder counts as a scenario, so 2018, 2050_BU and 2050_SP are
   picked up automatically. Nothing is hard-coded — a fourth scenario dropped
   in later is converted without changing the program.
3. **Works through the nine matrices of each scenario**, one at a time —
   auto, P&R + K&R, and transit, each for the AM, off-peak and PM period. For
   each one it:
   - skips the EMME header block at the top of the `.in` file and starts
     reading at the line beginning `a matrix=`;
   - reads every "from-zone to-zone: number of trips" entry and places it in
     the right cell of a blank 1310 × 1310 table;
   - sets aside any entry whose origin or destination is not one of the 1310
     zones — the external/cordon zones and the P&R station zones described at
     the bottom of this page — and keeps a running total of them so that
     nothing is lost silently;
   - writes the finished table to `CSV/<name>.csv` next to the `EMME` folder.
4. **Writes two summary files** into the `QA` folder recording how many trips
   went into each CSV and how many landed on zones outside the TAZ layer.

As it goes it prints one line per matrix, so you can watch the progress:

```
=== scenario 2018
  AUTOTOT_a.in    -> AUTOTOT_a.csv    pairs= 796,703  total= 556,994.60  in-TAZ= 493,916.50 (88.68%)
```

Read that as: this matrix listed 796,703 origin-destination entries totalling
556,994.6 trips, and 493,916.5 of them (88.68 %) sit inside the 1310-zone TAZ
system and were written to the CSV.

### Step 2 — check the result

```bash
python3 scripts/validate_matrices.py
```

This takes about 50 seconds and runs 234 separate tests. It is deliberately
suspicious of step 1: it does not trust anything that step 1 reported, and
instead re-reads both the original `.in` files and the CSV files from scratch
and compares them. In order, for each of the 27 matrices it asks:

1. **Are the labels right?** Do the row labels and the column headers of the
   CSV match the 1310 `TAZV41` zone numbers exactly, in the same order?
2. **Was anything lost while reading?** A second, deliberately simple reader
   adds up every number in the `.in` file. Its total and its count of entries
   must match what the converter found.
3. **Do the trips add up?** Trips in the CSV, plus the trips on zones outside
   the TAZ layer, must equal the total in the `.in` file — to the last
   decimal. This is the test that proves nothing was quietly dropped.
4. **Did the CSV survive being written?** The CSV is read back from disk and
   compared with the original: the same grand total, the same value in every
   single one of the 1,716,100 cells, and the same number of non-empty cells.
5. **Is the matrix internally consistent?** Adding up the rows (trips leaving
   each zone) must give the same answer as adding up the columns (trips
   arriving in each zone), and both must equal the grand total.
6. **Are the values sensible?** No missing or infinite numbers, no negative
   trips, and no origin-destination pair listed twice in the source.

Then it compares the matrices against each other: that each daily figure
equals its AM + off-peak + PM parts, and that both 2050 scenarios are at or
above the 2018 base for every mode.

Finally it writes the results to `QA/validation_report.md` and
`QA/scenario_totals.csv` and prints the verdict:

```
234 checks run, 0 failed.
```

**Anything other than `0 failed` means the CSV files should not be used.**
The failing tests are named individually on screen and listed again in a
"Failures" section at the top of `QA/validation_report.md`, so you can see
which scenario and which matrix is affected.

### Useful variations

| command | what it does |
|---|---|
| `python3 scripts/convert_emme_to_csv.py --scenario 2018` | rebuild one scenario only, instead of all three |
| `python3 scripts/convert_emme_to_csv.py --scenario 2050_SP` | the same, using the scenario name rather than the folder name `2050_HS` |
| `python3 scripts/convert_emme_to_csv.py --gzip` | write compressed `.csv.gz` files instead — a tenth of the size, and readable directly by Excel-alternatives and by pandas, though not by Excel itself |
| `python3 scripts/convert_emme_to_csv.py --help` | list every option |

Note that `--scenario` also limits what goes into the `QA` summary files, so
after a partial rebuild run the plain command once more to restore the full
summaries.

### If something goes wrong

| message | what it means |
|---|---|
| `No module named 'numpy'` | the one-time install above has not been done — run `pip install numpy` |
| `no such file or directory: scripts/...` | you are in the wrong folder — `cd` to the folder holding `scripts` and `TLV_Model_v433` |
| `column 'TAZV41' not found` | the shapefile was replaced with one that names its zone column differently |
| `TAZV41 is not unique` | the replacement zone layer repeats a zone number; it must be fixed before a matrix can be built from it |
| `more than one matrix block` | an `.in` file holds several matrices stacked together, which these exports never do — the file needs splitting first |

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
